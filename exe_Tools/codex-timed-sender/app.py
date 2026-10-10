from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from uuid import uuid4

from timed_sender.content import validate_draft
from timed_sender.delivery import DeliveryService, TargetWindow
from timed_sender.models import Draft, ScheduledDelivery
from timed_sender.queue import QueueItem, QueueItemStatus, QueueSettings, QueueStore
from timed_sender.queue_runner import QueueRunner
from timed_sender.scheduler import validate_schedule
from timed_sender.windows import WindowsDesktopAdapter


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
STATUS_LABELS = {QueueItemStatus.PENDING: "待发送", QueueItemStatus.IN_FLIGHT: "发送中", QueueItemStatus.SENT: "已发送", QueueItemStatus.FAILED: "发送失败"}


def build_plan(target: TargetWindow | None, text: str, file_paths: tuple[Path, ...], image_path: Path | None, send_at: datetime, send_key: str) -> tuple[ScheduledDelivery | None, str | None]:
    if target is None:
        return None, "请先绑定 Codex 窗口。"
    draft = Draft(text, file_paths, image_path)
    error = validate_draft(draft) or validate_schedule(send_at, datetime.now())
    return (None, error) if error else (ScheduledDelivery(target, draft, send_at, send_key), None)


def build_queue_item(text: str, file_paths: tuple[Path, ...], image_path: Path | None, send_key: str, identifier: str, created_at: datetime) -> tuple[QueueItem | None, str | None]:
    draft = Draft(text, file_paths, image_path)
    error = validate_draft(draft)
    return (None, error) if error else (QueueItem(identifier, draft, send_key, created_at), None)


def build_queue_settings(target: TargetWindow | None, resume_text: str, interval_text: str, confirm_first: bool) -> tuple[QueueSettings | None, str | None]:
    if target is None:
        return None, "请先绑定 Codex 窗口。"
    try:
        resume_at = datetime.strptime(resume_text.strip(), TIME_FORMAT)
    except ValueError:
        return None, "额度恢复时间格式不正确。"
    try:
        interval_seconds = int(interval_text.strip())
    except ValueError:
        return None, "发送间隔必须是正整数秒。"
    if interval_seconds < 1:
        return None, "发送间隔必须是正整数秒。"
    return QueueSettings(resume_at, interval_seconds * 60, paused=False, confirm_first=confirm_first), None


class TimedSenderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Codex 队列投递器")
        self.root.geometry("760x800")
        self.adapter = WindowsDesktopAdapter()
        self.store = QueueStore()
        self.runner = QueueRunner(self.store, DeliveryService(self.adapter))
        self.target: TargetWindow | None = None
        self.bind_id: str | None = None
        self.tick_id: str | None = None
        self.files: tuple[Path, ...] = ()
        self.image_path: Path | None = None
        self.selected_identifier: str | None = None
        settings = self.runner.state.settings
        self.target_text = tk.StringVar(value="未绑定（重启程序后需要重新绑定）")
        self.image_text = tk.StringVar(value="未选择图片")
        self.resume_text = tk.StringVar(value=(settings.resume_at or datetime.now()).strftime(TIME_FORMAT))
        self.interval_text = tk.StringVar(value=str(max(1, (settings.interval_seconds + 59) // 60)))
        self.confirm_first = tk.BooleanVar(value=settings.confirm_first)
        self.send_key = tk.StringVar(value="enter")
        self.status = tk.StringVar(value=self.store.load_error or "可编辑草稿并加入队列。")
        self._build()
        self.refresh_queue()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        target_box = ttk.LabelFrame(frame, text="目标窗口", padding=8)
        target_box.grid(row=0, column=0, sticky="ew")
        target_box.columnconfigure(0, weight=1)
        ttk.Label(target_box, textvariable=self.target_text, wraplength=540).grid(row=0, column=0, sticky="w")
        ttk.Button(target_box, text="3 秒后绑定当前窗口", command=self.start_binding).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(target_box, text="解除绑定", command=self.clear_target).grid(row=0, column=2, padx=(8, 0))

        editor = ttk.LabelFrame(frame, text="编辑队列消息", padding=8)
        editor.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.message = tk.Text(editor, height=7, wrap="word")
        self.message.pack(fill="x", expand=True)
        file_row = ttk.Frame(editor)
        file_row.pack(fill="x", pady=(6, 0))
        ttk.Button(file_row, text="选择本地文件（发送路径）", command=self.choose_files).pack(side="left")
        ttk.Button(file_row, text="清除文件", command=self.clear_files).pack(side="left", padx=8)
        self.file_label = ttk.Label(editor, text="未选择文件", wraplength=700)
        self.file_label.pack(anchor="w", pady=(3, 0))
        image_row = ttk.Frame(editor)
        image_row.pack(fill="x", pady=(6, 0))
        ttk.Button(image_row, text="选择图片（作为附件粘贴）", command=self.choose_image).pack(side="left")
        ttk.Button(image_row, text="清除图片", command=self.clear_image).pack(side="left", padx=8)
        ttk.Label(editor, textvariable=self.image_text, wraplength=700).pack(anchor="w", pady=(3, 0))
        key_row = ttk.Frame(editor)
        key_row.pack(fill="x", pady=(6, 0))
        ttk.Radiobutton(key_row, text="Enter 发送", variable=self.send_key, value="enter").pack(side="left")
        ttk.Radiobutton(key_row, text="Ctrl+Enter 发送", variable=self.send_key, value="ctrl_enter").pack(side="left", padx=10)
        ttk.Button(key_row, text="加入队列", command=self.add_item).pack(side="right")
        ttk.Button(key_row, text="更新选中项", command=self.update_item).pack(side="right", padx=8)
        ttk.Button(key_row, text="新建草稿", command=self.clear_editor).pack(side="right")

        queue_box = ttk.LabelFrame(frame, text="待发送队列", padding=8)
        queue_box.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        queue_box.columnconfigure(0, weight=1)
        queue_box.rowconfigure(0, weight=1)
        self.queue_view = ttk.Treeview(queue_box, columns=("status", "content"), show="headings", height=8)
        self.queue_view.heading("status", text="状态")
        self.queue_view.heading("content", text="内容")
        self.queue_view.column("status", width=90, anchor="center", stretch=False)
        self.queue_view.column("content", width=610)
        self.queue_view.grid(row=0, column=0, sticky="nsew")
        self.queue_view.bind("<<TreeviewSelect>>", self.select_item)
        controls = ttk.Frame(queue_box)
        controls.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(controls, text="删除", command=self.delete_item).pack(side="left")
        ttk.Button(controls, text="上移", command=lambda: self.move_item(-1)).pack(side="left", padx=8)
        ttk.Button(controls, text="下移", command=lambda: self.move_item(1)).pack(side="left")

        schedule = ttk.LabelFrame(frame, text="额度恢复后自动投递", padding=8)
        schedule.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(schedule, text="额度恢复时间：").grid(row=0, column=0, sticky="w")
        ttk.Entry(schedule, textvariable=self.resume_text, width=22).grid(row=0, column=1, sticky="w")
        ttk.Label(schedule, text="YYYY-MM-DD HH:MM:SS").grid(row=0, column=2, padx=8, sticky="w")
        ttk.Label(schedule, text="每条间隔（分钟）：").grid(row=1, column=0, pady=(6, 0), sticky="w")
        ttk.Entry(schedule, textvariable=self.interval_text, width=8).grid(row=1, column=1, pady=(6, 0), sticky="w")
        ttk.Checkbutton(schedule, text="首条发送后等我确认再继续", variable=self.confirm_first).grid(row=1, column=2, pady=(6, 0), padx=8, sticky="w")
        buttons = ttk.Frame(schedule)
        buttons.grid(row=2, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="保存并启动队列", command=self.start_queue).pack(side="left")
        ttk.Button(buttons, text="暂停", command=self.pause_queue).pack(side="left", padx=8)
        ttk.Button(buttons, text="继续 / 重试", command=self.resume_queue).pack(side="left")
        ttk.Label(frame, textvariable=self.status, foreground="#245a88", wraplength=730).grid(row=4, column=0, sticky="w", pady=(8, 0))

    def start_binding(self) -> None:
        if self.bind_id is None:
            self.status.set("请在 3 秒内切换到要绑定的 Codex 对话窗口……")
            self.bind_id = self.root.after(3000, self.finish_binding)

    def finish_binding(self) -> None:
        self.bind_id = None
        target = self.adapter.current_foreground_target()
        if target is None or target.handle == self.root.winfo_id():
            self.status.set("未检测到可绑定窗口。请重试并切换到 Codex 对话。")
            return
        self.target = target
        self.target_text.set(f"已绑定：{target.title}（PID {target.process_id}）")
        self.status.set("窗口已绑定。")

    def clear_target(self) -> None:
        self.target = None
        self.target_text.set("未绑定（重启程序后需要重新绑定）")
        self.status.set("已解除绑定。")

    def choose_files(self) -> None:
        selected = filedialog.askopenfilenames(title="选择要作为路径发送的本地文件")
        if selected:
            self.files = tuple(Path(path) for path in selected)
            self.file_label.config(text="\n".join(str(path) for path in self.files))

    def clear_files(self) -> None:
        self.files = ()
        self.file_label.config(text="未选择文件")

    def choose_image(self) -> None:
        selected = filedialog.askopenfilename(title="选择要作为附件粘贴的图片", filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif"), ("所有文件", "*.*")])
        if selected:
            self.image_path = Path(selected)
            self.image_text.set(str(self.image_path))

    def clear_image(self) -> None:
        self.image_path = None
        self.image_text.set("未选择图片")

    def add_item(self) -> None:
        item, error = build_queue_item(self.message.get("1.0", "end-1c"), self.files, self.image_path, self.send_key.get(), uuid4().hex, datetime.now())
        if error:
            self.status.set(error)
            return
        self.runner.state = self.store.add(self.runner.state, item)
        self.store.save(self.runner.state)
        self.clear_editor()
        self.refresh_queue()
        self.status.set("已加入队列。")

    def update_item(self) -> None:
        if self.selected_identifier is None:
            self.status.set("请先在队列中选择一条消息。")
            return
        existing = next(item for item in self.runner.state.items if item.identifier == self.selected_identifier)
        item, error = build_queue_item(self.message.get("1.0", "end-1c"), self.files, self.image_path, self.send_key.get(), existing.identifier, existing.created_at)
        if error:
            self.status.set(error)
            return
        self.runner.state = self.store.update(self.runner.state, replace(item, status=existing.status, error=existing.error))
        self.store.save(self.runner.state)
        self.refresh_queue()
        self.status.set("队列消息已更新。")

    def delete_item(self) -> None:
        if self.selected_identifier is None:
            self.status.set("请先选择要删除的消息。")
            return
        self.runner.state = self.store.delete(self.runner.state, self.selected_identifier)
        self.store.save(self.runner.state)
        self.clear_editor()
        self.refresh_queue()
        self.status.set("已删除队列消息。")

    def move_item(self, offset: int) -> None:
        if self.selected_identifier is None:
            self.status.set("请先选择要移动的消息。")
            return
        self.runner.state = self.store.move(self.runner.state, self.selected_identifier, offset)
        self.store.save(self.runner.state)
        self.refresh_queue()

    def select_item(self, _event: object) -> None:
        selection = self.queue_view.selection()
        if not selection:
            return
        self.selected_identifier = selection[0]
        item = next(item for item in self.runner.state.items if item.identifier == self.selected_identifier)
        self.message.delete("1.0", "end")
        self.message.insert("1.0", item.draft.text)
        self.files = item.draft.file_paths
        self.file_label.config(text="\n".join(str(path) for path in self.files) if self.files else "未选择文件")
        self.image_path = item.draft.image_path
        self.image_text.set(str(self.image_path) if self.image_path else "未选择图片")
        self.send_key.set(item.send_key)

    def clear_editor(self) -> None:
        self.selected_identifier = None
        self.message.delete("1.0", "end")
        self.clear_files()
        self.clear_image()
        self.send_key.set("enter")
        self.queue_view.selection_remove(self.queue_view.selection())

    def refresh_queue(self) -> None:
        self.queue_view.delete(*self.queue_view.get_children())
        for item in self.runner.state.items:
            summary = item.draft.text.strip().replace("\n", " ") or "（仅文件或图片）"
            if item.status is QueueItemStatus.FAILED and item.error:
                summary = f"{summary} — {item.error}"
            self.queue_view.insert("", "end", iid=item.identifier, values=(STATUS_LABELS[item.status], summary[:100]))

    def start_queue(self) -> None:
        settings, error = build_queue_settings(self.target, self.resume_text.get(), self.interval_text.get(), self.confirm_first.get())
        if error:
            self.status.set(error)
            return
        self.runner.configure(settings)
        self.status.set("队列已启动，将在恢复时间后按顺序投递。")
        self.schedule_tick()

    def pause_queue(self) -> None:
        self.runner.pause()
        self.cancel_tick()
        self.status.set("队列已暂停；消息仍保留。")

    def resume_queue(self) -> None:
        if self.target is None:
            self.status.set("请先绑定 Codex 窗口。")
            return
        self.runner.resume()
        self.status.set("队列已继续，将重试失败消息或发送下一条。")
        self.schedule_tick()

    def schedule_tick(self) -> None:
        if self.tick_id is None:
            self.tick_id = self.root.after(250, self.tick)

    def tick(self) -> None:
        self.tick_id = None
        result = self.runner.tick(datetime.now(), self.target)
        self.status.set(result.message)
        self.refresh_queue()
        if not self.runner.state.settings.paused:
            self.schedule_tick()

    def cancel_tick(self) -> None:
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None


if __name__ == "__main__":
    root = tk.Tk()
    TimedSenderApp(root)
    root.mainloop()

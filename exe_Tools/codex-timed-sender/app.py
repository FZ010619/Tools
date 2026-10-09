from __future__ import annotations

import math
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from timed_sender.content import validate_draft
from timed_sender.delivery import DeliveryService, TargetWindow
from timed_sender.models import Draft, ScheduledDelivery
from timed_sender.scheduler import ScheduleState, schedule_state, validate_schedule
from timed_sender.windows import WindowsDesktopAdapter


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def build_plan(
    target: TargetWindow | None,
    text: str,
    file_paths: tuple[Path, ...],
    image_path: Path | None,
    send_at: datetime,
    send_key: str,
) -> tuple[ScheduledDelivery | None, str | None]:
    if target is None:
        return None, "请先绑定 Codex 窗口。"
    draft = Draft(text, file_paths, image_path)
    error = validate_draft(draft) or validate_schedule(send_at, datetime.now())
    if error:
        return None, error
    return ScheduledDelivery(target, draft, send_at, send_key), None


class TimedSenderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Codex 定时投递器")
        self.root.geometry("680x620")
        self.adapter = WindowsDesktopAdapter()
        self.delivery = DeliveryService(self.adapter)
        self.target: TargetWindow | None = None
        self.plan: ScheduledDelivery | None = None
        self.tick_id: str | None = None
        self.bind_id: str | None = None
        self.files: tuple[Path, ...] = ()
        self.image_path: Path | None = None

        self.target_text = tk.StringVar(value="未绑定")
        self.image_text = tk.StringVar(value="未选择图片")
        self.time_text = tk.StringVar(value=datetime.now().strftime(TIME_FORMAT))
        self.send_key = tk.StringVar(value="enter")
        self.status = tk.StringVar(value="就绪")
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        target_box = ttk.LabelFrame(frame, text="目标窗口", padding=8)
        target_box.grid(row=0, column=0, sticky="ew")
        target_box.columnconfigure(0, weight=1)
        ttk.Label(target_box, textvariable=self.target_text, wraplength=500).grid(row=0, column=0, sticky="w")
        ttk.Button(target_box, text="3 秒后绑定当前窗口", command=self.start_binding).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(target_box, text="解除绑定", command=self.clear_target).grid(row=0, column=2, padx=(8, 0))

        draft_box = ttk.LabelFrame(frame, text="要发送的内容", padding=8)
        draft_box.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        frame.rowconfigure(1, weight=1)
        self.message = tk.Text(draft_box, height=9, wrap="word")
        self.message.pack(fill="both", expand=True)
        file_row = ttk.Frame(draft_box)
        file_row.pack(fill="x", pady=(8, 0))
        ttk.Button(file_row, text="选择本地文件（发送路径）", command=self.choose_files).pack(side="left")
        ttk.Button(file_row, text="清除文件", command=self.clear_files).pack(side="left", padx=8)
        self.file_label = ttk.Label(draft_box, text="未选择文件", wraplength=620)
        self.file_label.pack(anchor="w", pady=(4, 0))
        image_row = ttk.Frame(draft_box)
        image_row.pack(fill="x", pady=(8, 0))
        ttk.Button(image_row, text="选择图片（作为附件粘贴）", command=self.choose_image).pack(side="left")
        ttk.Button(image_row, text="清除图片", command=self.clear_image).pack(side="left", padx=8)
        ttk.Label(draft_box, textvariable=self.image_text, wraplength=620).pack(anchor="w", pady=(4, 0))

        schedule_box = ttk.LabelFrame(frame, text="发送计划", padding=8)
        schedule_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(schedule_box, text="发送时间：").grid(row=0, column=0, sticky="w")
        ttk.Entry(schedule_box, textvariable=self.time_text, width=22).grid(row=0, column=1, sticky="w")
        ttk.Label(schedule_box, text="格式：YYYY-MM-DD HH:MM:SS").grid(row=0, column=2, padx=8, sticky="w")
        ttk.Radiobutton(schedule_box, text="Enter 发送", variable=self.send_key, value="enter").grid(row=1, column=0, pady=(6, 0), sticky="w")
        ttk.Radiobutton(schedule_box, text="Ctrl+Enter 发送", variable=self.send_key, value="ctrl_enter").grid(row=1, column=1, pady=(6, 0), sticky="w")
        ttk.Button(schedule_box, text="开始倒计时", command=self.start_plan).grid(row=1, column=2, pady=(6, 0), sticky="e")
        ttk.Button(schedule_box, text="取消计划", command=self.cancel_plan).grid(row=1, column=3, pady=(6, 0), padx=(8, 0), sticky="e")

        ttk.Separator(frame).grid(row=3, column=0, sticky="ew", pady=10)
        ttk.Label(frame, textvariable=self.status, foreground="#245a88", wraplength=650).grid(row=4, column=0, sticky="w")

    def start_binding(self) -> None:
        if self.bind_id:
            return
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
        self.target_text.set("未绑定")
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
        selected = filedialog.askopenfilename(
            title="选择要作为附件粘贴的图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif"), ("所有文件", "*.*")],
        )
        if selected:
            self.image_path = Path(selected)
            self.image_text.set(str(self.image_path))

    def clear_image(self) -> None:
        self.image_path = None
        self.image_text.set("未选择图片")

    def start_plan(self) -> None:
        try:
            send_at = datetime.strptime(self.time_text.get().strip(), TIME_FORMAT)
        except ValueError:
            self.status.set("发送时间格式不正确。")
            return
        plan, error = build_plan(
            self.target,
            self.message.get("1.0", "end-1c"),
            self.files,
            self.image_path,
            send_at,
            self.send_key.get(),
        )
        if error:
            self.status.set(error)
            return
        self.cancel_plan(silent=True)
        self.plan = plan
        self.status.set("计划已开始。")
        self.tick()

    def tick(self) -> None:
        if self.plan is None:
            return
        now = datetime.now()
        state = schedule_state(self.plan, now)
        remaining = max(0, math.ceil((self.plan.send_at - now).total_seconds()))
        if state is ScheduleState.DUE:
            self.send_now()
            return
        prefix = "即将发送，可点击取消。" if state is ScheduleState.WARNING else "等待发送。"
        self.status.set(f"{prefix} 剩余 {remaining} 秒。")
        self.tick_id = self.root.after(250, self.tick)

    def send_now(self) -> None:
        plan, self.plan = self.plan, None
        self.tick_id = None
        if plan is None:
            return
        result = self.delivery.deliver(plan)
        self.status.set(result.message)
        if not result.success:
            messagebox.showwarning("未发送", result.message)

    def cancel_plan(self, silent: bool = False) -> None:
        if self.tick_id:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None
        had_plan = self.plan is not None
        self.plan = None
        if had_plan and not silent:
            self.status.set("计划已取消。")


if __name__ == "__main__":
    root = tk.Tk()
    TimedSenderApp(root)
    root.mainloop()

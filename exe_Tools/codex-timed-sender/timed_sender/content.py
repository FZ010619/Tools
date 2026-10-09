from pathlib import Path

from .models import Draft


def format_message(draft: Draft) -> str:
    text = draft.text.strip()
    if not draft.file_paths:
        return text
    paths = "\n".join(f"- {path}" for path in draft.file_paths)
    heading = "本地文件路径："
    return f"{text}\n\n{heading}\n{paths}" if text else f"{heading}\n{paths}"


def validate_draft(draft: Draft) -> str | None:
    if not draft.text.strip() and not draft.file_paths and draft.image_path is None:
        return "请填写文本或选择文件或图片。"
    for path in draft.file_paths:
        if not Path(path).is_file():
            return f"文件不存在：{path}"
    if draft.image_path is not None and not Path(draft.image_path).is_file():
        return f"图片不存在：{draft.image_path}"
    return None

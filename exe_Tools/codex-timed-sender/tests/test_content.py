import tempfile
import unittest
from pathlib import Path

from timed_sender.content import format_message, validate_draft
from timed_sender.models import Draft


class ContentTests(unittest.TestCase):
    def test_formats_text_and_local_file_paths(self):
        draft = Draft("请分析这些资料", (Path(r"D:\work\one.pdf"), Path(r"D:\work\two.csv")))
        self.assertEqual(format_message(draft), "请分析这些资料\n\n本地文件路径：\n- D:\\work\\one.pdf\n- D:\\work\\two.csv")

    def test_rejects_empty_draft(self):
        self.assertEqual(validate_draft(Draft("   ", ())), "请填写文本或选择文件或图片。")

    def test_rejects_missing_file(self):
        self.assertEqual(validate_draft(Draft("", (Path(r"D:\missing-file.txt"),))), "文件不存在：D:\\missing-file.txt")

    def test_accepts_existing_file(self):
        with tempfile.NamedTemporaryFile() as handle:
            self.assertIsNone(validate_draft(Draft("", (Path(handle.name),))))

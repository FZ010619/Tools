import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from timed_sender.windows import VK_CONTROL, VK_V, WindowsDesktopAdapter


class WindowsAdapterTests(unittest.TestCase):
    def test_activate_waits_for_delayed_foreground_switch(self):
        target = type("Target", (), {"handle": 99})()
        adapter = WindowsDesktopAdapter()
        with patch("timed_sender.windows.user32") as user32, patch("timed_sender.windows.time.sleep") as sleep:
            user32.GetForegroundWindow.side_effect = [1, 1, 99]
            self.assertTrue(adapter.activate(target))
        user32.ShowWindow.assert_called_once()
        user32.SetForegroundWindow.assert_called_once_with(99)
        self.assertEqual(sleep.call_count, 2)

    def test_paste_image_places_image_and_pastes_it(self):
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.close()
        try:
            Image.new("RGB", (1, 1), "white").save(handle.name)
            adapter = WindowsDesktopAdapter()
            with patch.object(adapter, "_set_clipboard", return_value=True) as set_clipboard, patch.object(adapter, "_hotkey") as hotkey:
                self.assertTrue(adapter.paste_image(Path(handle.name)))
            set_clipboard.assert_called_once()
            hotkey.assert_called_once_with(VK_CONTROL, VK_V)
        finally:
            os.unlink(handle.name)

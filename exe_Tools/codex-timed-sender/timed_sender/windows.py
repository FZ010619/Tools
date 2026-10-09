import ctypes
import io
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image

from .delivery import TargetWindow


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
kernel32.GlobalFree.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = (wintypes.UINT, ctypes.c_void_p)
user32.SetClipboardData.restype = ctypes.c_void_p

CF_UNICODETEXT = 13
CF_DIB = 8
GMEM_MOVEABLE = 0x0002
SW_RESTORE = 9
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002


class WindowsDesktopAdapter:
    def target_is_valid(self, target: TargetWindow) -> bool:
        if not user32.IsWindow(target.handle):
            return False
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(target.handle, ctypes.byref(process_id))
        return process_id.value == target.process_id and self._window_title(target.handle) == target.title

    def activate(self, target: TargetWindow) -> bool:
        user32.ShowWindow(target.handle, SW_RESTORE)
        user32.SetForegroundWindow(target.handle)
        for _ in range(15):
            if user32.GetForegroundWindow() == target.handle:
                return True
            time.sleep(0.1)
        return False

    def paste_text(self, text: str) -> bool:
        if not self._set_clipboard(CF_UNICODETEXT, (text + "\0").encode("utf-16-le")):
            return False
        self._hotkey(VK_CONTROL, VK_V)
        return True

    def paste_image(self, image_path: Path) -> bool:
        try:
            with Image.open(image_path) as image:
                output = io.BytesIO()
                image.convert("RGB").save(output, "BMP")
            if not self._set_clipboard(CF_DIB, output.getvalue()[14:]):
                return False
            self._hotkey(VK_CONTROL, VK_V)
            return True
        except (OSError, ValueError):
            return False
        finally:
            if "output" in locals() and not output.closed:
                output.close()

    def send_key(self, key: str) -> None:
        if key == "ctrl_enter":
            self._hotkey(VK_CONTROL, VK_RETURN)
        else:
            self._key_press(VK_RETURN)

    @staticmethod
    def current_foreground_target() -> TargetWindow | None:
        handle = user32.GetForegroundWindow()
        if not handle:
            return None
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        title = WindowsDesktopAdapter._window_title(handle)
        return TargetWindow(handle, process_id.value, title) if title else None

    @staticmethod
    def _window_title(handle: int) -> str:
        length = user32.GetWindowTextLengthW(handle)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, len(buffer))
        return buffer.value

    @staticmethod
    def _set_clipboard(format_id: int, data: bytes) -> bool:
        if not user32.OpenClipboard(None):
            return False
        try:
            if not user32.EmptyClipboard():
                return False
            memory = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not memory:
                return False
            pointer = kernel32.GlobalLock(memory)
            ctypes.memmove(pointer, data, len(data))
            kernel32.GlobalUnlock(memory)
            if not user32.SetClipboardData(format_id, memory):
                kernel32.GlobalFree(memory)
                return False
            return True
        finally:
            user32.CloseClipboard()

    @staticmethod
    def _key_press(key: int) -> None:
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def _hotkey(modifier: int, key: int) -> None:
        user32.keybd_event(modifier, 0, 0, 0)
        WindowsDesktopAdapter._key_press(key)
        user32.keybd_event(modifier, 0, KEYEVENTF_KEYUP, 0)

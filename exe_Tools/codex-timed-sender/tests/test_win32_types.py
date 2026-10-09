import ctypes
import unittest

from timed_sender.windows import kernel32


class Win32TypeTests(unittest.TestCase):
    def test_clipboard_memory_functions_return_pointer_sized_values(self):
        self.assertIs(kernel32.GlobalAlloc.restype, ctypes.c_void_p)
        self.assertIs(kernel32.GlobalLock.restype, ctypes.c_void_p)

#!/usr/bin/env python3
"""PDF Editor Lite - trình xem và chỉnh sửa PDF gọn nhẹ. Chạy: python main.py [file.pdf ...]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _blocked_dll(e: BaseException) -> bool:
    """Windows (Smart App Control / chính sách của công ty) chặn thư viện chưa ký số của app."""
    while e is not None:
        t = str(e).lower()
        if "application control" in t or "4551" in t:    # 4551 = ERROR_SYSTEM_INTEGRITY_POLICY_VIOLATION
            return True
        e = e.__cause__ or e.__context__
    return False


def _show_error(msg: str) -> None:
    print(msg)
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "PDF Editor Lite", 0x10)
            return
        except Exception:
            pass
    try:
        import tkinter.messagebox as mb
        mb.showerror("PDF Editor Lite", msg)
    except Exception:
        pass


BLOCKED_MSG = ("Windows đang chặn không cho PDF Editor Lite nạp thư viện đọc PDF, nên app không mở được.\n\n"
               "Nguyên nhân: Smart App Control (hoặc chính sách bảo mật của công ty) chặn các file chương trình "
               "chưa có chữ ký số.\n\n"
               "Cách xử lý:\n"
               "1. Mở Windows Security → App & browser control → Smart App Control settings.\n"
               "2. Chọn Off, rồi mở lại PDF Editor Lite.\n\n"
               "Nếu đây là máy công ty, hãy nhờ bộ phận IT cho phép thư mục cài đặt của PDF Editor Lite.")


def main() -> int:
    try:
        from litepdf.launch import main as run
    except ImportError as e:
        if _blocked_dll(e):
            _show_error(BLOCKED_MSG)
            return 1
        msg = ("Thiếu thư viện: %s\nHãy chạy file cài đặt (PDFEditorLite.bat trên Windows, PDFEditorLite.sh trên Linux/macOS) "
               "hoặc: pip install -r requirements.txt" % e)
        _show_error(msg)
        return 1
    try:
        return run(sys.argv)
    except (ImportError, OSError) as e:
        if _blocked_dll(e):
            _show_error(BLOCKED_MSG)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())

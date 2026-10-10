#!/usr/bin/env python3
"""PDF Editor Lite - trình xem và chỉnh sửa PDF gọn nhẹ. Chạy: python main.py [file.pdf ...]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        from litepdf.app import run
    except ImportError as e:
        msg = ("Thiếu thư viện: %s\nHãy chạy file cài đặt (PDFEditorLite.bat trên Windows, PDFEditorLite.sh trên Linux/macOS) "
               "hoặc: pip install -r requirements.txt" % e)
        print(msg)
        try:
            import tkinter.messagebox as mb
            mb.showerror("PDF Editor Lite", msg)
        except Exception:
            pass
        return 1
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

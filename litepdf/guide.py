"""Bảng tình trạng các thành phần tuỳ chọn trên máy (hiện trong Trợ giúp → Giới thiệu)."""
from __future__ import annotations

import html


def status_rows(st: dict) -> str:
    def row(name, ok, yes, no):
        mark = "<span style='color:#188038'>●</span>" if ok else "<span style='color:#d93025'>○</span>"
        return f"<tr><td>{mark} <b>{name}</b></td><td>{html.escape(yes if ok else no)}</td></tr>"
    langs = st.get("tess") or []
    return "".join([
        row("Ảnh → PDF", True, "Sẵn sàng (có sẵn trong app).", ""),
        row("Word / Excel / PowerPoint → PDF", bool(st.get("office")), "Sẵn sàng (" + str(st.get("office")) + ").",
            "Chưa có LibreOffice hoặc Microsoft Office. " + st.get("add", "")),
        row("PDF → Word", st.get("pdf2docx"), "Sẵn sàng.", "Thiếu thư viện pdf2docx."),
        row("PDF → Excel", st.get("openpyxl"), "Sẵn sàng.", "Thiếu thư viện openpyxl."),
        row("PDF → Ảnh, Văn bản, HTML", True, "Sẵn sàng (có sẵn trong app).", ""),
        row("OCR Tesseract", bool(langs), "Sẵn sàng. Ngôn ngữ: " + ", ".join(langs), "Chưa có. " + st.get("add", "")),
        row("OCR RapidOCR", st.get("rapid"), "Sẵn sàng.", "Chưa có. " + st.get("add", "")),
        row("API key Gemini (dịch, OCR trên mạng)", st.get("gemini"), "Đã nhập.",
            "Chưa nhập. Mở Chuyển đổi → Dịch tài liệu để nhập key."),
        row("AI dịch chạy trên máy (Ollama / LM Studio)", bool(st.get("local")), "Đang chạy: " + str(st.get("local")),
            "Không thấy đang chạy. " + st.get("add_ai", "")),
        row("Ký bằng USB token", st.get("pkcs11"), "Thư viện sẵn sàng (vẫn cần driver của nhà cung cấp token).",
            "Thiếu thư viện python-pkcs11."),
    ])

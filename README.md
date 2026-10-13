# PDF Editor Lite

Trình xem và chỉnh sửa PDF gọn nhẹ, **miễn phí**, giao diện tiếng Việt, chạy trên **Windows, macOS và Linux Mint / Ubuntu / Debian**.
Thay thế được các chức năng thường dùng của Foxit / Acrobat: xem, sửa chữ gốc, ghi chú, sắp xếp trang, chuyển đổi, OCR, dịch tài liệu, so sánh hai tài liệu và ký số.

Tác giả: **ngthhung** · Phiên bản: **1.0.0**

## Tải về

Vào trang **[Releases](https://github.com/ngthhung-dev/pdf-editor-lite/releases/latest)** và chọn đúng file cho máy của bạn:

| Hệ điều hành | File cần tải |
|---|---|
| Windows 10/11 64-bit | `PDF-Editor-Lite-1.0.0-build…-Setup.exe` |
| macOS 12 trở lên, chip Apple (M1, M2, M3…) | `PDF-Editor-Lite-1.0.0-build…-macOS-AppleSilicon.pkg` |
| macOS 12 trở lên, chip Intel | `PDF-Editor-Lite-1.0.0-build…-macOS-Intel.pkg` |
| Linux Mint 21/22, Ubuntu 22.04+, Debian 64-bit | `pdf-editor-lite_1.0.0-build…_amd64.deb` |

Số sau chữ `build` là số bản: số càng lớn thì bản càng mới. Hướng dẫn sử dụng đầy đủ có hình minh hoạ: [`assets/Huong dan su dung PDF Editor Lite.pdf`](assets/Huong%20dan%20su%20dung%20PDF%20Editor%20Lite.pdf) (trong app bấm **F1**).

## Chức năng

**Xem và đọc**
- Mở nhiều file theo tab; nhấp đúp file PDF khác khi app đang mở sẽ thêm tab trong cùng cửa sổ.
- Thu phóng, vừa chiều rộng / vừa trang, toàn màn hình, thanh bên hình thu nhỏ trang và bookmark.
- Tìm chữ trong tài liệu (F3 / Shift+F3), sao chép chữ và hình ảnh.

**Chỉnh sửa**
- Sửa chữ gốc của PDF: sửa từng dòng hoặc quét chọn cả vùng; định dạng đậm, nghiêng, màu từng ký tự; chữ dài hơn tự xuống dòng và đẩy các dòng bên dưới xuống (trong bảng chỉ đẩy trong ô đó).
- Thêm chữ, chèn ảnh, xoá trắng một vùng, xoá / lưu hình ảnh trong trang.
- Ghi chú: tô sáng, gạch chân, gạch ngang, ghi chú dán, hình chữ nhật, elip, đường thẳng, mũi tên, vẽ tự do; làm phẳng ghi chú.
- Hoàn tác / làm lại nhiều bước, nhanh cả với file lớn.

**Trang và bookmark**
- Xoay, xoá, nhân đôi, sắp xếp trang (kéo thả), chèn trang trắng, chèn file khác.
- Đánh số trang, đóng dấu chìm (watermark).
- Tạo, sửa bookmark; tự tạo bookmark từ các tiêu đề hoặc cho từng trang.

**Tạo và chuyển đổi**
- Tạo PDF trắng; ảnh / Word / Excel / PowerPoint → PDF; ghép nhiều ảnh, gộp nhiều file thành một PDF; tách PDF.
- PDF → Word, Excel, ảnh (PNG/JPG), văn bản, HTML; xuất mọi hình ảnh trong PDF ra thư mục.
- Nén giảm dung lượng.

**Nhận dạng chữ (OCR)** cho bản scan và ảnh chụp: Tesseract (nhanh, cho bản scan sạch), RapidOCR (cho ảnh chụp, scan xấu), hoặc Gemini.

**Dịch tài liệu** sang ngôn ngữ khác, giữ nguyên bố cục, công thức toán / hoá học:
- Google Translate (miễn phí, không cần key), Gemini (cần API key, có gói miễn phí), hoặc AI theo chuẩn OpenAI (OpenAI, OpenRouter, Ollama chạy ngay trên máy).
- Rà soát, sửa câu dịch từng trang; xem song song bản gốc và bản dịch.

**So sánh hai tài liệu**: đặt hai file cạnh nhau, cuộn đồng bộ, tô sáng chữ khác nhau (trái đỏ, phải xanh), nhảy tới chỗ khác nhau trước / sau (Shift+F9 / F9) và sửa trực tiếp ở cả hai bên.

**Ký số và bảo mật**
- Ký số bằng USB token (PKCS#11) hoặc file chứng thư (.pfx/.p12), có hoặc không hiện khung chữ ký; kiểm tra chữ ký số.
- Chèn ảnh chữ ký tay / con dấu (thư viện chữ ký dùng lại được).
- Đặt và gỡ mật khẩu file.

Danh sách phím tắt đầy đủ: trong app bấm **Ctrl+F1**.

## Cài đặt

### Windows
1. Đóng PDF Editor Lite nếu đang mở, chạy file `…-Setup.exe`, bấm **Yes** khi Windows hỏi quyền.
2. Ở bước **Chọn thành phần**, tích phần muốn cài:

   | Thành phần | Ghi chú |
   |---|---|
   | PDF Editor Lite | Bắt buộc |
   | OCR Tesseract (tiếng Việt, tiếng Anh) | Kèm sẵn |
   | OCR RapidOCR | Kèm sẵn |
   | LibreOffice (Word / Excel / PowerPoint → PDF) | Kèm sẵn; bỏ tích nếu máy đã có Microsoft Office |
   | AI dịch chạy trên máy (Ollama + model) | Tải về khi cài (vài GB, cần RAM từ 8 GB) |

3. Đặt làm chương trình mở PDF mặc định: chuột phải file .pdf → **Open with → Choose another app** → PDF Editor Lite → **Always**. Khung Preview của Explorer vẫn xem trước được PDF.

**Khởi động nhanh** (tích ở bước cài, hoặc trong app: Tệp → Khởi động nhanh): app chạy sẵn ẩn khi đăng nhập máy, nhấp đúp file PDF là hiện ngay. Rất nên bật nếu máy cài nhiều phông chữ, vì lần mở đầu tiên sau khi bật máy sẽ chậm. Đóng cửa sổ thì app vẫn chạy nền (biểu tượng ở khay hệ thống); tắt hẳn bằng Tệp → Thoát.

Gỡ cài đặt: **Settings → Apps → Installed apps → PDF Editor Lite → Uninstall**.

### macOS
1. Chọn đúng file theo loại chip (menu Apple → **About This Mac**).
2. Bộ cài chưa có chữ ký Apple nên lần đầu macOS sẽ chặn: chuột phải file `.pkg` → **Open** → **Open**. Trên macOS 15 trở lên: mở file một lần, rồi vào **System Settings → Privacy & Security → Open Anyway**.
3. Ở bước **Installation Type** chọn thành phần: PDF Editor Lite (đã gồm Tesseract, RapidOCR, hướng dẫn), LibreOffice (kèm sẵn) và AI dịch trên máy (tải về khi cài, mặc định không tích).

Gỡ cài đặt: kéo PDF Editor Lite từ thư mục Applications vào Thùng rác. Trên macOS, phím **Ctrl** trong hướng dẫn tương ứng với **⌘ Command**.

### Linux Mint / Ubuntu / Debian
```bash
sudo apt install ./pdf-editor-lite_1.0.0-build…_amd64.deb
```
Hoặc nhấp đúp file `.deb` → **Install Package**. Gói đã kèm mọi thư viện, Tesseract, RapidOCR; LibreOffice được lấy từ kho phần mềm nếu máy chưa có.
AI dịch chạy trên máy: mở mục **PDF Editor Lite – Cài AI dịch trên máy** trong menu ứng dụng.

Gỡ cài đặt: `sudo apt remove pdf-editor-lite`.

### Những thứ phải tự cài / tự nhập
- Driver của USB token ký số (do nhà cung cấp chữ ký số phát hành).
- Chứng thư gốc tin cậy để kiểm tra chữ ký (Ký & Bảo mật → Mở thư mục chứng thư gốc tin cậy).
- API key Gemini nếu dùng Gemini (lấy miễn phí tại Google AI Studio).

## Dữ liệu và quyền riêng tư

- Cài đặt, API key, bộ nhớ dịch, ảnh chữ ký tay nằm trong thư mục dữ liệu của app: Windows `%APPDATA%\PDF Editor Lite`, macOS `~/Library/Application Support/PDF Editor Lite`, Linux `~/.config/PDF Editor Lite`. Cập nhật hay gỡ app không xoá thư mục này.
- API key được lưu ở dạng đọc được, không mã hoá. App không lưu mật khẩu file hay mã PIN của token.
- File có mật khẩu không bao giờ được ghi bản đã giải mã ra ổ đĩa.
- Khi dịch / OCR bằng Gemini hoặc Google Translate, nội dung trang được gửi tới Google. Với gói Gemini miễn phí, Google có thể dùng nội dung đó để cải thiện dịch vụ: không dùng cho tài liệu mật. Tài liệu mật nên dịch bằng AI chạy ngay trên máy (Ollama), OCR bằng Tesseract / RapidOCR.

## Chạy từ mã nguồn

Cần Python 3.10 trở lên.

```bash
pip install -r requirements.txt
pip install -r requirements-them.txt   # tuỳ chọn: PDF → Word, ký bằng USB token
python main.py [file.pdf ...]
```
Hoặc chạy `PDFEditorLite.bat` (Windows), `PDFEditorLite.sh` (Linux), `PDFEditorLite.command` (macOS): lần đầu tự tạo môi trường và cài thư viện.

## Tự build bộ cài

Mỗi lần đẩy mã lên nhánh `main`, GitHub Actions (`.github/workflows/build-windows.yml`) tự build cả 4 bộ cài, cài thử, chạy tự kiểm tra rồi phát hành vào mục Releases với cùng một số build.

Dọn bản cũ: vào **Actions → Dọn Release cũ → Run workflow**. Mỗi lần chạy sẽ xoá Release cũ, tag cũ, toàn bộ Artifacts và lịch sử các lần chạy trước, chỉ giữ Release mới nhất.

Build trên máy riêng (xem thêm [`packaging/HUONG_DAN_BUILD.txt`](packaging/HUONG_DAN_BUILD.txt)):

| Hệ điều hành | Lệnh | Kết quả |
|---|---|---|
| Windows (cần Inno Setup 6) | `packaging\windows\BUILD_WINDOWS.bat` | `build_win\output\*.exe` |
| macOS (cần Xcode Command Line Tools) | `bash packaging/macos/build_macos.sh` | `build_mac/output/*.pkg` |
| Linux (nên dùng Ubuntu 22.04) | `bash packaging/linux/build_linux.sh` | `build_linux/output/*.deb` |

## Thư viện sử dụng và giấy phép

[PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0), [PySide6 / Qt](https://www.qt.io/qt-for-python) (LGPL-3.0), [pyHanko](https://github.com/MatthiasValvekens/pyHanko) (MIT), [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) (AGPL-3.0), [openpyxl](https://openpyxl.readthedocs.io/) (MIT), [RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache-2.0), [Tesseract](https://github.com/tesseract-ocr/tesseract) dữ liệu ngôn ngữ (Apache-2.0), [LibreOffice](https://www.libreoffice.org/) (MPL-2.0), [Ollama](https://ollama.com/) (MIT).

Vì dùng PyMuPDF (AGPL), khi phát hành lại app cho người khác cần công bố kèm mã nguồn.

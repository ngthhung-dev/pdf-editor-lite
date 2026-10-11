"""Hướng dẫn sử dụng hiển thị trong app (Trợ giúp → Hướng dẫn sử dụng)."""
from __future__ import annotations

import html

SECTIONS = [
    ("batdau", "Bắt đầu nhanh"),
    ("xem", "Xem và tìm kiếm"),
    ("sua", "Sửa nội dung, ghi chú"),
    ("trang", "Sắp xếp trang"),
    ("bookmark", "Bookmark"),
    ("tao", "Tạo, ghép, tách PDF"),
    ("chuyendoi", "Chuyển đổi và nén"),
    ("ocr", "Nhận dạng chữ (OCR)"),
    ("dich", "Dịch tài liệu"),
    ("kyso", "Ký số và bảo mật"),
    ("in", "In"),
    ("dulieu", "Dữ liệu và quyền riêng tư"),
    ("suco", "Xử lý sự cố"),
]

BODY = """
<h2 id="batdau">Bắt đầu nhanh</h2>
<ul>
<li>Mở file: <b>Tệp → Mở</b> (Ctrl+O), hoặc kéo thả file PDF, ảnh, Word, Excel, PowerPoint vào cửa sổ.</li>
<li>Mỗi file mở trong một tab. Tab có dấu ● là đang có thay đổi chưa lưu; bấm <b>Ctrl+S</b> để lưu.</li>
<li>Mọi thao tác sửa đều hoàn tác được bằng <b>Ctrl+Z</b> (làm lại: Ctrl+Y).</li>
<li>Rê chuột vào nút trên thanh công cụ để xem tên và phím tắt. Xem toàn bộ phím tắt: <b>Trợ giúp → Danh sách phím tắt</b>.</li>
<li>Mục nào trong menu bị mờ là chưa dùng được với tài liệu hiện tại.</li>
</ul>

<h2 id="xem">Xem và tìm kiếm</h2>
<ul>
<li>Lăn chuột để cuộn trang; giữ <b>Ctrl + lăn chuột</b> để thu phóng. Ctrl+0: 100%, Ctrl+1: vừa chiều rộng, Ctrl+2: vừa cả trang.</li>
<li><b>F4</b> ẩn/hiện thanh bên. Thanh bên có hai tab: <b>Trang</b> (ảnh thu nhỏ) và <b>Bookmark</b>. Kéo thanh chia để đổi độ rộng, nhấp đúp vào thanh chia để về mặc định.</li>
<li>Tìm chữ: gõ vào ô tìm ở góc phải thanh công cụ (Ctrl+F), F3 tìm tiếp, Shift+F3 tìm ngược.</li>
<li><b>Tệp → Thông tin tài liệu</b> (Ctrl+D): số trang, khổ giấy, phông chữ, bảo mật, chữ ký…</li>
<li>So sánh hai tài liệu cạnh nhau: <b>Xem → So sánh song song</b> (F6); F7 bật/tắt cuộn đồng bộ. Bấm vào bên nào thì các công cụ sửa, lưu, hoàn tác áp dụng cho bên đó.</li>
</ul>

<h2 id="sua">Sửa nội dung, ghi chú</h2>
<p>Chọn công cụ trên thanh công cụ thứ hai hoặc trong menu <b>Công cụ</b> (mỗi công cụ có một phím tắt một chữ cái):</p>
<table>
<tr><td><b>Bàn tay</b> (H)</td><td>Di chuyển trang; bấm vào ghi chú, hình vẽ để chọn, kéo để dời, Delete để xoá.</td></tr>
<tr><td><b>Chọn chữ / hình ảnh</b> (V)</td><td>Bôi chọn chữ để sao chép (Ctrl+C) hoặc bấm chuột phải để tô sáng; bấm vào hình ảnh để sao chép, lưu ra file hoặc xoá.</td></tr>
<tr><td><b>Sửa chữ gốc</b> (E)</td><td>Bấm vào một dòng chữ có sẵn để sửa nội dung, hoặc kéo để dời. Chỉ dùng được với PDF có lớp chữ thật, không dùng được với bản scan.</td></tr>
<tr><td><b>Thêm chữ</b> (T), <b>Chèn ảnh</b> (I)</td><td>Bấm vào vị trí muốn đặt.</td></tr>
<tr><td><b>Xoá trắng một vùng</b> (X)</td><td>Kéo khung quanh vùng cần xoá. Nội dung trong vùng bị gỡ hẳn khỏi trang.</td></tr>
<tr><td><b>Tô sáng, gạch chân, gạch ngang</b> (M, U, K)</td><td>Kéo qua dòng chữ.</td></tr>
<tr><td><b>Ghi chú dán</b> (N)</td><td>Bấm vào trang rồi nhập nội dung. Rê chuột vào ghi chú để đọc, bấm đúp để sửa.</td></tr>
<tr><td><b>Hình, đường, mũi tên, vẽ tự do</b> (R, O, L, A, P)</td><td>Kéo để vẽ; đổi màu và độ dày nét ở ô Màu, Nét.</td></tr>
</table>
<p><b>Sửa → Làm phẳng ghi chú</b> gắn chết các ghi chú, hình vẽ vào trang để người nhận không sửa được.</p>

<h2 id="trang">Sắp xếp trang</h2>
<ul>
<li>Ở tab <b>Trang</b> của thanh bên: kéo thả ảnh thu nhỏ để đổi thứ tự; giữ Ctrl hoặc Shift để chọn nhiều trang; bấm chuột phải để mở menu trang.</li>
<li>Menu <b>Trang</b>: xoay, xoá, nhân đôi, chuyển lên/xuống, chèn trang trắng, chèn file khác vào sau trang đang xem.</li>
<li><b>Đánh số trang</b> và <b>Đóng dấu chìm (watermark)</b> áp dụng cho cả tài liệu hoặc các trang chỉ định.</li>
</ul>

<h2 id="bookmark">Bookmark</h2>
<ul>
<li>Mở tab <b>Bookmark</b> ở thanh bên. Bấm vào một mục để tới đúng vị trí; khi cuộn trang, mục tương ứng tự được tô sáng.</li>
<li>Hàng biểu tượng: thêm bookmark tại chỗ đang xem (Ctrl+B), thêm mục con, đổi tên, xoá. Kéo thả để sắp xếp và đổi cấp.</li>
<li>Nút tuỳ chọn (☰): <b>Tự tạo bookmark từ các tiêu đề</b> (nhiều cấp, lấy từ trang mục lục in sẵn hoặc cỡ chữ tiêu đề), tạo bookmark cho từng trang, mở rộng/thu gọn tất cả, xuống dòng với tên dài, xoá tất cả.</li>
<li>Bấm chuột phải vào một bookmark để đặt lại đích của nó về vị trí đang xem.</li>
</ul>

<h2 id="tao">Tạo, ghép, tách PDF</h2>
<ul>
<li><b>Tệp → Ảnh / Word / Excel / PowerPoint → PDF</b>: tạo PDF từ file khác. File Office cần LibreOffice hoặc Microsoft Office trên máy.</li>
<li><b>Tệp → Ghép nhiều ảnh thành một PDF</b>: chọn khổ giấy, hướng giấy, lề, cách đặt ảnh; có khung xem trước.</li>
<li><b>Tệp → Gộp nhiều file thành một PDF</b>: chọn file và khoảng trang của từng file, có thể đưa tất cả về cùng khổ A4. Bấm <b>Tạo PDF</b>, kết quả mở ở tab mới và chưa lưu.</li>
<li><b>Chuyển đổi → Tách file PDF</b>: tách theo khoảng trang, cắt tại các trang, chia đều, theo bookmark, hoặc rời từng trang.
Trong ô khoảng trang, dấu phẩy tách thành nhiều file (<code>1-3, 4-10</code>), dấu cộng nối các trang rời vào một file (<code>1-3+7</code>).
Nếu đã chọn sẵn nhiều trang ở tab Trang, hộp thoại tự điền để trích các trang đó ra một file.</li>
</ul>

<h2 id="chuyendoi">Chuyển đổi và nén</h2>
<ul>
<li>Menu <b>Chuyển đổi</b>: PDF → Word, Excel, ảnh (PNG/JPG), văn bản, HTML; xuất mọi hình ảnh trong PDF ra thư mục.</li>
<li>PDF → Word/Excel cho kết quả tốt với tài liệu chữ thông thường; bố cục phức tạp có thể lệch. Bản scan cần chạy OCR trước.</li>
<li><b>Nén giảm dung lượng</b>: chọn mức nén; mức cao giảm độ phân giải ảnh.</li>
</ul>

<h2 id="ocr">Nhận dạng chữ (OCR)</h2>
<p><b>Chuyển đổi → Nhận dạng chữ (OCR)</b> thêm lớp chữ ẩn vào bản scan để tìm kiếm, bôi chọn và sao chép được. Có ba bộ máy:</p>
<table>
<tr><td><b>Tesseract</b></td><td>Chạy trên máy, nhẹ, hợp với bản scan sạch. Trang được đổi thành ảnh kèm lớp chữ.</td></tr>
<tr><td><b>RapidOCR</b></td><td>Chạy trên máy, tốt hơn với ảnh chụp và bản scan xấu, chậm hơn. Lớp chữ đặt lên trang gốc nên hình giữ nguyên độ nét.</td></tr>
<tr><td><b>Gemini</b></td><td>Chạy trên mạng bằng API key Gemini, thường chính xác nhất với tài liệu khó. Ảnh trang được gửi lên Google: không dùng cho tài liệu mật.</td></tr>
</table>
<p>Ô <b>Chỉ nhận dạng các trang chưa có chữ</b> giữ nguyên những trang đã chọn được chữ. Kết quả OCR có thể sai, nhất là con số và tên riêng: nên rà lại chỗ quan trọng.</p>

<h2 id="dich">Dịch tài liệu</h2>
<p><b>Chuyển đổi → Dịch tài liệu sang ngôn ngữ khác</b> (Ctrl+Alt+L). Bản dịch mở ở tab mới, file gốc giữ nguyên; bố cục, hình ảnh, header/footer, chữ đậm, gạch dưới và liên kết được giữ.</p>
<ul>
<li><b>Bộ máy dịch:</b> Gemini của Google (chất lượng cao, có gói miễn phí, cần API key), Google Translate (không cần key, chất lượng thông thường), hoặc AI khác theo chuẩn OpenAI, kể cả AI chạy ngay trên máy như Ollama.</li>
<li><b>API key Gemini:</b> bấm <b>Lấy key…</b> để mở trang của Google, tạo key, dán vào rồi bấm <b>Kiểm tra</b>. Gói miễn phí giới hạn số lượt gọi mỗi phút nên tài liệu dài sẽ có lúc phải chờ; ô <b>Ưu tiên tốc độ</b> cho dùng tạm model khác thay vì chờ.</li>
<li><b>Lĩnh vực chuyên ngành</b> và <b>Bảng thuật ngữ</b> (mỗi dòng: <code>từ gốc = từ dịch</code>) giúp dịch đúng thuật ngữ.</li>
<li><b>Trang cần dịch:</b> để trống là cả tài liệu; nhập <code>1-3, 5</code> để chỉ dịch các trang đó.</li>
<li><b>Dịch cả chữ nằm trong hình ảnh:</b> dùng cho ảnh chụp màn hình, sơ đồ và trang scan. App đọc chữ trong hình, dịch rồi viết đè lên. Công thức, ký hiệu toán và hoá được giữ nguyên. Chậm hơn và tốn thêm lượt gọi nên mặc định tắt.</li>
<li><b>Bộ nhớ dịch:</b> câu đã dịch được lưu trên máy; dịch lại cùng tài liệu sẽ lấy lại ngay, chỉ câu mới mới gọi máy dịch. Bỏ tích để dịch lại từ đầu.</li>
<li><b>Rà soát:</b> sau khi dịch, bấm <b>So sánh song song gốc – dịch</b> để xem hai bản cạnh nhau. <b>Chuyển đổi → Rà soát / sửa câu dịch của trang này</b> (Ctrl+Alt+G) mở bảng câu gốc – câu dịch để sửa; trang được dựng lại đúng bố cục và câu đã sửa được nhớ cho lần sau.</li>
</ul>
<p>Máy dịch có thể sai thuật ngữ hoặc ngữ cảnh: hợp đồng và văn bản pháp lý nên có người rà lại.</p>

<h2 id="kyso">Ký số và bảo mật</h2>
<ul>
<li><b>Ký số:</b> <b>Ký &amp; Bảo mật → Ký số</b>, kéo khung tại vị trí muốn hiện chữ ký, rồi chọn chứng thư: file <b>.pfx/.p12</b> hoặc <b>USB token</b>. App không lưu mật khẩu hay mã PIN.</li>
<li><b>USB token</b> cần cài driver của nhà cung cấp (VNPT, Viettel, FPT, BKAV…) trước. Ký từ xa (SmartCA, MySign) chưa được hỗ trợ.</li>
<li><b>Kiểm tra chữ ký số:</b> cho biết tài liệu có bị sửa sau khi ký không và chứng thư có được tin cậy không. Để chứng thư được coi là tin cậy, chép chứng thư gốc của nhà cung cấp vào thư mục mở bằng <b>Mở thư mục chứng thư gốc tin cậy</b>.</li>
<li><b>Chèn ảnh chữ ký tay / con dấu:</b> vẽ hoặc chọn ảnh chữ ký rồi đặt lên trang. Đây chỉ là hình ảnh, không có giá trị như chữ ký số.</li>
<li><b>Đặt / Gỡ mật khẩu</b> cho file. Sửa và lưu một file đã ký số sẽ làm chữ ký cũ mất hiệu lực; app sẽ hỏi lại trước khi lưu.</li>
</ul>

<h2 id="in">In</h2>
<p><b>Tệp → In</b> (Ctrl+P): chọn máy in, khoảng trang, số bản, in hai mặt, nhiều trang trên một tờ, co giãn cho vừa giấy, và in dạng sách nhỏ (booklet). Khung bên phải xem trước đúng kết quả sẽ in.</p>

<h2 id="dulieu">Dữ liệu và quyền riêng tư</h2>
<ul>
<li>Thư mục dữ liệu của app trên máy này: <code>{data_dir}</code>. Trong đó có cài đặt, API key, bộ nhớ dịch, ảnh chữ ký tay và chứng thư tin cậy. Cập nhật hoặc gỡ app không xoá thư mục này.</li>
<li>API key và bộ nhớ dịch được lưu ở dạng đọc được, không mã hoá. Không dùng chung máy nếu tài liệu nhạy cảm.</li>
<li>Khi dịch hoặc OCR bằng Gemini hay Google Translate, nội dung trang được gửi lên máy chủ của Google. Ở gói miễn phí của Gemini, Google có thể dùng nội dung để cải thiện sản phẩm. Với tài liệu mật, hãy dùng các bộ máy chạy trên máy (Tesseract, RapidOCR, Ollama).</li>
</ul>

<h2 id="suco">Xử lý sự cố</h2>
<table>
<tr><td><b>Không lưu được file vào Documents / Desktop</b></td><td>Windows Security đang bảo vệ thư mục (Controlled folder access). Lưu vào thư mục khác, hoặc vào Windows Security → Ransomware protection → Allow an app through Controlled folder access và thêm PDF Editor Lite.</td></tr>
<tr><td><b>Không bôi chọn hay sửa được chữ</b></td><td>File là bản scan (trang là ảnh). Chạy OCR để có lớp chữ.</td></tr>
<tr><td><b>Dịch báo “Hết lượt gọi miễn phí trong phút này”</b></td><td>Giới hạn của gói Gemini miễn phí. App tự chờ rồi dịch tiếp; có thể tích “Ưu tiên tốc độ” hoặc dịch ít trang một lần.</td></tr>
<tr><td><b>Dịch báo không tìm thấy chữ</b></td><td>Trang là ảnh: tích “Dịch cả chữ nằm trong hình ảnh”.</td></tr>
<tr><td><b>Không chuyển được Word/Excel/PowerPoint sang PDF</b></td><td>Máy chưa có LibreOffice hoặc Microsoft Office. {office_fix}</td></tr>
<tr><td><b>Không ký được bằng USB token</b></td><td>Cài driver của nhà cung cấp token và cắm token trước khi mở hộp ký.</td></tr>
<tr><td><b>Muốn PDF Editor Lite mở file .pdf mặc định</b></td><td>Bấm chuột phải vào một file .pdf → Open with → Choose another app → PDF Editor Lite → Always.</td></tr>
</table>
"""


def status_rows(st: dict) -> str:
    def row(name, ok, yes, no):
        mark = "<span style='color:#188038'>●</span>" if ok else "<span style='color:#d93025'>○</span>"
        return f"<tr><td>{mark} <b>{name}</b></td><td>{html.escape(yes if ok else no)}</td></tr>"
    langs = st.get("tess") or []
    return "".join([
        row("OCR Tesseract", bool(langs), "Sẵn sàng. Ngôn ngữ: " + ", ".join(langs), "Chưa có. " + st.get("add", "")),
        row("OCR RapidOCR", st.get("rapid"), "Sẵn sàng.", "Chưa có. " + st.get("add", "")),
        row("Chuyển Word/Excel/PowerPoint → PDF", bool(st.get("office")), "Sẵn sàng (" + str(st.get("office")) + ").",
            "Chưa có LibreOffice hoặc Microsoft Office. " + st.get("add", "")),
        row("API key Gemini (dịch, OCR trên mạng)", st.get("gemini"), "Đã nhập.",
            "Chưa nhập. Mở Chuyển đổi → Dịch tài liệu để nhập key."),
        row("AI dịch chạy trên máy (Ollama / LM Studio)", bool(st.get("local")), "Đang chạy: " + str(st.get("local")),
            "Không thấy đang chạy. " + st.get("add_ai", "")),
        row("PDF → Word", st.get("pdf2docx"), "Sẵn sàng.", "Thiếu thư viện pdf2docx."),
        row("Ký bằng USB token", st.get("pkcs11"), "Thư viện sẵn sàng (vẫn cần driver của nhà cung cấp token).",
            "Thiếu thư viện python-pkcs11."),
    ])


def guide_html(app_name: str, version: str, st: dict) -> str:
    frozen = st.get("frozen")
    office_fix = "Chạy lại bộ cài PDF Editor Lite và tích thành phần LibreOffice." if frozen else \
        "Cài LibreOffice (miễn phí) rồi mở lại app."
    toc = " · ".join(f"<a href='#{k}'>{t}</a>" for k, t in [("tinhtrang", "Tình trạng trên máy này")] + SECTIONS)
    body = BODY.replace("{data_dir}", html.escape(st.get("data_dir", ""))).replace("{office_fix}", office_fix)
    return (
        "<style>h1{font-size:19px;margin:4px 0 2px 0} h2{font-size:15px;margin:18px 0 4px 0;color:#1a56c4}"
        " p,li,td{font-size:13px;line-height:150%} table{margin:4px 0} td{padding:3px 12px 3px 0;vertical-align:top}"
        " code{background:#eef1f5} a{color:#1a56c4;text-decoration:none}</style>"
        f"<h1>Hướng dẫn sử dụng {html.escape(app_name)}</h1>"
        f"<p style='color:#5f6368'>Phiên bản {html.escape(version)} · "
        f"{'bản cài đặt' if frozen else 'bản portable (chạy từ mã nguồn)'}</p>"
        f"<p>{toc}</p>"
        "<h2 id='tinhtrang'>Tình trạng trên máy này</h2>"
        "<p>Các thành phần tuỳ chọn mà app tìm thấy lúc mở hướng dẫn này:</p>"
        f"<table>{status_rows(st)}</table>" + body)

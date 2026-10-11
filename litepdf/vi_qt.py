"""Tiếng Việt cho các chữ do chính Qt hiển thị (nút OK/Cancel/Yes/No, menu chuột phải của ô nhập, hộp chọn file/màu/in
không dùng hộp thoại của hệ điều hành). Qt không kèm bản dịch tiếng Việt nên app tự mang theo bảng này."""
from PySide6.QtCore import QTranslator

VI = {
    # nút chuẩn
    "OK": "Đồng ý", "&OK": "Đồ&ng ý", "Cancel": "Hủy", "&Cancel": "&Hủy", "&Yes": "&Có", "&No": "&Không", "Yes": "Có", "No": "Không",
    "Yes to &All": "Có &tất cả", "N&o to All": "Khô&ng tất cả", "Save": "Lưu", "&Save": "&Lưu", "Save All": "Lưu tất cả",
    "Open": "Mở", "&Open": "&Mở", "Close": "Đóng", "&Close": "Đón&g", "Apply": "Áp dụng", "Reset": "Đặt lại",
    "Restore Defaults": "Về mặc định", "Help": "Trợ giúp", "Discard": "Bỏ thay đổi", "Don't Save": "Không lưu",
    "Close without Saving": "Đóng không lưu", "Abort": "Hủy bỏ", "Retry": "Thử lại", "Ignore": "Bỏ qua",
    "Show Details...": "Xem chi tiết…", "Hide Details...": "Ẩn chi tiết…",
    # menu chuột phải của ô nhập chữ
    "&Undo": "&Hoàn tác", "&Redo": "&Làm lại", "Cu&t": "&Cắt", "&Copy": "&Sao chép", "&Paste": "&Dán", "Delete": "Xóa",
    "Select All": "Chọn tất cả", "&Select All": "Chọn &tất cả", "Copy &Link Location": "Sao chép địa chỉ &liên kết",
    "&Step up": "&Tăng", "Step &down": "&Giảm",
    # thanh cuộn, thanh tab
    "Scroll here": "Cuộn tới đây", "Left edge": "Mép trái", "Top": "Đầu", "Right edge": "Mép phải", "Bottom": "Cuối",
    "Page left": "Sang trái một trang", "Page up": "Lên một trang", "Page right": "Sang phải một trang",
    "Page down": "Xuống một trang", "Scroll left": "Cuộn sang trái", "Scroll up": "Cuộn lên", "Scroll right": "Cuộn sang phải",
    "Scroll down": "Cuộn xuống", "Scroll Left": "Cuộn sang trái", "Scroll Right": "Cuộn sang phải",
    # hộp chọn file
    "&Delete": "&Xóa", "&Look in:": "&Tìm trong:", "Look in:": "Tìm trong:", "&New Folder": "Thư mục &mới",
    "&Rename": "Đổi &tên", "All Files (*)": "Tất cả các file (*)", "Back": "Lùi", "Forward": "Tiến",
    "Change to detail view mode": "Xem dạng chi tiết", "Change to list view mode": "Xem dạng danh sách",
    "Create New Folder": "Tạo thư mục mới", "Create a New Folder": "Tạo thư mục mới", "New Folder": "Thư mục mới",
    "Detail View": "Xem chi tiết", "List View": "Xem danh sách", "File &name:": "&Tên file:", "Files": "File",
    "Files of &type:": "&Loại file:", "Files of type:": "Loại file:", "Go back": "Lùi lại", "Go forward": "Tiến tới",
    "Go to the parent directory": "Lên thư mục cha", "Parent Directory": "Thư mục cha",
    "List of places and bookmarks": "Danh sách nơi lưu", "Show ": "Hiện ", "Show &hidden files": "Hiện file ẩ&n",
    "Sidebar": "Thanh bên", "Computer": "Máy tính", "My Computer": "Máy tính", "Date Modified": "Ngày sửa", "Name": "Tên",
    "Size": "Dung lượng", "Type": "Loại", "Kind": "Loại", "Drive": "Ổ đĩa", "Folder": "Thư mục", "File": "File",
    "Save As": "Lưu thành", "&Choose": "&Chọn", "Directory:": "Thư mục:", "Directories": "Thư mục", "Remove": "Gỡ",
    "Recent Places": "Nơi mở gần đây", "Find Directory": "Tìm thư mục", "Show": "Hiện", "Unknown": "Không rõ",
    "%1 already exists.\nDo you want to replace it?": "%1 đã có sẵn.\nGhi đè lên file này?",
    "%1\nFile not found.\nPlease verify the correct file name was given.":
        "%1\nKhông tìm thấy file.\nHãy kiểm tra lại tên file.",
    "%1\nDirectory not found.\nPlease verify the correct directory name was given.":
        "%1\nKhông tìm thấy thư mục.\nHãy kiểm tra lại tên thư mục.",
    "Are you sure you want to delete '%1'?": "Xóa '%1'?", "Could not delete directory.": "Không xóa được thư mục.",
    "Invalid filename": "Tên file không hợp lệ", "The name \"%1\" cannot be used.": "Không dùng được tên \"%1\".",
    # hộp chọn màu
    "&Add to Custom Colors": "&Thêm vào màu tự chọn", "&Basic colors": "Màu &cơ bản", "&Custom colors": "Màu tự c&họn",
    "&Red:": "Đỏ (&R):", "&Green:": "Lục (&G):", "Bl&ue:": "Lam (&B):", "Hu&e:": "Sắc (&H):", "&Sat:": "Độ đậm (&S):",
    "&Val:": "Độ sáng (&V):", "A&lpha channel:": "Độ tr&ong:", "&HTML:": "Mã &HTML:", "&Pick Screen Color": "&Lấy màu trên màn hình",
    "Select Color": "Chọn màu", "Cursor at %1, %2\nPress ESC to cancel": "Con trỏ ở %1, %2\nNhấn ESC để hủy",
    "Enter a value:": "Nhập giá trị:",
    # hộp in và xem trước khi in
    "&Options >>": "Tù&y chọn >>", "&Options <<": "Tù&y chọn <<", "&Print": "&In", "Print": "In", "All Pages": "Tất cả các trang",
    "Even Pages": "Trang chẵn", "Odd Pages": "Trang lẻ", "Local file": "File trên máy", "Print to File (PDF)": "In ra file (PDF)",
    "Write PDF file": "Ghi file PDF", "Print To File ...": "In ra file…", "First page": "Trang đầu", "Last page": "Trang cuối",
    "Next page": "Trang sau", "Previous page": "Trang trước", "Fit page": "Vừa trang", "Fit width": "Vừa chiều rộng",
    "Landscape": "Ngang", "Portrait": "Dọc", "Page setup": "Thiết lập trang", "Page Setup": "Thiết lập trang",
    "Print Preview": "Xem trước khi in", "Show facing pages": "Hiện hai trang đối nhau",
    "Show overview of all pages": "Hiện tổng quan mọi trang", "Show single page": "Hiện từng trang", "Zoom in": "Phóng to",
    "Zoom out": "Thu nhỏ", "Export to PDF": "Xuất ra PDF", "Collate": "Xếp theo bộ", "Color": "Màu", "Color Mode": "Chế độ màu",
    "Copies": "Số bản", "Copies:": "Số bản:", "Current Page": "Trang hiện tại", "Double Sided Printing": "In hai mặt",
    "Grayscale": "Đen trắng", "Long side binding": "Lật theo cạnh dài", "Short side binding": "Lật theo cạnh ngắn",
    "Off": "Tắt", "Options": "Tùy chọn", "Output Settings": "Thiết lập đầu ra", "Page &Set:": "&Nhóm trang:", "Pages": "Trang",
    "Pages from": "Từ trang", "to": "đến", "Print all": "In tất cả", "Print range": "Phạm vi in", "Reverse": "In ngược thứ tự",
    "Selection": "Vùng chọn",
    "Specify pages or ranges separated by commas. Ranges are specified by two numbers separated by a hyphen. "
    "E.g: 3,5-7,9 prints pages 3, 5, 6, 7 and 9.":
        "Ghi các trang hoặc khoảng trang, cách nhau bằng dấu phẩy. Khoảng trang là hai số nối bằng dấu gạch. "
        "Ví dụ: 3,5-7,9 sẽ in các trang 3, 5, 6, 7 và 9.",
    "&Name:": "&Tên:", "Location:": "Vị trí:", "Output &file:": "&File xuất ra:", "P&roperties": "Thuộc tín&h",
    "Preview": "Xem trước", "Printer": "Máy in", "Type:": "Loại:", "Paper": "Giấy", "Page size:": "Khổ giấy:",
    "Width:": "Rộng:", "Height:": "Cao:", "Paper source:": "Khay giấy:", "Orientation": "Hướng giấy", "Margins": "Lề",
    "Reverse landscape": "Ngang ngược", "Reverse portrait": "Dọc ngược", "Custom": "Tự chọn",
}

SKIP = {"QShortcut", "QPageSize"}       # tên phím (Ctrl, Shift…) và tên khổ giấy: giữ nguyên


class ViTranslator(QTranslator):
    def translate(self, context, source, disambiguation=None, n=-1):
        if context in SKIP or not (context or "").startswith("Q"):
            return ""
        return VI.get(source, "")

    def isEmpty(self):
        return False


def install(app):
    t = ViTranslator(app)
    app.installTranslator(t)
    app._vi_translator = t
    return t

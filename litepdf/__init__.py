
import sys as _sys
if getattr(_sys, "frozen", False) and _sys.platform == "darwin":
    # Trong gói .app, mã Python của OpenCV nằm ở Resources còn sys.path[0] là Frameworks: báo bộ nạp của cv2 đặt
    # thư mục chứa phần nhị phân lên đầu sys.path, nếu không nó nạp lại chính nó ("recursion is detected").
    _sys.OpenCV_REPLACE_SYS_PATH_0 = True

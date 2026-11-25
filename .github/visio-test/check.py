"""Thử tạm (không đưa vào main): tạo file .vsdx mẫu, chuyển bằng litepdf.tools rồi xuất ảnh."""
import os
import sys
import zipfile

sys.path.insert(0, os.getcwd())
import pymupdf  # noqa: E402
from litepdf import tools  # noqa: E402

OUT = "visio-out"
os.makedirs(OUT, exist_ok=True)
NS = ('xmlns="http://schemas.microsoft.com/office/visio/2012/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')


def rect(i, x, y, w, h, fill, text):
    return f'''<Shape ID="{i}" Type="Shape">
<Cell N="PinX" V="{x}"/><Cell N="PinY" V="{y}"/><Cell N="Width" V="{w}"/><Cell N="Height" V="{h}"/>
<Cell N="LocPinX" V="{w / 2}"/><Cell N="LocPinY" V="{h / 2}"/>
<Cell N="FillForegnd" V="{fill}"/><Cell N="FillPattern" V="1"/><Cell N="LineColor" V="#1F4E79"/>
<Cell N="LineWeight" V="0.02"/><Cell N="LinePattern" V="1"/><Cell N="Char.Size" V="0.2"/>
<Section N="Character"><Row IX="0"><Cell N="Size" V="0.2"/><Cell N="Color" V="#000000"/></Row></Section>
<Section N="Geometry" IX="0"><Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/>
<Row T="RelMoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
<Row T="RelLineTo" IX="2"><Cell N="X" V="1"/><Cell N="Y" V="0"/></Row>
<Row T="RelLineTo" IX="3"><Cell N="X" V="1"/><Cell N="Y" V="1"/></Row>
<Row T="RelLineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="1"/></Row>
<Row T="RelLineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row></Section>
<Text>{text}</Text></Shape>'''


def line(i, x1, y1, x2, y2):
    w = x2 - x1
    return f'''<Shape ID="{i}" Type="Shape">
<Cell N="PinX" V="{(x1 + x2) / 2}"/><Cell N="PinY" V="{y1}"/><Cell N="Width" V="{w}"/><Cell N="Height" V="0"/>
<Cell N="LocPinX" V="{w / 2}"/><Cell N="LocPinY" V="0"/><Cell N="LineColor" V="#C00000"/>
<Cell N="LineWeight" V="0.03"/><Cell N="LinePattern" V="1"/><Cell N="EndArrow" V="4"/>
<Section N="Geometry" IX="0"><Cell N="NoFill" V="1"/><Cell N="NoLine" V="0"/>
<Row T="MoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
<Row T="LineTo" IX="2"><Cell N="X" V="{w}"/><Cell N="Y" V="0"/></Row></Section></Shape>'''


pages = {
    1: rect(1, 2, 6, 2.5, 1, "#BDD7EE", "Máy chủ ERP") + rect(2, 7, 6, 2.5, 1, "#C6E0B4", "Tường lửa")
       + line(3, 3.25, 6, 5.75, 6) + rect(4, 4.5, 2.5, 4, 1.2, "#FFE699", "Sơ đồ mạng Hà Nội – Đà Nẵng"),
    2: rect(1, 5.5, 4.25, 6, 3, "#F8CBAD", "Trang 2: Kho dữ liệu"),
}
files = {
    "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>'
    '<Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>'
    + "".join(f'<Override PartName="/visio/pages/page{n}.xml" ContentType="application/vnd.ms-visio.page+xml"/>' for n in pages)
    + "</Types>",
    "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/></Relationships>',
    "visio/document.xml": f'<?xml version="1.0" encoding="UTF-8"?><VisioDocument {NS}><DocumentSettings/><Colors/><FaceNames/>'
    '<StyleSheets><StyleSheet ID="0" NameU="No Style" Name="No Style"><Cell N="LineWeight" V="0.01"/><Cell N="LineColor" V="0"/>'
    '<Cell N="LinePattern" V="1"/><Cell N="FillForegnd" V="1"/><Cell N="FillPattern" V="1"/></StyleSheet></StyleSheets></VisioDocument>',
    "visio/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/></Relationships>',
    "visio/pages/pages.xml": f'<?xml version="1.0" encoding="UTF-8"?><Pages {NS}>'
    + "".join(f'<Page ID="{n - 1}" NameU="Page-{n}" Name="Trang {n}"><PageSheet><Cell N="PageWidth" V="11"/>'
              f'<Cell N="PageHeight" V="8.5"/><Cell N="PageScale" V="1" U="IN"/><Cell N="DrawingScale" V="1" U="IN"/></PageSheet>'
              f'<Rel r:id="rId{n}"/></Page>' for n in pages) + "</Pages>",
    "visio/pages/_rels/pages.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + "".join(f'<Relationship Id="rId{n}" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page{n}.xml"/>' for n in pages)
    + "</Relationships>",
}
for n, body in pages.items():
    files[f"visio/pages/page{n}.xml"] = f'<?xml version="1.0" encoding="UTF-8"?><PageContents {NS}><Shapes>{body}</Shapes></PageContents>'
src = os.path.join(OUT, "so-do-mau.vsdx")
with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)

print("soffice:", tools.find_soffice(), "| engine:", tools.visio_engine())
# bộ lọc JSON (chất lượng cao) phải chạy được, không rơi xuống kiểu mặc định
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    res, err = tools._soffice_convert(tools.find_soffice(), os.path.abspath(src), td, tools._LO_DRAW_PDF)
    print("JSON filter:", "OK" if res else "FAIL " + err)
    assert res, "bo loc JSON khong chay"

pdf = os.path.join(OUT, "so-do-mau.pdf")
print("engine used:", tools.visio_to_pdf(src, pdf))
d = pymupdf.open(pdf)
print("pages:", d.page_count, [tuple(round(v) for v in p.rect) for p in d])
text = " | ".join(p.get_text().strip().replace("\n", " ") for p in d)
print("text:", text)
assert d.page_count == 2, "phai co 2 trang"
for want in ("Máy chủ ERP", "Tường lửa", "Hà Nội", "Kho dữ liệu"):
    assert want in text, "thieu chu: " + want
print("vector drawings page1:", len(d[0].get_drawings()))
for fmt, dpi, tr in (("png", 600, True), ("jpg", 300, False), ("svg", 0, False)):
    outs, low = tools.export_pdf_pages(d, OUT, "so-do-mau", fmt, dpi or 300, tr)
    for o in outs:
        extra = ""
        if fmt != "svg":
            px = pymupdf.Pixmap(o)
            extra = f"{px.width}x{px.height} alpha={px.alpha} dpi={px.xres}"
        print(fmt, os.path.basename(o), os.path.getsize(o) // 1024, "KB", extra)
# mở thẳng file Visio như khi người dùng mở trong app
data, eng = tools.any_to_pdf_bytes(src)
print("any_to_pdf_bytes:", len(data), "bytes via", eng)
print("ALL OK")

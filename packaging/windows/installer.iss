; Inno Setup 6 - bo cai Windows cho PDF Editor Lite (file nay luu dang UTF-8 co BOM).
; Duoc goi tu build_windows.ps1 voi cac tuy chon /DWithRapid /DWithLO /DWithOllama /DWithModel /DModel=... /DAppVer=...
#ifndef AppVer
  #define AppVer "1.0.0"
#endif
#ifndef Model
  #define Model "gemma3:4b"
#endif
#define AppName "PDF Editor Lite"
#define AppExe "PDFEditorLite.exe"
#define Work "..\..\build_win"

[Setup]
AppId={{6C1E6C0B-7B0E-4E7B-9B1B-2F5C3F0E9A41}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=ngthhung
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#Work}\output
OutputBaseFilename=PDF-Editor-Lite-{#AppVer}-Setup
SetupIconFile=..\..\assets\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2/normal
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
ChangesAssociations=yes
#ifdef WithModel
DiskSpanning=yes
DiskSliceSize=2000000000
#endif

[Messages]
SelectComponentsLabel2=Tích chọn những thành phần muốn cài, bỏ tích những thành phần không cần. Có thể chạy lại bộ cài này để thêm hoặc bớt thành phần sau.

[Types]
Name: "full"; Description: "Đầy đủ: cài tất cả, dùng được mọi chức năng ngay"
Name: "standard"; Description: "Thông thường: không cài AI dịch chạy trên máy"
Name: "compact"; Description: "Gọn nhẹ: chỉ phần chính của ứng dụng"
Name: "custom"; Description: "Tự chọn"; Flags: iscustom

[Components]
Name: "core"; Description: "PDF Editor Lite (xem, sửa, ghép/tách, in, bookmark, ký số, chuyển đổi, dịch)"; Types: full standard compact custom; Flags: fixed
Name: "tess"; Description: "OCR trên máy cho bản scan sạch (Tesseract: tiếng Việt, tiếng Anh)"; Types: full standard
#ifdef WithRapid
Name: "rapid"; Description: "OCR trên máy cho ảnh chụp / scan xấu (RapidOCR)"; Types: full standard
#endif
#ifdef WithLO
Name: "lo"; Description: "LibreOffice: chuyển Word / Excel / PowerPoint sang PDF (bỏ tích nếu máy đã có Microsoft Office)"; Types: full standard
#endif
#ifdef WithOllama
Name: "ollama"; Description: "AI dịch chạy ngay trên máy, không cần mạng và API key (Ollama; cần RAM từ 8 GB)"; Types: full
#ifdef WithModel
Name: "ollama\model"; Description: "Model dịch {#Model} (kèm sẵn trong bộ cài)"; Types: full
#else
Name: "ollama\model"; Description: "Model dịch {#Model} (TẢI VỀ khi cài: cần mạng, vài GB)"; Types: full
#endif
#endif

[Tasks]
Name: "desktopicon"; Description: "Tạo lối tắt ngoài Desktop"
Name: "assocpdf"; Description: "Thêm PDF Editor Lite vào danh sách chương trình mở file .pdf (Open with)"

[Files]
Source: "{#Work}\dist\PDFEditorLite\*"; DestDir: "{app}"; Components: core; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Work}\vendor\tessdata\*"; DestDir: "{app}\resources\tessdata"; Components: tess; Flags: ignoreversion
#ifdef WithRapid
Source: "{#Work}\vendor\rapid\_internal\*"; DestDir: "{app}\_internal"; Components: rapid; Flags: recursesubdirs createallsubdirs ignoreversion
#endif
#ifdef WithLO
Source: "{#Work}\vendor\LibreOffice.msi"; DestDir: "{tmp}"; Components: lo; Flags: deleteafterinstall
#endif
#ifdef WithOllama
Source: "{#Work}\vendor\OllamaSetup.exe"; DestDir: "{tmp}"; Components: ollama; Flags: deleteafterinstall
#ifdef WithModel
Source: "{#Work}\vendor\ollama_models\*"; DestDir: "{%USERPROFILE}\.ollama\models"; Components: ollama\model; Flags: recursesubdirs createallsubdirs uninsneveruninstall onlyifdoesntexist
#endif
#endif

[InstallDelete]
; bo tich mot thanh phan khi chay lai bo cai thi go phan do di
Type: filesandordirs; Name: "{app}\resources\tessdata"; Components: not tess
#ifdef WithRapid
Type: filesandordirs; Name: "{app}\_internal\rapidocr"; Components: not rapid
Type: filesandordirs; Name: "{app}\_internal\onnxruntime"; Components: not rapid
#endif

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Dang ky de app xuat hien trong "Open with" va trong Settings > Default apps. Windows 10/11 khong cho bo cai tu dat
; lam mac dinh: nguoi dung chon "Always" o lan mo dau, hoac vao Default apps.
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf"; ValueType: string; ValueData: "Tài liệu PDF"; Flags: uninsdeletekey; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFEditorLite.pdf"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assocpdf
Root: HKA; Subkey: "Software\PDFEditorLite\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: assocpdf
Root: HKA; Subkey: "Software\PDFEditorLite\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "PDF Editor Lite by ngthhung"; Tasks: assocpdf
Root: HKA; Subkey: "Software\PDFEditorLite\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "PDFEditorLite.pdf"; Tasks: assocpdf
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "PDFEditorLite"; ValueData: "Software\PDFEditorLite\Capabilities"; Flags: uninsdeletevalue; Tasks: assocpdf

[Run]
#ifdef WithLO
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\LibreOffice.msi"" /qn /norestart"; Components: lo; Check: not HasLibreOffice; StatusMsg: "Đang cài LibreOffice (mất vài phút)..."; Flags: waituntilterminated
#endif
#ifdef WithOllama
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/VERYSILENT /NORESTART"; Components: ollama; Check: not HasOllama; StatusMsg: "Đang cài Ollama (AI dịch chạy trên máy)..."; Flags: waituntilterminated
#ifndef WithModel
Filename: "{code:OllamaExe}"; Parameters: "pull {#Model}"; Components: ollama\model; StatusMsg: "Đang tải model dịch {#Model} (vài GB, cần mạng; có thể mất khá lâu)..."; Flags: waituntilterminated runasoriginaluser
#endif
#endif
Filename: "{app}\{#AppExe}"; Description: "Mở {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function HasLibreOffice(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf}\LibreOffice\program\soffice.exe'))
         or FileExists(ExpandConstant('{commonpf32}\LibreOffice\program\soffice.exe'));
end;

function OllamaExe(Param: String): String;
begin
  Result := ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe');
end;

function HasOllama(): Boolean;
begin
  Result := FileExists(OllamaExe(''));
end;

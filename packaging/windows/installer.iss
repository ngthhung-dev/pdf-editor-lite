; Inno Setup 6 - bo cai Windows cho PDF Editor Lite (file nay luu dang UTF-8 co BOM).
; Duoc goi tu build_windows.ps1 voi cac tuy chon /DWithRapid /DWithLO /DWithOllama /DWithModel /DModel=... /DAppVer=...
#ifndef AppVer
  #define AppVer "1.0.0"
#endif
#ifndef Build
  #define Build "0"
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
AppVerName={#AppName} {#AppVer} (build {#Build})
AppPublisher=ngthhung
VersionInfoVersion={#AppVer}.{#Build}
VersionInfoTextVersion={#AppVer}.{#Build}
VersionInfoProductVersion={#AppVer}.{#Build}
VersionInfoProductTextVersion={#AppVer}
VersionInfoProductName={#AppName}
VersionInfoCompany=ngthhung
VersionInfoDescription={#AppName} by ngthhung
VersionInfoCopyright=Copyright © 2026 ngthhung
AppCopyright=Copyright © 2026 ngthhung
AppContact=ngthhung.dev@gmail.com
AppSupportPhone=0968 799 365
AppComments={#AppName} by ngthhung
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
ShowLanguageDialog=no
ChangesAssociations=yes
; app dang mo thi bo cai tu dong dong lai de ghi de duoc file moi (neu khong se van chay ban cu)
CloseApplications=force
RestartApplications=no
#ifdef WithModel
DiskSpanning=yes
DiskSliceSize=2000000000
#endif

[Languages]
; Inno Setup khong kem tieng Viet: dung file dich dat canh kich ban nay
Name: "vi"; MessagesFile: "Vietnamese.isl"

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
Name: "ollama"; Description: "AI dịch chạy ngay trên máy, không cần API key (Ollama; TẢI VỀ khi cài ~1,5 GB; cần RAM từ 8 GB)"; Types: full
#ifdef WithModel
Name: "ollama\model"; Description: "Model dịch {#Model} (kèm sẵn trong bộ cài)"; Types: full
#else
Name: "ollama\model"; Description: "Model dịch {#Model} (TẢI VỀ khi cài: cần mạng, vài GB)"; Types: full
#endif
#endif

[Tasks]
Name: "desktopicon"; Description: "Tạo lối tắt ngoài Desktop"
Name: "assocpdf"; Description: "Thêm PDF Editor Lite vào danh sách chương trình mở file .pdf (Open with)"
Name: "faststart"; Description: "Khởi động nhanh: chạy sẵn PDF Editor Lite (ẩn) khi đăng nhập Windows, mở file PDF là hiện ngay (app luôn chạy nền, tốn thêm một ít RAM)"

[Files]
Source: "{#Work}\dist\PDFEditorLite\*"; DestDir: "{app}"; Components: core; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Work}\vendor\tessdata\*"; DestDir: "{app}\resources\tessdata"; Components: tess; Flags: ignoreversion
#ifdef WithRapid
Source: "{#Work}\vendor\rapid\_internal\*"; DestDir: "{app}\_internal"; Components: rapid; Flags: recursesubdirs createallsubdirs ignoreversion
#endif
#ifdef WithLO
Source: "{#Work}\vendor\LibreOffice.msi"; DestDir: "{tmp}"; Components: lo; Flags: deleteafterinstall nocompression
#endif
#ifdef WithOllama
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
; AppUserModelID phai trung voi ma app tu dat luc chay (ngthhung.PDFEditorLite): Windows dua vao do de lay dung bieu tuong
; cho nut tren thanh tac vu va de ghim app.
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\app_icon.ico"; AppUserModelID: "ngthhung.PDFEditorLite"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\app_icon.ico"; AppUserModelID: "ngthhung.PDFEditorLite"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PDFEditorLite"; ValueData: """{app}\{#AppExe}"" --background"; Flags: uninsdeletevalue; Tasks: faststart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "PDFEditorLite"; Flags: deletevalue uninsdeletevalue; Tasks: not faststart
; Dang ky de app xuat hien trong "Open with" va trong Settings > Default apps. Windows 10/11 khong cho bo cai tu dat
; lam mac dinh: nguoi dung chon "Always" o lan mo dau, hoac vao Default apps.
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf"; ValueType: string; ValueData: "Tài liệu PDF"; Flags: uninsdeletekey; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assocpdf
; Khung Preview (Alt+P) va anh thu nho cua Explorer do mot "preview handler" ve, tra theo kieu file dang lam mac dinh.
; App khong co bo ve rieng: muon lai bo ve PDF co san tren may (Microsoft Edge, Acrobat, Foxit...) de khung Preview van hien noi dung.
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\shellex\{{8895b1c6-b41f-4c1c-a562-0d564250836f}"; ValueType: string; ValueData: "{code:PdfShellHandler|preview}"; Check: HasPdfShellHandler('preview'); Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFEditorLite.pdf\shellex\{{E357FCCD-A995-4576-B01F-234630154E96}"; ValueType: string; ValueData: "{code:PdfShellHandler|thumb}"; Check: HasPdfShellHandler('thumb'); Tasks: assocpdf
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
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/VERYSILENT /NORESTART"; Components: ollama; Check: OllamaDownloaded; StatusMsg: "Đang cài Ollama (AI dịch chạy trên máy)..."; Flags: waituntilterminated
#ifndef WithModel
Filename: "{code:OllamaExe}"; Parameters: "pull {#Model}"; Components: ollama\model; Check: HasOllama; StatusMsg: "Đang tải model dịch {#Model} (vài GB, cần mạng; có thể mất khá lâu)..."; Flags: waituntilterminated runasoriginaluser
#endif
#endif
Filename: "{app}\{#AppExe}"; Parameters: "--background"; Tasks: faststart; Flags: nowait runasoriginaluser
Filename: "{app}\{#AppExe}"; Description: "Mở {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function PdfShellHandler(Kind: String): String;
var
  Ids: array[0..6] of String;
  I, Root: Integer;
  S: String;
begin
  Result := '';
  if Kind = 'preview' then Kind := '{8895b1c6-b41f-4c1c-a562-0d564250836f}' else Kind := '{E357FCCD-A995-4576-B01F-234630154E96}';
  Ids[0] := 'MSEdgePDF'; Ids[1] := 'AcroExch.Document.DC'; Ids[2] := 'AcroExch.Document'; Ids[3] := 'Acrobat.Document.DC';
  Ids[4] := 'FoxitReader.Document'; Ids[5] := 'FoxitPhantomPDF.Document'; Ids[6] := 'SystemFileAssociations\.pdf';
  for I := 0 to 6 do
    if RegQueryStringValue(HKCR, Ids[I] + '\shellex\' + Kind, '', S) and (S <> '') then
    begin
      Result := S;
      Exit;
    end;
  { Edge co san tren Windows 10/11: bo ve PDF cua no cho khung Preview }
  if CompareText(Kind, '{8895b1c6-b41f-4c1c-a562-0d564250836f}') = 0 then
  begin
    if IsWin64 then Root := HKCR64 else Root := HKCR;
    if RegKeyExists(Root, 'CLSID\{3A84F9C2-6164-485C-A7D9-4B27F8AC009E}') then
      Result := '{3A84F9C2-6164-485C-A7D9-4B27F8AC009E}';
  end;
end;

function HasPdfShellHandler(Kind: String): Boolean;
begin
  Result := PdfShellHandler(Kind) <> '';
end;

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

function OllamaDownloaded(): Boolean;
begin
  Result := (not HasOllama()) and FileExists(ExpandConstant('{tmp}\OllamaSetup.exe'));
end;

#ifdef WithOllama
var
  DownloadPage: TDownloadWizardPage;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Đang tải Ollama', 'Tải bộ cài Ollama (khoảng 1,5 GB) từ ollama.com. Cần có mạng; có thể mất vài phút.', @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsComponentSelected('ollama') and (not HasOllama()) then begin
    DownloadPage.Clear;
    DownloadPage.Add('https://ollama.com/download/OllamaSetup.exe', 'OllamaSetup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        // khong tai duoc (mat mang / nguoi dung bam Huy): van cai phan con lai, chi thieu AI dich chay tren may
        SuppressibleMsgBox('Không tải được Ollama nên sẽ bỏ qua phần "AI dịch chạy trên máy". Các phần khác vẫn được cài bình thường.' + #13#10 + #13#10 + 'Có thể chạy lại bộ cài này khi có mạng để thêm sau.', mbInformation, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
#endif

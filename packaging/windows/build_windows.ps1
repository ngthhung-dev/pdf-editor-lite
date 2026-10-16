<#
  Build bo cai Windows cho PDF Editor Lite.
  Chay:  powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
  Tuy chon:
    -NoLibreOffice   khong kem LibreOffice (bo cai nhe hon ~350 MB)
    -NoOllama        khong kem Ollama (AI dich chay tren may)
    -NoModel         kem Ollama nhung KHONG kem model (model se duoc tai luc cai, can mang)
    -Model <ten>     model dich kem theo (mac dinh gemma3:4b, ~3.3 GB, can may RAM 8 GB tro len)
  Can san tren may build: Python 3.10-3.13 (64-bit), Inno Setup 6, mang Internet.
#>
param([switch]$NoLibreOffice, [switch]$NoOllama, [switch]$NoModel, [string]$Model = "gemma3:4b")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$root   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$work   = Join-Path $root "build_win"
$vendor = Join-Path $work "vendor"
$dist   = Join-Path $work "dist\PDFEditorLite"
New-Item -ItemType Directory -Force -Path $work, $vendor | Out-Null
$log = Join-Path $work "build.log"
function Step($t) {
    Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan
    Add-Content -Path $log -Value "$(Get-Date -Format 'HH:mm:ss')  $t" -Encoding UTF8
}
function Note($t) { Write-Host "  $t"; Add-Content -Path $log -Value "  $(Get-Date -Format 'HH:mm:ss')  $t" -Encoding UTF8 }
Set-Content -Path $log -Value "Build PDF Editor Lite - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8
trap { Add-Content -Path $log -Value "LOI: $_" -Encoding UTF8; throw }
function Get-File($url, $out) {
    if (Test-Path $out) { Write-Host "  da co: $out"; return }
    Note "tai: $url"
    # curl.exe (co san trong Windows 10/11): theo chuyen huong, thu lai khi rot mang, co gioi han thoi gian de khong treo
    & curl.exe -L --fail --silent --show-error --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 1500 -o "$out.part" $url
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$out.part")) { throw "Khong tai duoc: $url (curl ma $LASTEXITCODE)" }
    Move-Item -Force "$out.part" $out
    Note ("  xong: " + [math]::Round((Get-Item $out).Length / 1MB) + " MB")
}

# ---------------------------------------------------------------- 1. Python + thu vien
Step "1/8  Python va thu vien"
$py = $null
foreach ($c in @(@("py", "-3"), @("python"))) {
    try { & $c[0] $c[1..9] -c "import sys; assert sys.version_info[:2] >= (3,10) and sys.maxsize > 2**32" 2>$null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
}
if (-not $py) { throw "Khong tim thay Python 3.10+ 64-bit. Cai tu https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." }
$venv = Join-Path $work "venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) { & $py[0] $py[1..9] -m venv $venv }
$vpy = "$venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip | Out-Null
& $vpy -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Cai thu vien chinh that bai." }
Note "thu vien chinh: OK"
foreach ($pkg in @("pdf2docx", "python-pkcs11", "rapidocr", "onnxruntime", "pyinstaller")) {
    & $vpy -m pip install $pkg
    if ($LASTEXITCODE -ne 0) {
        if ($pkg -eq "pyinstaller") { throw "Khong cai duoc PyInstaller." }
        Note "KHONG cai duoc $pkg : chuc nang tuong ung se thieu trong bo cai."
    } else { Note "$pkg : OK" }
}

# ---------------------------------------------------------------- 2. Model tieng Viet cua RapidOCR
Step "2/8  Model tieng Viet/Latin cua RapidOCR (tai san de may nguoi dung khong can mang)"
$warm = Start-Process -FilePath $vpy -ArgumentList "-c", "`"from litepdf import ocr; ocr.rapid_engine('latin', ''); ocr.rapid_engine('korean', ''); print('model latin+korean: OK')`"" -WorkingDirectory $root -PassThru -NoNewWindow
if (-not $warm.WaitForExit(300000)) { $warm.Kill(); Note "Tai model latin qua 5 phut: bo qua (app se tu tai o lan dung dau)." }
elseif ($warm.ExitCode -ne 0) { Note "Chua tai duoc model latin: app se tu tai o lan dung dau tien (can mang)." }
else { Note "model latin: OK" }
$latin = Get-ChildItem -Path "$venv\Lib\site-packages\rapidocr\models" -Filter "*PP-OCRv5*" -ErrorAction SilentlyContinue
Note ("file model latin trong goi: " + ($latin | ForEach-Object { $_.Name }) -join ", ")

# ---------------------------------------------------------------- 3. Du lieu Tesseract
Step "3/8  Du lieu ngon ngu Tesseract (vie, eng, osd, chi_sim, chi_tra, jpn, kor)"
$tess = Join-Path $vendor "tessdata"
New-Item -ItemType Directory -Force -Path $tess | Out-Null
foreach ($l in @("vie", "eng", "osd", "chi_sim", "chi_tra", "jpn", "kor")) {
    Get-File "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$l.traineddata" (Join-Path $tess "$l.traineddata")
}

# ---------------------------------------------------------------- 4. Dong goi app
Step "4/8  Dong goi app bang PyInstaller"
if (Test-Path (Join-Path $work "dist")) { Remove-Item -Recurse -Force (Join-Path $work "dist") }
& $vpy -m PyInstaller (Join-Path $root "packaging\PDFEditorLite.spec") --noconfirm --distpath (Join-Path $work "dist") --workpath (Join-Path $work "pyi")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$dist\PDFEditorLite.exe")) { throw "PyInstaller that bai." }
Note ("dung luong ban dong goi: " + [math]::Round((Get-ChildItem $dist -Recurse | Measure-Object Length -Sum).Sum / 1MB) + " MB")

# ---------------------------------------------------------------- 5. Tu kiem tra ban dong goi
Step "5/8  Tu kiem tra ban dong goi"
New-Item -ItemType Directory -Force -Path "$dist\resources" | Out-Null
Copy-Item -Recurse -Force $tess "$dist\resources\tessdata"
$st = Join-Path $work "selftest.json"
if (Test-Path $st) { Remove-Item $st }
$p = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "--selftest", "`"$st`"" -PassThru
if (-not $p.WaitForExit(300000)) { $p.Kill(); Note "Tu kiem tra chay qua 5 phut: da dung." }
if (-not (Test-Path $st)) { throw "Ban dong goi khong chay duoc (khong tao ra selftest.json)." }
Get-Content $st -Encoding UTF8 | Write-Host
Add-Content -Path $log -Value (Get-Content $st -Raw -Encoding UTF8) -Encoding UTF8
if ((Get-Content $st -Raw -Encoding UTF8) -match '"(pymupdf|pyhanko|fonts)": "LOI') { throw "Ban dong goi thieu thanh phan bat buoc (xem tren)." }
# Do thoi gian khoi dong (mo app kem mot file PDF, den luc trang dau ve xong): lan 1 gan nhu "lanh", lan 2 "am"
$pdf = Join-Path $root "assets\Huong dan su dung PDF Editor Lite.pdf"
foreach ($k in 1, 2) {
    $pj = Join-Path $work "startup$k.json"
    $env:LITEPDF_STARTUP_PROBE = $pj
    $sp = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "`"$pdf`"" -PassThru
    if (-not $sp.WaitForExit(120000)) { $sp.Kill() }
    Remove-Item Env:\LITEPDF_STARTUP_PROBE
    if (Test-Path $pj) { Note ("khoi dong lan ${k} (giay tu luc tao tien trinh): " + (Get-Content $pj -Raw)) } else { Note "khoi dong lan ${k}: khong do duoc" }
}
# Khoi dong nhanh: chay san an (--background), roi do thoi gian mo mot file PDF bang cach giao cho ban chay san
$bg = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "--background" -PassThru
Start-Sleep -Seconds 12
$sw = [Diagnostics.Stopwatch]::StartNew()
$h = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "`"$pdf`"" -PassThru
if (-not $h.WaitForExit(60000)) { $h.Kill() }
Note ("khoi dong nhanh: giao file cho ban chay san mat " + [math]::Round($sw.Elapsed.TotalSeconds, 2) + " giay, ban chay san con song: " + (-not $bg.HasExited))
if (-not $bg.HasExited) { $bg.Kill() }
Start-Sleep -Seconds 1
foreach ($opt in "windows:nodirectwrite", "windows:fontengine=freetype") {
    $pj = Join-Path $work "startup_opt.json"
    $env:LITEPDF_STARTUP_PROBE = $pj; $env:QT_QPA_PLATFORM = $opt
    $sp = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "`"$pdf`"" -PassThru
    if (-not $sp.WaitForExit(120000)) { $sp.Kill() }
    Remove-Item Env:\LITEPDF_STARTUP_PROBE; Remove-Item Env:\QT_QPA_PLATFORM
    if (Test-Path $pj) { Note ("khoi dong voi ${opt}: " + (Get-Content $pj -Raw)); Remove-Item $pj } else { Note "khoi dong voi ${opt}: khong do duoc" }
}
Remove-Item -Recurse -Force "$dist\resources\tessdata"      # tessdata la thanh phan tuy chon, do bo cai chep vao

# ---------------------------------------------------------------- 6. Tach thanh phan tuy chon RapidOCR
Step "6/8  Tach thanh phan tuy chon (RapidOCR)"
$rapid = Join-Path $vendor "rapid\_internal"
if (Test-Path (Join-Path $vendor "rapid")) { Remove-Item -Recurse -Force (Join-Path $vendor "rapid") }
New-Item -ItemType Directory -Force -Path $rapid | Out-Null
foreach ($d in @("rapidocr", "onnxruntime")) {
    if (Test-Path "$dist\_internal\$d") { Move-Item "$dist\_internal\$d" (Join-Path $rapid $d) }
}
$hasRapid = Test-Path (Join-Path $rapid "rapidocr")

# ---------------------------------------------------------------- 7. LibreOffice, Ollama, model
Step "7/8  Tai LibreOffice / Ollama / model dich"
$ver = if ($env:LITEPDF_VERSION) { $env:LITEPDF_VERSION } else { "1.0.0" }
$defs = @("/DAppVer=$ver")
Note "tham so: NoLibreOffice=$NoLibreOffice NoOllama=$NoOllama NoModel=$NoModel Model=$Model"
if ($hasRapid) { $defs += "/DWithRapid=1" }
if (-not $NoLibreOffice) {
    $lo = Join-Path $vendor "LibreOffice.msi"
    if (-not (Test-Path $lo)) {
        $idx = (& curl.exe -L --fail --silent --show-error --connect-timeout 30 --max-time 120 "https://download.documentfoundation.org/libreoffice/stable/") -join "`n"
        $vers = [regex]::Matches($idx, 'href="(\d+\.\d+\.\d+)/"') | ForEach-Object { [version]$_.Groups[1].Value } | Sort-Object
        if (-not $vers) { throw "Khong doc duoc danh sach phien ban LibreOffice." }
        $v = $vers[0].ToString()      # ban on dinh cu hon ("still") trong muc stable: it loi hon ban moi nhat
        Note "LibreOffice phien ban $v"
        Get-File "https://download.documentfoundation.org/libreoffice/stable/$v/win/x86_64/LibreOffice_${v}_Win_x86-64.msi" $lo
    }
    $defs += "/DWithLO=1"
}
if (-not $NoOllama) {
    # Bo cai Ollama nang ~1.5 GB nen KHONG nhet vao bo cai: khi nguoi dung tich muc nay, trinh cai se tai Ollama ve (can mang).
    # Chi tai ve may build khi can keo san model de kem theo.
    if (-not $NoModel) { Get-File "https://ollama.com/download/OllamaSetup.exe" (Join-Path $vendor "OllamaSetup.exe") }
    $defs += "/DWithOllama=1"; $defs += "/DModel=$Model"
    if (-not $NoModel) {
        $models = Join-Path $vendor "ollama_models"
        if (-not (Test-Path "$models\manifests")) {
            $ol = (Get-Command ollama -ErrorAction SilentlyContinue).Source
            if (-not $ol -and $env:CI) {          # may build tu dong: cai Ollama de keo model ve
                # khong dung -Wait: trinh cai Ollama tu mo ung dung sau khi cai, -Wait se cho ca ung dung do va treo mai
                $inst = Start-Process -FilePath (Join-Path $vendor "OllamaSetup.exe") -ArgumentList "/VERYSILENT", "/NORESTART" -PassThru
                if (-not $inst.WaitForExit(900000)) { $inst.Kill(); Note "Cai Ollama qua 15 phut: bo qua viec kem model." }
                $ol = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
            }
            if ($ol -and (Test-Path $ol)) {
                $env:OLLAMA_MODELS = $models
                $srv = Start-Process -FilePath $ol -ArgumentList "serve" -PassThru -WindowStyle Hidden
                Start-Sleep -Seconds 6
                & $ol pull $Model
                $ok = $LASTEXITCODE -eq 0
                Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
                Remove-Item Env:\OLLAMA_MODELS
                if (-not $ok) { Write-Warning "Khong keo duoc model $Model : bo cai se tai model luc cai dat."; if (Test-Path $models) { Remove-Item -Recurse -Force $models } }
            } else {
                Write-Warning "May build chua co Ollama nen khong kem san duoc model: bo cai se tai model $Model luc cai dat (can mang). Muon kem san: cai Ollama roi chay lai."
            }
        }
        if (Test-Path "$models\manifests") { $defs += "/DWithModel=1" }
    }
}

# ---------------------------------------------------------------- 8. Tao file cai
Step "8/8  Tao file cai bang Inno Setup"
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { $iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source }
if (-not $iscc) { throw "Chua cai Inno Setup 6. Tai mien phi tai https://jrsoftware.org/isdl.php roi chay lai." }
Note "tuy chon: $($defs -join ' ')"
$isslog = Join-Path $work "inno.log"
& $iscc @defs (Join-Path $PSScriptRoot "installer.iss") 2>&1 | Tee-Object -FilePath $isslog | Select-Object -Last 40
if ($LASTEXITCODE -ne 0) { Add-Content -Path $log -Value (Get-Content $isslog -Tail 40 | Out-String) -Encoding UTF8; throw "Inno Setup bao loi." }
Write-Host ""
Write-Host "XONG. File cai nam trong: $(Join-Path $work 'output')" -ForegroundColor Green
Get-ChildItem (Join-Path $work "output") | ForEach-Object { Note ("XONG: " + $_.Name + "  " + [math]::Round($_.Length / 1MB) + " MB") }
foreach ($f in @((Get-ChildItem (Join-Path $work "output") -Filter *.exe | Select-Object -First 1).FullName, "$dist\PDFEditorLite.exe")) {
    $v = (Get-Item $f).VersionInfo
    Note ("thong tin " + (Split-Path $f -Leaf) + ": mo ta=[" + $v.FileDescription + "] phien ban file=[" + $v.FileVersion + "] san pham=[" + $v.ProductName + " " + $v.ProductVersion + "] cong ty=[" + $v.CompanyName + "] ban quyen=[" + $v.LegalCopyright + "] ghi chu=[" + $v.Comments + "]")
}
Get-ChildItem (Join-Path $work "output") | Format-Table Name, @{n="MB"; e={[math]::Round($_.Length / 1MB)}}

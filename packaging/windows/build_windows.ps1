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
function Step($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Get-File($url, $out) {
    if (Test-Path $out) { Write-Host "  da co: $out"; return }
    Write-Host "  tai: $url"
    Invoke-WebRequest -Uri $url -OutFile "$out.part" -UseBasicParsing
    Move-Item -Force "$out.part" $out
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
foreach ($pkg in @("pdf2docx", "python-pkcs11", "rapidocr", "onnxruntime", "pyinstaller")) {
    & $vpy -m pip install $pkg
    if ($LASTEXITCODE -ne 0) {
        if ($pkg -eq "pyinstaller") { throw "Khong cai duoc PyInstaller." }
        Write-Warning "Khong cai duoc $pkg : chuc nang tuong ung se thieu trong bo cai."
    }
}

# ---------------------------------------------------------------- 2. Model tieng Viet cua RapidOCR
Step "2/8  Model tieng Viet/Latin cua RapidOCR (tai san de may nguoi dung khong can mang)"
Push-Location $root
& $vpy -c "from litepdf import ocr; ocr.rapid_engine('latin', ''); print('  model latin: OK')"
if ($LASTEXITCODE -ne 0) { Write-Warning "Chua tai duoc model latin: app se tu tai o lan dung dau tien (can mang)." }
Pop-Location

# ---------------------------------------------------------------- 3. Du lieu Tesseract
Step "3/8  Du lieu ngon ngu Tesseract (vie, eng, osd)"
$tess = Join-Path $vendor "tessdata"
New-Item -ItemType Directory -Force -Path $tess | Out-Null
foreach ($l in @("vie", "eng", "osd")) {
    Get-File "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$l.traineddata" (Join-Path $tess "$l.traineddata")
}

# ---------------------------------------------------------------- 4. Dong goi app
Step "4/8  Dong goi app bang PyInstaller"
if (Test-Path (Join-Path $work "dist")) { Remove-Item -Recurse -Force (Join-Path $work "dist") }
& $vpy -m PyInstaller (Join-Path $root "packaging\PDFEditorLite.spec") --noconfirm --distpath (Join-Path $work "dist") --workpath (Join-Path $work "pyi")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$dist\PDFEditorLite.exe")) { throw "PyInstaller that bai." }

# ---------------------------------------------------------------- 5. Tu kiem tra ban dong goi
Step "5/8  Tu kiem tra ban dong goi"
New-Item -ItemType Directory -Force -Path "$dist\resources" | Out-Null
Copy-Item -Recurse -Force $tess "$dist\resources\tessdata"
$st = Join-Path $work "selftest.json"
if (Test-Path $st) { Remove-Item $st }
$p = Start-Process -FilePath "$dist\PDFEditorLite.exe" -ArgumentList "--selftest", "`"$st`"" -PassThru -Wait
if (-not (Test-Path $st)) { throw "Ban dong goi khong chay duoc (khong tao ra selftest.json)." }
Get-Content $st -Encoding UTF8 | Write-Host
if ((Get-Content $st -Raw -Encoding UTF8) -match '"(pymupdf|pyhanko|fonts)": "LOI') { throw "Ban dong goi thieu thanh phan bat buoc (xem tren)." }
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
$defs = @("/DAppVer=1.0.0")
if ($hasRapid) { $defs += "/DWithRapid=1" }
if (-not $NoLibreOffice) {
    $lo = Join-Path $vendor "LibreOffice.msi"
    if (-not (Test-Path $lo)) {
        $idx = (Invoke-WebRequest -Uri "https://download.documentfoundation.org/libreoffice/stable/" -UseBasicParsing).Content
        $vers = [regex]::Matches($idx, 'href="(\d+\.\d+\.\d+)/"') | ForEach-Object { [version]$_.Groups[1].Value } | Sort-Object
        if (-not $vers) { throw "Khong doc duoc danh sach phien ban LibreOffice." }
        $v = $vers[0].ToString()      # ban on dinh cu hon ("still") trong muc stable: it loi hon ban moi nhat
        Get-File "https://download.documentfoundation.org/libreoffice/stable/$v/win/x86_64/LibreOffice_${v}_Win_x86-64.msi" $lo
    }
    $defs += "/DWithLO=1"
}
if (-not $NoOllama) {
    Get-File "https://ollama.com/download/OllamaSetup.exe" (Join-Path $vendor "OllamaSetup.exe")
    $defs += "/DWithOllama=1"; $defs += "/DModel=$Model"
    if (-not $NoModel) {
        $models = Join-Path $vendor "ollama_models"
        if (-not (Test-Path "$models\manifests")) {
            $ol = (Get-Command ollama -ErrorAction SilentlyContinue).Source
            if (-not $ol -and $env:CI) {          # may build tu dong: cai Ollama de keo model ve
                Start-Process -FilePath (Join-Path $vendor "OllamaSetup.exe") -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
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
Write-Host "  tuy chon: $($defs -join ' ')"
& $iscc @defs (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup bao loi." }
Write-Host ""
Write-Host "XONG. File cai nam trong: $(Join-Path $work 'output')" -ForegroundColor Green
Get-ChildItem (Join-Path $work "output") | Format-Table Name, @{n="MB"; e={[math]::Round($_.Length / 1MB)}}

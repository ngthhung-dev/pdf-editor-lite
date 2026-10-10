@echo off
rem PDF Editor Lite - chay tren Windows. Lan dau se tu cai thu vien vao thu muc .venv ben canh.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" goto run

echo Lan dau chay: dang cai thu vien, can co mang, mat vai phut...
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if not exist ".venv\Scripts\python.exe" goto nopython
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install pdf2docx
if errorlevel 1 echo [Canh bao] Khong cai duoc pdf2docx: chuc nang PDF sang Word se khong dung duoc.
".venv\Scripts\python.exe" -m pip install python-pkcs11
if errorlevel 1 echo [Canh bao] Khong cai duoc python-pkcs11: chua ky duoc bang USB token.

:run
start "" ".venv\Scripts\pythonw.exe" main.py %*
exit /b 0

:nopython
echo.
echo Chua cai Python. Tai Python 3.11 tro len tai https://www.python.org/downloads/
echo Khi cai nho tick o "Add python.exe to PATH", sau do chay lai file nay.
pause
exit /b 1

:failed
echo.
echo Cai thu vien that bai. Kiem tra mang roi xoa thu muc .venv va chay lai.
rmdir /s /q .venv
pause
exit /b 1

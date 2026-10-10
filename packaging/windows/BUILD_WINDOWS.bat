@echo off
rem Nhap dup file nay de build bo cai Windows day du. Ket qua nam trong thu muc build_win\output.
cd /d "%~dp0\..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\windows\build_windows.ps1" %*
echo.
pause

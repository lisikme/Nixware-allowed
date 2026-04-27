@echo off
echo Building executable in ONEDIR mode (скрытая консоль)...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul
pyi-makespec --onedir --windowed --icon "app.ico" --name "KL-MonitoringCS2" --hidden-import=win32file --hidden-import=win32event --hidden-import=win32api "app.py"
echo import sys >> KL-MonitoringCS2.spec
echo sys.setrecursionlimit(5000) >> KL-MonitoringCS2.spec
pyinstaller --noconfirm --distpath "./" --clean KL-MonitoringCS2.spec
echo ========================================
echo Ready!
echo ========================================
pause
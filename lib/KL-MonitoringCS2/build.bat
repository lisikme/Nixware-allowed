@echo off
echo Building executable...
pyi-makespec --onefile --windowed --icon "app.ico" --name "KL-MonitoringCS2" --runtime-tmpdir "./temp" --hidden-import=win32file --hidden-import=win32event --hidden-import=win32api "app.py"
echo import sys >> KL-MonitoringCS2.spec
echo sys.setrecursionlimit(5000) >> KL-MonitoringCS2.spec
pyinstaller --noconfirm --distpath "./" --clean KL-MonitoringCS2.spec
echo.
echo ========================================
echo Build complete!
echo ========================================
pause
@echo off
echo Building executable...
pyi-makespec --onefile --windowed --icon "app.ico" --name "KL-RadioAPI" --runtime-tmpdir "./temp" --hidden-import=win32file --hidden-import=win32event --hidden-import=win32api "app.py"
echo import sys >> KL-RadioAPI.spec
echo sys.setrecursionlimit(5000) >> KL-RadioAPI.spec
pyinstaller --noconfirm --distpath "./" --clean KL-RadioAPI.spec
echo.
echo ========================================
echo Build complete!
echo ========================================
pause
@echo off
echo Building executable...
pyi-makespec --onefile --windowed --icon "app.ico" --name "KL-DiscordRPC" --runtime-tmpdir "./temp" --hidden-import=win32file --hidden-import=win32event --hidden-import=win32api "app.py"
echo import sys >> KL-DiscordRPC.spec
echo sys.setrecursionlimit(5000) >> KL-DiscordRPC.spec
pyinstaller --noconfirm --distpath "./" --clean KL-DiscordRPC.spec
echo.
echo ========================================
echo Build complete!
echo ========================================
pause
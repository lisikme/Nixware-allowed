# from flask import Flask, request, jsonify
# import pygame
# import os

# app = Flask(__name__)

# # Инициализация микшера pygame
# pygame.mixer.init()

# @app.route('/api/playsound', methods=['GET'])
# def play_sound():
#     path = request.args.get('path')
#     volume = request.args.get('volume', default=1.0, type=float)

#     # Проверка параметров
#     if not path:
#         return jsonify({"error": "Параметр 'path' обязателен"}), 400

#     if not os.path.isfile(path):
#         return jsonify({"error": f"Файл не найден: {path}"}), 404

#     # Ограничение громкости диапазоном [0.0, 1.0]
#     volume = max(0.0, min(1.0, volume))

#     try:
#         sound = pygame.mixer.Sound(path)
#         sound.set_volume(volume)
#         sound.play()
#         return jsonify({
#             "status": "ok",
#             "path": path,
#             "volume": volume
#         })
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# if __name__ == '__main__':
#     # Порт 3308
#     app.run(host='localhost', port=3308, debug=False)


from flask import Flask, request, jsonify
import pygame
import os
import sys
import time
import threading
import tempfile
import atexit

# --- Защита от двойного запуска через lock-файл ---
LOCK_FILE = os.path.join(tempfile.gettempdir(), "cs2_sound_server.lock")

def acquire_lock():
    """Пытается создать lock-файл. Если он уже существует и процесс жив — выходим."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if is_process_alive(old_pid):
                print(f"[!] Программа уже запущена (PID {old_pid}). Выход.")
                sys.exit(0)
            else:
                os.remove(LOCK_FILE)
        except (ValueError, OSError):
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.remove(LOCK_FILE)
    except (ValueError, OSError):
        pass

def is_process_alive(pid: int) -> bool:
    """Проверка, жив ли процесс по PID."""
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel32.CloseHandle(handle)
        return bool(ok) and exit_code.value == STILL_ACTIVE
    else:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

# --- Проверка наличия процесса cs2.exe ---
def is_cs2_running() -> bool:
    if sys.platform == "win32":
        import subprocess
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/NH"],
                startupinfo=startupinfo,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).decode("cp866", errors="ignore").lower()
            return "cs2.exe" in output
        except Exception:
            return False
    else:
        import subprocess
        try:
            output = subprocess.check_output(
                ["pgrep", "-f", "cs2"], stderr=subprocess.DEVNULL
            )
            return bool(output.strip())
        except Exception:
            return False

def monitor_cs2():
    """Фон-поток: как только cs2.exe исчез — завершаем программу."""
    while is_cs2_running():
        time.sleep(2)

    print("[!] cs2.exe завершён. Закрываем программу.")
    release_lock()
    os._exit(0)


# --- Flask ---
app = Flask(__name__)
pygame.mixer.init()

@app.route('/api/playsound', methods=['GET'])
def play_sound():
    path = request.args.get('path')
    volume = request.args.get('volume', default=1.0, type=float)

    if not path:
        return jsonify({"error": "Параметр 'path' обязателен"}), 400

    if not os.path.isfile(path):
        return jsonify({"error": f"Файл не найден: {path}"}), 404

    volume = max(0.0, min(1.0, volume))

    try:
        sound = pygame.mixer.Sound(path)
        sound.set_volume(volume)
        sound.play()
        return jsonify({"status": "ok", "path": path, "volume": volume})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # 1. Защита от двойного запуска
    acquire_lock()
    atexit.register(release_lock)

    # 2. Проверяем cs2.exe — если не запущен, сразу выходим
    if not is_cs2_running():
        print("[!] cs2.exe не запущен. Выход.")
        release_lock()
        sys.exit(0)

    print("[+] cs2.exe обнаружен. Запускаем сервер...")

    # 3. Фоновый мониторинг cs2.exe
    t = threading.Thread(target=monitor_cs2, daemon=True)
    t.start()

    # 4. Запуск сервера
    app.run(host='localhost', port=3308, debug=False, use_reloader=False)
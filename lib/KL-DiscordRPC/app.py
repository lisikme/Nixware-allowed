import sys
import ctypes
import os
from pypresence import Presence # type: ignore
import time
import json
import psutil
import win32event
import win32api
import winerror

# Имя мьютекса (уникальное для этого приложения)
MUTEX_NAME = "Global\\KensoLUA_DiscordRPC_SingleInstance"

def is_already_running():
    """Проверяет, запущен ли уже другой экземпляр программы с помощью мьютекса"""
    try:
        # Создаём мьютекс
        mutex = win32event.CreateMutex(None, False, MUTEX_NAME) # type: ignore
        last_error = ctypes.GetLastError()
        
        # Если мьютекс уже существует — приложение уже запущено
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            return True
        return False
    except Exception as e:
        print(f"Ошибка при проверке мьютекса: {e}")
        return False

def is_admin():
    """Проверяет, запущен ли скрипт с правами администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate_privileges():
    """Перезапускает скрипт с правами администратора"""
    if not is_admin():
        print("Запрос прав администратора...")
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{x}"' for x in sys.argv[1:]])
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            sys.exit(0)
        except Exception as e:
            print(f"Не удалось получить права администратора: {e}")
            return False
    return True

def is_cs2_running():
    """Проверяет, запущен ли процесс cs2.exe"""
    try:
        for process in psutil.process_iter(['name']):
            if process.info['name'] and process.info['name'].lower() == 'cs2.exe':
                return True
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return True

def load_config():
    """Загружает конфигурацию из config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Файл config.json не найден. Создаю стандартный конфиг...")
        default_config = {
            "application_id": "1393856315067203635",
            "statuses": [
                {
                    "state": "KensoUltra.lua",
                    "details": "◣   ◢"
                }
            ],
            "update_interval": 15,
            "config_check_interval": 5,
            "show": True
        }
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    except json.JSONDecodeError as e:
        print(f"Ошибка чтения config.json: {e}")
        return None

def get_config_modification_time():
    """Возвращает время последнего изменения config.json"""
    try:
        return os.path.getmtime('config.json')
    except OSError:
        return 0

def safe_rpc_connect(rpc, application_id):
    """Безопасное подключение RPC с обработкой ошибок"""
    try:
        rpc.connect()
        print("RPC подключен! CS2 запущена.")
        return True
    except Exception as e:
        print(f"Ошибка подключения RPC: {e}")
        return False

def safe_rpc_update(rpc, *args, **kwargs):
    """Безопасное обновление RPC статуса"""
    try:
        rpc.update(*args, **kwargs)
        return True
    except Exception as e:
        print(f"Ошибка обновления RPC: {e}")
        return False

def safe_rpc_close(rpc):
    """Безопасное закрытие RPC соединения"""
    try:
        if hasattr(rpc, 'sock_writer') and rpc.sock_writer is not None:
            rpc.close()
            print("RPC отключен.")
    except Exception as e:
        print(f"Ошибка при закрытии RPC: {e}")

def main():
    # Проверяем, не запущен ли уже другой экземпляр
    if is_already_running():
        print("❌ Программа уже запущена. Повторный запуск невозможен.")
        print("   Если вы уверены, что это ошибка, перезагрузите компьютер или завершите процесс вручную.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    
    print("✅ Уникальный экземпляр программы запущен.")
    
    # Проверяем, запущена ли CS2
    if not is_cs2_running():
        print("CS2 не запущена. RPC будет отключен.")
        return
    
    # Первоначальная загрузка конфигурации
    config = load_config()
    if config is None:
        return
    
    last_config_mod_time = get_config_modification_time()
    
    rpc = Presence(config["application_id"])
    
    try:
        # Пытаемся подключиться к RPC
        if not safe_rpc_connect(rpc, config["application_id"]):
            return
        
        # Инициализируем stt один раз при запуске RPC
        stt = time.time()
        
        current_status_index = 0
        statuses = config["statuses"]
        update_interval = config.get("update_interval", 15)
        config_check_interval = config.get("config_check_interval", 5)
        show_rpc = config.get("show", True)
        
        # Применяем первый статус если RPC включен
        if statuses and show_rpc:
            status = statuses[current_status_index]
            if safe_rpc_update(rpc, **status, start=stt):
                print(f"Статус установлен: {status.get('state', 'No state')}")
        elif not show_rpc:
            print("RPC отключен в настройках (show: false)")
        
        print("RPC запущен... Нажмите Ctrl+C для остановки.")
        
        last_config_check = time.time()
        last_cs2_check = time.time()
        cs2_check_interval = 10
        
        while True:
            current_time = time.time()
            
            # Проверяем, запущена ли CS2
            if current_time - last_cs2_check >= cs2_check_interval:
                if not is_cs2_running():
                    print("CS2 закрыта. Завершаем работу RPC.")
                    break
                last_cs2_check = current_time
            
            # Проверяем изменения в конфиге
            if current_time - last_config_check >= config_check_interval:
                current_mod_time = get_config_modification_time()
                
                if current_mod_time > last_config_mod_time:
                    print("Обнаружены изменения в config.json. Перезагружаем конфигурацию...")
                    new_config = load_config()
                    
                    if new_config is not None:
                        config = new_config
                        statuses = config["statuses"]
                        update_interval = config.get("update_interval", 15)
                        config_check_interval = config.get("config_check_interval", 5)
                        new_show_rpc = config.get("show", True)
                        
                        current_status_index = 0
                        
                        if statuses:
                            if new_show_rpc:
                                status = statuses[current_status_index]
                                if safe_rpc_update(rpc, **status, start=stt):
                                    print(f"Статус обновлен: {status.get('state', 'No state')}")
                            else:
                                safe_rpc_update(rpc, state="", details="")
                                print("RPC отключен в настройках (show: false)")
                        
                        show_rpc = new_show_rpc
                    
                    last_config_mod_time = current_mod_time
                
                last_config_check = current_time
            
            # Смена статусов
            if len(statuses) > 1 and show_rpc:
                time.sleep(update_interval)
                current_status_index = (current_status_index + 1) % len(statuses)
                status = statuses[current_status_index]
                if safe_rpc_update(rpc, **status, start=stt):
                    print(f"Статус изменен: {status.get('state', 'No state')}")
            else:
                time.sleep(min(config_check_interval, cs2_check_interval))

    except KeyboardInterrupt:
        print("RPC остановлен пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        safe_rpc_close(rpc)

if __name__ == "__main__":
    # АВТОМАТИЧЕСКИЙ ЗАПРОС ПРАВ АДМИНИСТРАТОРА ПРИ ЗАПУСКЕ
    if not elevate_privileges():
        print("Не удалось получить права администратора. Работа продолжается с текущими правами.")
    main()
import a2s
import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn
import re
import aiohttp
from typing import Dict, List, Any, Optional
import psutil
import threading
import time
import sys
import asyncio
from contextlib import asynccontextmanager

# Импортируем Rich для красивого логирования
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import print as rprint
import logging

# Настраиваем Rich логирование
logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])
logger = logging.getLogger("rich")
console = Console()

# Константы
A2S_TIMEOUT = 2.0  # Таймаут 2 секунды для всех a2s запросов
FILE_CHECK_INTERVAL = 5  # Проверка файла каждые 5 секунд (было 300)

# Глобальная переменная для контроля работы монитора
monitor_running = True

def check_cs2_process():
    """Проверяет, запущен ли процесс cs2.exe"""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == 'cs2.exe':
            console.print("✅ Процесс cs2.exe найден, приложение запускается...", style="green")
            return True
    
    console.print(
        Panel.fit(
            "❌ Процесс cs2.exe не найден!\n"
            "🚫 Приложение будет завершено.",
            title="[#ffffff]Критическая ошибка",
            border_style="red"
        )
    )
    return False

def monitor_cs2_process():
    """Мониторит процесс cs2.exe и завершает приложение если игра закрылась"""
    global monitor_running
    
    while monitor_running:
        cs2_found = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == 'cs2.exe':
                cs2_found = True
                break
        
        if not cs2_found:
            console.print(
                Panel.fit(
                    "❌ Процесс cs2.exe завершился!\n"
                    "🚫 FastAPI сервер будет остановлен.",
                    title="[#ffffff]Завершение работы",
                    border_style="red"
                )
            )
            time.sleep(2)
            os._exit(0)
        
        time.sleep(5)

def start_cs2_monitor():
    """Запускает мониторинг процесса cs2.exe в отдельном потоке"""
    monitor_thread = threading.Thread(target=monitor_cs2_process, daemon=True)
    monitor_thread.start()
    console.print("🔍 Мониторинг процесса cs2.exe запущен...", style="yellow")

# Проверяем наличие процесса cs2.exe перед запуском приложения
if not check_cs2_process():
    sys.exit(1)

# Запускаем мониторинг процесса
start_cs2_monitor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan контекст для управления жизненным циклом приложения"""
    # Запуск
    console.print("🚀 FastAPI приложение запускается...", style="green")
    # Запускаем мониторинг файла
    asyncio.create_task(file_monitor_loop())
    yield
    # Завершение
    global monitor_running
    monitor_running = False
    console.print("🛑 FastAPI приложение завершает работу...", style="yellow")

fastapi_app = FastAPI(title="Game Server Status API", lifespan=lifespan)

def log_server_request(server_ip: str, server_port: int, status: str, players: str = "0/0", map_name: str = "N/A", ver: str = "unknown"):
    """Красивое логирование запроса к серверу"""
    status_color = "green" if status == "Online" else "red"
    status_text = Text(status, style=status_color)
    table = Table(show_header=False, box=None, padding=0)
    table.add_column("")
    table.add_column("")
    table.add_row(f"{server_ip}:{server_port}: ", f"{status_text}: {players} | Map: {map_name} | Version: {ver}")
    console.print(Panel(table, title="📡 Запрос статуса сервера", border_style="blue"))

def log_startup():
    """Красивое логирование запуска приложения"""
    console.print(Panel.fit(
        "[#ffff44]Game Server Status API: "
        "[#6666ff]Сервер успешно запущен и готов к работе",
        title="[#ffffff]Запуск приложения (by kelix.me)",
        border_style="#ff6666"
    ))

def log_request(method: str, path: str, status_code: int, client_ip: str):
    """Красивое логирование HTTP запросов"""
    status_color = "green" if status_code < 400 else "red"
    status_text = Text(str(status_code), style=status_color)
    console.print(f"🌐 {client_ip} - \"{method} {path}\" {status_text}")

def log_error(error_msg: str, details: str = ""):
    """Красивое логирование ошибок"""
    console.print(
        Panel.fit(
            f"❌ {error_msg}\n"
            f"📝 {details}" if details else "",
            title="🚨 Ошибка",
            border_style="red"
        )
    )

def extract_build_number(version_str):
    """Извлекает номер билда из строки версии"""
    if not version_str:
        return 0
    numbers = re.findall(r'\d+', version_str)
    if numbers:
        try:
            return int(numbers[-1])
        except ValueError:
            return 0
    return 0

def is_server_updated(server_version, cs2_version):
    """Проверяет, обновлен ли сервер до последней версии"""
    if server_version == "unknown" or cs2_version == "unknown":
        return True
    server_build = extract_build_number(server_version)
    cs2_build = extract_build_number(cs2_version)
    return server_build >= cs2_build

def get_connect_status(server_version, cs2_version, server_status):
    """Определяет статус подключения на основе версий"""
    if server_status != "Online":
        return "offline"
    
    if server_version == "unknown" or cs2_version == "unknown":
        return "online"
    
    if is_server_updated(server_version, cs2_version):
        return "online"
    else:
        return "update"

async def get_server_info(server_ip: str, server_port: int) -> Dict[str, Any]:
    """Получение информации о сервере с таймаутом 2 секунды"""
    address = (server_ip, server_port)
    
    try:
        # Используем asyncio.wait_for для таймаута
        info = await asyncio.wait_for(
            a2s.ainfo(address),  # type: ignore
            timeout=A2S_TIMEOUT
        )
        
        cs2_latest_version = 'unknown'
        server_version = str(getattr(info, 'version', 'unknown')).strip()
        if server_version == 'unknown' or not server_version:
            server_version = "unknown"
        
        is_updated = is_server_updated(server_version, cs2_latest_version)
        connect_status = get_connect_status(server_version, cs2_latest_version, "Online")
        status = "Online"
        
        # Получаем список игроков с таймаутом
        try:
            players = await asyncio.wait_for(
                a2s.aplayers(address),  # type: ignore
                timeout=A2S_TIMEOUT
            )
            processed_players = []
            for player in players:
                processed_players.append({
                    'name': player.name or "Unknown",
                    'score': player.score or 0,
                    'duration': player.duration or 0,
                })
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Таймаут или ошибка при получении списка игроков {server_ip}:{server_port}: {e}")
            processed_players = []
        
        log_server_request(server_ip, server_port, status, f"{len(processed_players)}/{info.max_players}", info.map_name, info.version)
        
        return {
            "online": len(processed_players),
            "max_players": info.max_players,
            "map": info.map_name,
            "server_name": info.server_name,
            "status": status,
            "ip_port": f"{server_ip}:{server_port}",
            "players": processed_players,
            "version_server": server_version,
            "is_updated": is_updated,
            "status_connect": connect_status,
            "raw_info": {
                "protocol": info.protocol,
                "folder": info.folder,
                "game": info.game,
                "app_id": info.app_id,
                "player_count": info.player_count,
                "bot_count": info.bot_count,
                "server_type": info.server_type,
                "platform": info.platform,
                "password_protected": info.password_protected,
                "vac_enabled": info.vac_enabled,
                "version": info.version,
                "port": info.port,
                "steam_id": info.steam_id,
                "keywords": info.keywords,
                "ping": info.ping
            }
        }
        
    except asyncio.TimeoutError:
        error_msg = f"Таймаут {A2S_TIMEOUT}с при подключении к серверу {server_ip}:{server_port}"
        logger.error(error_msg)
        log_server_request(server_ip, server_port, "Offline")
        return {
            "online": 0,
            "max_players": 0,
            "map": "N/A",
            "server_name": "Сервер недоступен (таймаут)",
            "status": "Offline",
            "ip_port": f"{server_ip}:{server_port}",
            "players": [],
            "version_server": "unknown",
            "is_updated": False,
            "status_connect": "offline",
            "raw_info": None,
            "error": f"Timeout after {A2S_TIMEOUT}s"
        }
        
    except Exception as e:
        error_msg = f"Ошибка при подключении к серверу {server_ip}:{server_port}: {e}"
        logger.error(error_msg)
        log_server_request(server_ip, server_port, "Offline")
        return {
            "online": 0,
            "max_players": 0,
            "map": "N/A",
            "server_name": "Сервер недоступен",
            "status": "Offline",
            "ip_port": f"{server_ip}:{server_port}",
            "players": [],
            "version_server": "unknown",
            "is_updated": False,
            "status_connect": "offline",
            "raw_info": None,
            "error": str(e)
        }

async def process_servers_from_file():
    """Обрабатывает серверы из файла getserver.txt и создает JSON файл"""
    txt_file = "getserver.txt"
    json_file = "rawservers.json"
    
    if not os.path.exists(txt_file):
        return
    
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except Exception as e:
        console.print(f"❌ Ошибка чтения файла {txt_file}: {e}", style="red")
        return
    
    if not content:
        return
    
    console.print(f"📁 Обнаружен непустой файл {txt_file}, начинаю обработку...", style="yellow")
    
    # Парсим список серверов
    servers = []
    try:
        content_clean = content.replace("'", "").replace('"', "").replace(" ", "")
        server_entries = [s.strip() for s in content_clean.split(',') if s.strip()]
        
        for entry in server_entries:
            if ':' in entry:
                ip, port = entry.rsplit(':', 1)
                servers.append({
                    'ip': ip.strip(),
                    'port': int(port.strip())
                })
    except Exception as e:
        error_msg = f"Ошибка при парсинге файла {txt_file}: {e}"
        log_error(error_msg)
        console.print("❌ Содержимое файла getserver.txt НЕ будет очищено из-за ошибки", style="red")
        return
    
    if not servers:
        console.print("❌ Не удалось извлечь серверы из файла", style="red")
        return
    
    console.print(f"🔍 Обработка {len(servers)} серверов из файла...", style="yellow")
    
    # Параллельная обработка всех серверов
    tasks = [get_server_info(server["ip"], server["port"]) for server in servers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    servers_dict = {}
    for server, result in zip(servers, results):
        server_key = f"{server['ip']}:{server['port']}"
        if isinstance(result, Exception):
            servers_dict[server_key] = {
                "name": "Error",
                "ip": server["ip"],
                "port": server["port"],
                "error": f"Ошибка получения данных: {str(result)}"
            }
        else:
            servers_dict[server_key] = {
                "name": "CS2",
                "ip": server["ip"],
                "port": server["port"],
                "status": result["status"],
                "online": result["online"],
                "max_players": result["max_players"],
                "map": result["map"],
                "server_name": result["server_name"],
                "players": result["players"],
                "version_server": result["version_server"],
                "is_updated": result["is_updated"],
                "status_connect": result["status_connect"],
                "raw_info": result.get("raw_info"),
                "error": result.get("error")
            }
    
    # Сохраняем результат в JSON файл
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(servers_dict, f, ensure_ascii=False, indent=2)
        
        online_servers = sum(1 for server in servers_dict.values() if server.get("status") == "Online")
        console.print(f"✅ Файл {json_file} создан: {online_servers}/{len(servers)} серверов онлайн", style="green")
        
        # Очищаем исходный файл
        open(txt_file, 'w', encoding='utf-8').close()
        console.print(f"🗑️ Файл {txt_file} очищен, ожидаю новые запросы...", style="yellow")
        
    except Exception as e:
        error_msg = f"Ошибка при сохранении JSON файла: {e}"
        log_error(error_msg)
        console.print("❌ Содержимое файла getserver.txt НЕ будет очищено из-за ошибки", style="red")

async def file_monitor_loop():
    """Асинхронный мониторинг файла getserver.txt"""
    console.print("🔍 Асинхронный мониторинг файла getserver.txt запущен...", style="yellow")
    
    while monitor_running:
        try:
            await process_servers_from_file()
        except Exception as e:
            console.print(f"❌ Ошибка в мониторе файлов: {e}", style="red")
        
        await asyncio.sleep(FILE_CHECK_INTERVAL)

@fastapi_app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    
    log_request(
        request.method,
        request.url.path,
        response.status_code,
        request.client.host if request.client else "unknown"
    )
    
    # Добавляем заголовок с временем выполнения
    response.headers["X-Response-Time-Ms"] = str(int(duration_ms))
    return response

@fastapi_app.get("/")
async def root():
    logger.info("Получен запрос к корневому эндпоинту")
    return {"message": "Game Server Status API", "status": "online", "timeout": f"{A2S_TIMEOUT}s"}

@fastapi_app.get("/server/{server_ip}:{server_port}")
async def get_specific_server1(server_ip: str, server_port: int):
    """Получить информацию о конкретном сервере"""
    logger.info(f"Запрос информации о сервере {server_ip}:{server_port}")
    info = await get_server_info(server_ip, server_port)
    return {
        "name": "CS2",
        "ip": server_ip,
        "port": server_port,
        "status": info["status"],
        "online": info["online"],
        "max_players": info["max_players"],
        "map": info["map"],
        "server_name": info["server_name"],
        "players": info["players"],
        "version_server": info["version_server"],
        "is_updated": info["is_updated"],
        "status_connect": info["status_connect"],
        "raw_info": info.get("raw_info"),
        "error": info.get("error")
    }

@fastapi_app.get("/servers/{servers_list}")
async def get_multiple_servers(servers_list: str):
    """Получить информацию о нескольких серверах в одном ответе (JSON)"""
    logger.info(f"Запрос информации о нескольких серверах: {servers_list}")
    
    servers = []
    try:
        servers_str = servers_list.strip('{}')
        server_entries = [s.strip() for s in servers_str.split(',')]
        for entry in server_entries:
            if ':' in entry:
                ip, port = entry.rsplit(':', 1)
                servers.append({
                    'ip': ip.strip(),
                    'port': int(port.strip())
                })
    except Exception as e:
        error_msg = f"Неверный формат списка серверов: {e}"
        log_error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    console.print(f"🔍 Параллельная обработка {len(servers)} серверов...", style="yellow")
    
    # Параллельная обработка всех серверов
    tasks = [get_server_info(server["ip"], server["port"]) for server in servers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    servers_dict = {}
    for server, result in zip(servers, results):
        server_key = f"{server['ip']}:{server['port']}"
        if isinstance(result, Exception):
            servers_dict[server_key] = {
                "name": "Error",
                "ip": server["ip"],
                "port": server["port"],
                "error": f"Ошибка получения данных: {str(result)}"
            }
        else:
            servers_dict[server_key] = {
                "name": "CS2",
                "ip": server["ip"],
                "port": server["port"],
                "status": result["status"],
                "online": result["online"],
                "max_players": result["max_players"],
                "map": result["map"],
                "server_name": result["server_name"],
                "players": result["players"],
                "version_server": result["version_server"],
                "is_updated": result["is_updated"],
                "status_connect": result["status_connect"],
                "raw_info": result.get("raw_info"),
                "error": result.get("error")
            }
    
    online_servers = sum(1 for server in servers_dict.values() if server.get("status") == "Online")
    console.print(f"✅ Обработка завершена: {online_servers}/{len(servers)} серверов онлайн", style="green")
    return servers_dict

@fastapi_app.get("/servers_raw/{servers_list}")
async def get_multiple_servers_raw(servers_list: str):
    """Получить информацию о нескольких серверах в одном ответе (RAW текст)"""
    logger.info(f"Запрос RAW информации о нескольких серверах: {servers_list}")
    
    servers = []
    try:
        servers_str = servers_list.strip('{}')
        server_entries = [s.strip() for s in servers_str.split(',')]
        for entry in server_entries:
            if ':' in entry:
                ip, port = entry.rsplit(':', 1)
                servers.append({
                    'ip': ip.strip(),
                    'port': int(port.strip())
                })
    except Exception as e:
        error_msg = f"Неверный формат списка серверов: {e}"
        log_error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    console.print(f"🔍 Параллельная обработка {len(servers)} серверов (RAW)...", style="yellow")
    
    # Параллельная обработка всех серверов
    tasks = [get_server_info(server["ip"], server["port"]) for server in servers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    servers_dict = {}
    for server, result in zip(servers, results):
        server_key = f"{server['ip']}:{server['port']}"
        if isinstance(result, Exception):
            servers_dict[server_key] = {
                "name": "Error",
                "ip": server["ip"],
                "port": server["port"],
                "error": f"Ошибка получения данных: {str(result)}"
            }
        else:
            servers_dict[server_key] = {
                "name": "CS2",
                "ip": server["ip"],
                "port": server["port"],
                "status": result["status"],
                "online": result["online"],
                "max_players": result["max_players"],
                "map": result["map"],
                "server_name": result["server_name"],
                "players": result["players"],
                "version_server": result["version_server"],
                "is_updated": result["is_updated"],
                "status_connect": result["status_connect"],
                "raw_info": result.get("raw_info"),
                "error": result.get("error")
            }
    
    formatted_json = json.dumps(servers_dict, ensure_ascii=False, indent=2)
    online_servers = sum(1 for server in servers_dict.values() if server.get("status") == "Online")
    console.print(f"✅ RAW обработка завершена: {online_servers}/{len(servers)} серверов онлайн", style="green")
    return PlainTextResponse(formatted_json, media_type="text/plain")

@fastapi_app.get("/server_raw/{server_ip}:{server_port}")
async def get_specific_server_raw(server_ip: str, server_port: int):
    """Получить информацию о конкретном сервере в RAW формате"""
    logger.info(f"Запрос RAW информации о сервере {server_ip}:{server_port}")
    info = await get_server_info(server_ip, server_port)
    response_data = {
        "name": "CS2",
        "ip": server_ip,
        "port": server_port,
        "status": info["status"],
        "online": info["online"],
        "max_players": info["max_players"],
        "map": info["map"],
        "server_name": info["server_name"],
        "players": info["players"],
        "version_server": info["version_server"],
        "is_updated": info["is_updated"],
        "status_connect": info["status_connect"],
        "raw_info": info.get("raw_info"),
        "error": info.get("error")
    }
    formatted_json = json.dumps(response_data, ensure_ascii=False, indent=2)
    return PlainTextResponse(formatted_json, media_type="text/plain")

if __name__ == "__main__":
    log_startup()
    
    try:
        uvicorn.run(
            fastapi_app, 
            host="localhost", 
            port=13753, 
            log_config=None,
            timeout_keep_alive=5  # Уменьшаем keep-alive таймаут
        )
    except KeyboardInterrupt:
        console.print("🛑 Приложение завершено пользователем", style="yellow")
        monitor_running = False
    except Exception as e:
        console.print(f"🚫 Ошибка при работе сервера: {e}", style="red")
        monitor_running = False
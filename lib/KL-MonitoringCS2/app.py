import opengsq
import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn
import re
import aiohttp
from typing import Dict, List, Any
import psutil
import threading
import time
import sys
import asyncio
import socket

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

if not check_cs2_process():
    sys.exit(1)

start_cs2_monitor()

fastapi_app = FastAPI(title="Game Server Status API")

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
    if status_color == 'red':
        console.print(
            f"🌐 {client_ip} - \"{method} {path}\" {status_text}"
        )

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

async def get_server_info(server_ip, server_port):
    """Получает информацию о сервере используя opengsq"""
    try:
        source = opengsq.Source(server_ip, server_port, timeout=5.0)
        info = await source.get_info()
        
        # Парсим информацию о сервере
        if hasattr(info, 'version'):
            server_version = str(info.version).strip() # type: ignore
        elif isinstance(info, dict):
            server_version = str(info.get('version', 'unknown')).strip()
        else:
            server_version = "unknown"
            
        if not server_version or server_version == 'unknown':
            server_version = "unknown"
        
        if hasattr(info, 'map'):
            map_name = info.map
        elif isinstance(info, dict):
            map_name = info.get('map', 'N/A')
        else:
            map_name = 'N/A'
        
        if hasattr(info, 'max_players'):
            max_players = info.max_players
        elif isinstance(info, dict):
            max_players = info.get('max_players', 0)
        else:
            max_players = 0
        
        if hasattr(info, 'name'):
            server_name = info.name
        elif isinstance(info, dict):
            server_name = info.get('name', 'Unknown Server')
        else:
            server_name = 'Unknown Server'
        
        # Получаем количество игроков онлайн (без списка)
        online_players = 0
        try:
            players_raw = await source.get_players()
            online_players = len(players_raw) if players_raw else 0
        except Exception as e:
            logger.warning(f"Ошибка при получении количества игроков {server_ip}:{server_port}: {e}")
            online_players = 0
        
        status = "Online"
        
        log_server_request(
            server_ip, server_port, status, 
            f"{online_players}/{max_players}", 
            map_name, 
            server_version
        )
        
        # Объединяем всю информацию в единый JSON
        response_data = {
            "ip": server_ip,
            "port": server_port,
            "ip_port": f"{server_ip}:{server_port}",
            "name": server_name,
            "status": status,
            "online": online_players,
            "max_players": max_players,
            "map": map_name,
            "version": server_version,
            "protocol": getattr(info, 'protocol', 0) if hasattr(info, 'protocol') else (info.get('protocol', 0) if isinstance(info, dict) else 0),
            "folder": getattr(info, 'folder', '') if hasattr(info, 'folder') else (info.get('folder', '') if isinstance(info, dict) else ''),
            "game": getattr(info, 'game', '') if hasattr(info, 'game') else (info.get('game', '') if isinstance(info, dict) else ''),
            "app_id": getattr(info, 'appid', 0) if hasattr(info, 'appid') else (info.get('appid', 0) if isinstance(info, dict) else 0),
            "bot_count": getattr(info, 'bots', 0) if hasattr(info, 'bots') else (info.get('bots', 0) if isinstance(info, dict) else 0),
            "server_type": getattr(info, 'server_type', '') if hasattr(info, 'server_type') else (info.get('server_type', '') if isinstance(info, dict) else ''),
            "platform": getattr(info, 'environment', '') if hasattr(info, 'environment') else (info.get('environment', '') if isinstance(info, dict) else ''),
            "password_protected": getattr(info, 'password', False) if hasattr(info, 'password') else (info.get('password', False) if isinstance(info, dict) else False),
            "vac_enabled": getattr(info, 'vac', False) if hasattr(info, 'vac') else (info.get('vac', False) if isinstance(info, dict) else False),
            "steam_id": getattr(info, 'steamid', '') if hasattr(info, 'steamid') else (info.get('steamid', '') if isinstance(info, dict) else ''),
            "keywords": getattr(info, 'keywords', '') if hasattr(info, 'keywords') else (info.get('keywords', '') if isinstance(info, dict) else '')
        }
        
        return response_data
        
    except Exception as e:
        error_msg = f"Ошибка при подключении к серверу {server_ip}:{server_port}: {e}"
        logger.error(error_msg)
        log_server_request(server_ip, server_port, "Offline")
        
        return {
            "ip": server_ip,
            "port": server_port,
            "ip_port": f"{server_ip}:{server_port}",
            "name": "Сервер недоступен",
            "status": "Offline",
            "online": 0,
            "max_players": 0,
            "map": "N/A",
            "version": "unknown",
            "error": str(e)
        }

async def process_servers_from_file():
    """Обрабатывает серверы из файла getserver.txt и создает JSON файл"""
    txt_file = "getserver.txt"
    json_file = "rawservers.json"
    
    if not os.path.exists(txt_file):
        return
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    if not content:
        return
    
    console.print(f"📁 Обнаружен непустой файл {txt_file}, начинаю обработку...", style="yellow")
    
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
        console.print("❌ Содержимое файла getserver.txt НЕ будет очищено из-за ошибки", style="red")
        return
    
    console.print(f"🔍 Обработка {len(servers)} серверов из файла...", style="yellow")
    
    servers_dict = {}
    for server in servers:
        try:
            info = await get_server_info(server["ip"], server["port"])
            server_key = f"{server['ip']}:{server['port']}"
            servers_dict[server_key] = info
        except Exception as e:
            server_key = f"{server['ip']}:{server['port']}"
            servers_dict[server_key] = {
                "ip": server["ip"],
                "port": server["port"],
                "ip_port": server_key,
                "error": f"Ошибка получения данных: {str(e)}"
            }
    
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(servers_dict, f, ensure_ascii=False, indent=2)
        
        online_servers = sum(1 for server in servers_dict.values() if server.get("status") == "Online")
        console.print(f"✅ Файл {json_file} создан: {online_servers}/{len(servers)} серверов онлайн", style="green")
        
        open(txt_file, 'w', encoding='utf-8').close()
        console.print(f"🗑️ Файл {txt_file} очищен, ожидаю новые запросы...", style="yellow")
        
    except Exception as e:
        error_msg = f"Ошибка при сохранении JSON файла: {e}"
        log_error(error_msg)
        console.print("❌ Содержимое файла getserver.txt НЕ будет очищено из-за ошибки", style="red")

def start_file_monitor():
    """Запускает мониторинг файла в отдельном потоке"""
    def monitor_loop():
        while monitor_running:
            try:
                asyncio.run(process_servers_from_file())
            except Exception as e:
                console.print(f"❌ Ошибка в мониторе файлов: {e}", style="red")
            
            time.sleep(300)
    
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    console.print("🔍 Мониторинг файла getserver.txt запущен...", style="yellow")

@fastapi_app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    log_request(
        request.method,
        request.url.path,
        response.status_code,
        request.client.host if request.client else "unknown"
    )
    return response

@fastapi_app.get("/")
async def root():
    logger.info("Получен запрос к корневому эндпоинту")
    return {"message": "Game Server Status API", "status": "online"}

@fastapi_app.get("/server/{server_ip}:{server_port}")
async def get_specific_server1(server_ip: str, server_port: int):
    """Получить информацию о конкретном сервере"""
    logger.info(f"Запрос информации о сервере {server_ip}:{server_port}")
    return await get_server_info(server_ip, server_port)

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
    
    console.print(f"🔍 Обработка {len(servers)} серверов...", style="yellow")
    servers_dict = {}
    for server in servers:
        try:
            info = await get_server_info(server["ip"], server["port"])
            server_key = f"{server['ip']}:{server['port']}"
            servers_dict[server_key] = info
        except Exception as e:
            server_key = f"{server['ip']}:{server['port']}"
            servers_dict[server_key] = {
                "ip": server["ip"],
                "port": server["port"],
                "ip_port": server_key,
                "error": f"Ошибка получения данных: {str(e)}"
            }
    
    online_servers = sum(1 for server in servers_dict.values() if server.get("status") == "Online")
    console.print(f"✅ Обработка завершена: {online_servers}/{len(servers)} серверов онлайн", style="green")
    return servers_dict

@fastapi_app.get("/servers_raw/{servers_list}")
async def get_multiple_servers_raw(servers_list: str):
    """Получить информацию о нескольких серверах в одном ответе (Plain Text)"""
    logger.info(f"Запрос RAW информации о нескольких серверах: {servers_list}")
    result = await get_multiple_servers(servers_list)
    formatted_json = json.dumps(result, ensure_ascii=False, indent=2)
    return PlainTextResponse(formatted_json, media_type="text/plain")

@fastapi_app.get("/server_raw/{server_ip}:{server_port}")
async def get_specific_server_raw(server_ip: str, server_port: int):
    """Получить информацию о конкретном сервере в Plain Text формате"""
    logger.info(f"Запрос RAW информации о сервере {server_ip}:{server_port}")
    result = await get_specific_server1(server_ip, server_port)
    formatted_json = json.dumps(result, ensure_ascii=False, indent=2)
    return PlainTextResponse(formatted_json, media_type="text/plain")

if __name__ == "__main__":
    log_startup()
    start_file_monitor()
    try:
        uvicorn.run(fastapi_app, host="localhost", port=13753, log_config=None)
    except KeyboardInterrupt:
        console.print("🛑 Приложение завершено пользователем", style="yellow")
        monitor_running = False
    except Exception as e:
        console.print(f"🚫 Ошибка при работе сервера: {e}", style="red")
        monitor_running = False
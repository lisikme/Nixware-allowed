import asyncio
import aiofiles
import json
import time
import psutil
import subprocess
import threading
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import requests
from urllib.parse import urljoin
def set_play_false():
    """Устанавливает PLAY: false в config.json"""
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            config["PLAY"] = False
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("Установлено PLAY: false в config.json")
        else:
            print("Файл config.json не найден, создаем новый")
            config = {"PLAY": False, "URL": ""}
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка при установке PLAY: false: {e}")
def download_images():
    """Функция для скачивания изображений"""
    file_url = "https://raw.githubusercontent.com/lisikme/live.ketaru.com/refs/heads/web/list.js"
    base_image_url = "https://raw.githubusercontent.com/lisikme/live.ketaru.com/web/img/"
    local_dir = "./img/"
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        content = response.text
        image_paths = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('//'):
                continue
            if 'img/' in line and (line.endswith('.png"') or line.endswith('.png",')):
                img_path = line.replace('"', '').replace(',', '').strip()
                image_paths.append(img_path)
        print(f"Найдено {len(image_paths)} изображений для скачивания")
        downloaded_count = 0
        skipped_count = 0
        for img_path in image_paths:
            img_filename = os.path.basename(img_path)
            local_path = os.path.join(local_dir, img_filename)
            if os.path.exists(local_path):
                print(f"Пропущено (уже существует): {img_filename}")
                skipped_count += 1
                continue
            try:
                img_url = urljoin(base_image_url, img_filename)
                img_response = requests.get(img_url)
                img_response.raise_for_status()
                with open(local_path, 'wb') as f:
                    f.write(img_response.content)
                downloaded_count += 1
                print(f"Скачано: {img_filename}")
            except requests.exceptions.RequestException as e:
                print(f"Ошибка при скачивании {img_filename}: {e}")
            except Exception as e:
                print(f"Ошибка при сохранении {img_filename}: {e}")
        print(f"\nРезультат:")
        print(f"Скачано: {downloaded_count}")
        print(f"Пропущено (уже существуют): {skipped_count}")
        print(f"Всего обработано: {downloaded_count + skipped_count} из {len(image_paths)}")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке файла: {e}")
    except Exception as e:
        print(f"Общая ошибка: {e}")
async def async_main():
    while True:
        try:
            async def load_config():
                async with aiofiles.open('config.json', 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content)
            FFMPEG_BIN = "ffmpeg"
            def is_cs2_running():
                """Проверяет, запущен ли процесс cs2.exe"""
                for process in psutil.process_iter(['name']):
                    if process.info['name'] and process.info['name'].lower() == 'cs2.exe':
                        return True
                return False
            class AsyncAudioPlayer:
                def __init__(self):
                    self.audio_thread = None
                    self.ffmpeg_process = None
                    self.current_url = None
                    self.current_volume = 1.0
                    self.is_playing = False
                    self.shutdown_flag = asyncio.Event()
                    self.config_check_task = None
                    self.audio_task = None
                    self.executor = ThreadPoolExecutor(max_workers=2)
                    self.restart_event = asyncio.Event()
                    self.last_config = None
                async def create_ffmpeg_process(self, url):
                    """Асинхронно создает процесс ffmpeg с скрытой консолью"""
                    loop = asyncio.get_event_loop()
                    command = [
                        FFMPEG_BIN,
                        '-i', url,
                        '-f', 's16le',
                        '-ar', '44100', 
                        '-ac', '2',
                        '-reconnect', '1',
                        '-reconnect_streamed', '1',
                        '-reconnect_delay_max', '5',
                        '-loglevel', 'quiet',  # Убираем лишние логи
                        '-'
                    ]
                    try:
                        startupinfo = None
                        if sys.platform == "win32":
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = 0  # SW_HIDE - скрыть окно
                        process = await loop.run_in_executor(
                            self.executor, 
                            lambda: subprocess.Popen(
                                command, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,  # Добавляем для избежания блокировок
                                bufsize=10**6,
                                startupinfo=startupinfo,  # Используем startupinfo для скрытия
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # Дополнительный флаг для Windows
                            )
                        )
                        return process
                    except Exception as e:
                        print(f"Ошибка создания ffmpeg процесса: {e}")
                        return None
                def set_volume(self, volume_percent):
                    """Устанавливает громкость"""
                    self.current_volume = max(0.0, min(1.0, volume_percent / 100.0))
                    print(f"Громкость установлена на {volume_percent}%")
                def apply_volume(self, data):
                    """Применяет громкость к аудиоданным"""
                    if self.current_volume == 1.0:
                        return data
                    import array
                    audio_data = array.array('h', data)
                    for i in range(len(audio_data)):
                        audio_data[i] = int(audio_data[i] * self.current_volume)
                    return audio_data.tobytes()
                async def start_playback(self, url):
                    """Начинает воспроизведение асинхронно"""
                    await self.stop_playback()
                    print(f"Асинхронный запуск воспроизведения: {url}")
                    self.ffmpeg_process = await self.create_ffmpeg_process(url)
                    if not self.ffmpeg_process:
                        print("Не удалось создать ffmpeg процесс")
                        return False
                    self.current_url = url
                    self.is_playing = True
                    if not self.audio_task or self.audio_task.done():
                        self.audio_task = asyncio.create_task(self.audio_playback_loop())
                    print("Воспроизведение успешно запущено")
                    return True
                async def stop_playback(self):
                    """Останавливает воспроизведение асинхронно"""
                    self.is_playing = False
                    if self.ffmpeg_process:
                        try:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                self.executor, 
                                lambda: self.ffmpeg_process.terminate() # type: ignore
                            )
                            await asyncio.sleep(0.1)  # Даем время на завершение
                        except Exception as e:
                            print(f"Ошибка при остановке ffmpeg: {e}")
                        finally:
                            self.ffmpeg_process = None
                    print("Воспроизведение остановлено")
                async def audio_playback_loop(self):
                    """Асинхронный цикл воспроизведения аудио"""
                    import pyaudio
                    p = pyaudio.PyAudio()
                    stream = None
                    try:
                        stream = p.open(
                            format=pyaudio.paInt16,
                            channels=2,
                            rate=44100,
                            output=True
                        )
                        while self.is_playing and self.ffmpeg_process:
                            try:
                                loop = asyncio.get_event_loop()
                                data = await loop.run_in_executor(
                                    self.executor,
                                    lambda: self.ffmpeg_process.stdout.read(4096) # type: ignore
                                )
                                if not data:
                                    print("Аудиопоток завершился")
                                    break
                                data_with_volume = self.apply_volume(data)
                                await loop.run_in_executor(
                                    self.executor,
                                    lambda: stream.write(data_with_volume)
                                )
                                await asyncio.sleep(0.001)
                            except Exception as e:
                                print(f"Ошибка в аудио loop: {e}")
                                break
                    except Exception as e:
                        print(f"Ошибка инициализации аудио: {e}")
                    finally:
                        if stream:
                            stream.stop_stream()
                            stream.close()
                        p.terminate()
                        self.is_playing = False
                        print("Аудио loop завершен")
                async def check_and_apply_config(self):
                    """Асинхронно проверяет и применяет конфигурацию"""
                    config = await load_config()
                    if config["PLAY"] and not self.is_playing:
                        asyncio.create_task(self.start_playback(config["URL"]))
                    elif not config["PLAY"] and self.is_playing:
                        await self.stop_playback()
                    elif config["PLAY"] and self.is_playing and config["URL"] != self.current_url:
                        print(f"URL изменился, переключаемся на: {config['URL']}")
                        asyncio.create_task(self.start_playback(config["URL"]))
                    if "VOLUME" in config:
                        volume = config["VOLUME"]
                        if volume != self.current_volume * 100:
                            self.set_volume(volume)
                    self.last_config = config
                async def config_monitor_loop(self):
                    """Цикл мониторинга конфигурации"""
                    while not self.shutdown_flag.is_set():
                        try:
                            await self.check_and_apply_config()
                            await asyncio.sleep(0.5)  # Проверяем каждые 500ms
                        except Exception as e:
                            print(f"Ошибка в config monitor: {e}")
                            await asyncio.sleep(1)
                async def run(self):
                    self.config_check_task = asyncio.create_task(self.config_monitor_loop())
                    try:
                        await self.shutdown_flag.wait()
                    except asyncio.CancelledError:
                        pass
                    finally:
                        if self.config_check_task:
                            self.config_check_task.cancel()
                        if self.audio_task:
                            self.audio_task.cancel()
                        await self.stop_playback()
                        self.executor.shutdown(wait=False)
            async def main_async():
                if not is_cs2_running():
                    print("CS2 не запущен. Завершение работы.")
                    os._exit(0)
                player = AsyncAudioPlayer()
                try:
                    player_task = asyncio.create_task(player.run())
                    while True:
                        if not is_cs2_running():
                            print("CS2 закрыт. Завершение работы.")
                            player.shutdown_flag.set()
                            await asyncio.sleep(1)  # Даем время на корректное завершение
                            os._exit(0)
                        await asyncio.sleep(2)  # Проверяем каждые 2 секунды
                    await player_task
                except KeyboardInterrupt:
                    print("Завершение работы...")
                    player.shutdown_flag.set()
                except Exception as e:
                    print(f"Ошибка в main: {e}")
                finally:
                    player.shutdown_flag.set()
            await main_async()
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            await asyncio.sleep(5)
if __name__ == "__main__":
    print("Установка PLAY: false в config.json...")
    set_play_false()
    print("Запуск загрузки изображений...")
    download_images()
    print("Загрузка изображений завершена. Запуск основного приложения...")
    asyncio.run(async_main())
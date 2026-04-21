import os
import glob
import asyncio
import yaml
import time
import platform
import subprocess
import logging
import sys
import signal
import atexit
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from tqdm import tqdm

from core.exporter import ProxyExporter
from core.fetcher import ProxyFetcher
from core.parser import ProxyParser
from core.checker import ProxyChecker

# === ОТКЛЮЧАЕМ СПАМ ОТ БИБЛИОТЕК ===
logging.getLogger("singbox2proxy").setLevel(logging.CRITICAL)
logging.getLogger("curl_cffi").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.CRITICAL)

os.makedirs("logs", exist_ok=True)
logger.add("logs/checker.log", rotation="5 MB", level="INFO")


def kill_zombie_singbox():
    """Жестко убивает все процессы sing-box."""
    try:
        current_os = platform.system().lower()
        if current_os == "windows":
            # Используем CREATE_NO_WINDOW, чтобы консоль taskkill не моргала
            subprocess.run(["taskkill", "/F", "/T", "/IM", "sing-box.exe"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                           )
        else:
            subprocess.run(["pkill", "-9", "-f", "sing-box"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# === РЕГИСТРИРУЕМ ОБРАБОТЧИКИ ОСТАНОВКИ ===
# 1. При штатном выходе из программы
atexit.register(kill_zombie_singbox)


# 2. При нажатии CTRL+C в терминале или мягкой остановке
def handle_exit(signum, frame):
    print("\n\n[!] Получен сигнал остановки! Убиваем процессы sing-box...")
    kill_zombie_singbox()
    os._exit(0)


try:
    signal.signal(signal.SIGINT, handle_exit)  # Перехват CTRL+C
    signal.signal(signal.SIGTERM, handle_exit)  # Перехват программного завершения
    if platform.system().lower() == "windows":
        signal.signal(signal.SIGBREAK, handle_exit)
except AttributeError:
    pass


def setup_singbox_path():
    singbox_dirs = [d for d in glob.glob("sing-box*") if os.path.isdir(d)]
    if singbox_dirs:
        singbox_dir = os.path.abspath(singbox_dirs[0])
        os.environ["PATH"] = singbox_dir + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"Sing-box path attached: {singbox_dir}")


async def fetch_and_parse_source(src, fetcher, parser):
    try:
        content = await fetcher.fetch_one(src['url'])
        if content:
            proxies = parser.parse_with_metadata(content, src['name'])
            logger.info(f"Extracted {len(proxies)} from {src['name']}")
            return proxies
    except Exception as e:
        logger.warning(f"Error processing {src['name']}: {e}")
    return []


async def main():
    logger.info("Cleaning up old sing-box processes...")
    kill_zombie_singbox()
    time.sleep(1)

    setup_singbox_path()

    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info("=== Starting FurProxy Engine ===")

    fetcher = ProxyFetcher()
    parser = ProxyParser()
    all_extracted = []

    print("[*] Асинхронная загрузка подписок...")
    sources = config.get('sources', [])

    tasks = [fetch_and_parse_source(src, fetcher, parser) for src in sources]
    results_lists = await asyncio.gather(*tasks)

    for proxies in results_lists:
        all_extracted.extend(proxies)

    unique_map = {p['url']: p for p in all_extracted}
    unique_proxies = list(unique_map.values())

    print(f"[*] Собрано уникальных прокси: {len(unique_proxies)}\n")

    if not unique_proxies:
        print("[-] Прокси не найдены. Выход.")
        return

    checker = ProxyChecker(
        timeout=config.get('timeout', 5),
        test_url=config.get('test_url', "https://api.myip.com")
    )

    max_threads = min(config.get('threads', 30), 50)
    print(f"[*] Запуск проверки | Потоков: {max_threads} | Таймаут: {checker.timeout}с.")

    results = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(executor, checker.check, p)
            for p in unique_proxies
        ]

        alive_count = 0
        total = len(futures)

        # Выводим явно в sys.stdout, чтобы PyCharm не тупил с потоками
        pbar = tqdm(
            asyncio.as_completed(futures),
            total=total,
            desc="ЖИВЫЕ: 0",
            file=sys.stdout,
            dynamic_ncols=True,
            # Измененный формат: убрали postfix, используем только desc
            bar_format="Прогресс: {percentage:3.0f}% |{bar}| {desc} | {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )

        for f in pbar:
            result = await f

            if result['status'] == 'alive':
                alive_count += 1
                cc = result.get('cc', '??')
                ping = result.get('latency', 0)
                source = result.get('source_name', 'Unknown')
                name = result.get('orig_name', 'Unnamed')[:30]

                # Формируем строку и выводим её с принудительным сбросом буфера
                msg = f"[+] {cc} | {ping}ms | [{source}] {name}"
                pbar.write(msg)
                sys.stdout.flush()  # Заставляем PyCharm отрисовать текст НЕМЕДЛЕННО

                # Обновляем счетчик
                pbar.set_description(f"ЖИВЫЕ: {alive_count}")

            results.append(result)

    working_proxies = [r for r in results if r['status'] == "alive"]

    print(f"\n[✓] Проверка завершена! Найдено рабочих узлов: {len(working_proxies)}")

    exporter = ProxyExporter(output_dir="results")
    exporter.save_all(working_proxies)
    print("[✓] Файлы успешно сохранены в папку /results/")

    kill_zombie_singbox()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Обрабатывается внутри signal

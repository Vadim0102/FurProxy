import os
import glob
import asyncio
import yaml
import time
import platform
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from tqdm import tqdm

from core.exporter import ProxyExporter
from core.fetcher import ProxyFetcher
from core.parser import ProxyParser
from core.checker import ProxyChecker

# === ГЛУШИМ ВСЕ ЛОГИ ОТ БИБЛИОТЕК ===
logging.getLogger().setLevel(logging.CRITICAL)
for lib in ["singbox2proxy", "curl_cffi", "urllib3"]:
    l = logging.getLogger(lib)
    l.setLevel(logging.CRITICAL)
    l.propagate = False
    l.handlers = []

os.makedirs("logs", exist_ok=True)
logger.add("logs/checker.log", rotation="5 MB", level="INFO")


def kill_zombie_singbox():
    try:
        if platform.system().lower() == "windows":
            subprocess.run(["taskkill", "/F", "/IM", "sing-box.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "sing-box"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def setup_singbox_path():
    singbox_dirs = [d for d in glob.glob("sing-box*") if os.path.isdir(d)]
    if singbox_dirs:
        os.environ["PATH"] = os.path.abspath(singbox_dirs[0]) + os.pathsep + os.environ.get("PATH", "")


# Асинхронная функция для одновременного парсинга
async def fetch_and_parse(fetcher, parser, src):
    content = await fetcher.fetch_one(src['url'])
    if content:
        return parser.parse_with_metadata(content, src['name'])
    return []


async def main():
    kill_zombie_singbox()
    time.sleep(1)
    setup_singbox_path()

    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print("\n[*] Загрузка и парсинг списков...")
    fetcher = ProxyFetcher()
    parser = ProxyParser()
    
    # === 1. АСИНХРОННЫЙ ПАРСИНГ (Молниеносно) ===
    tasks = [fetch_and_parse(fetcher, parser, src) for src in config.get('sources', [])]
    results_lists = await asyncio.gather(*tasks)
    
    all_extracted = []
    for proxies in results_lists:
        all_extracted.extend(proxies)

    unique_map = {p['url']: p for p in all_extracted}
    unique_proxies = list(unique_map.values())

    print(f"[*] Собрано уникальных прокси: {len(unique_proxies)}\n")

    if not unique_proxies:
        print("[-] Прокси не найдены. Выход.")
        return

    # Задаем таймаут 8 секунд, чтобы узлы успели ответить
    checker = ProxyChecker(
        timeout=config.get('timeout', 8),
        test_url=config.get('test_url', "http://ip-api.com/json") 
    )

    max_threads = min(config.get('threads', 40), 60)
    print(f"[*] Запуск проверки | Потоков: {max_threads} | Таймаут: {checker.timeout}с.\n")

    results = []
    alive_count = 0

    # === 2. МНОГОПОТОЧНАЯ ПРОВЕРКА ===
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, checker.check, p) for p in unique_proxies]

        pbar = tqdm(
            asyncio.as_completed(futures),
            total=len(futures),
            desc="Прогресс | живые: 0",
            unit="шт",
            dynamic_ncols=True,
            bar_format="{desc} | {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )

        for f in pbar:
            result = await f

            if result['status'] == 'alive':
                alive_count += 1
                cc = result.get('cc', '??')
                ping = result.get('latency', 0)
                source = result.get('source_name', 'Unknown')
                name = result.get('orig_name', 'Unnamed')[:30]

                # tqdm.write ВАЖЕН! Он выводит текст, не разрывая ползунок
                tqdm.write(f"[+] {cc} | {ping}ms | [{source}] {name}")

            results.append(result)
            pbar.set_description_str(f"Прогресс | живые: {alive_count}")

    # === 3. СОХРАНЕНИЕ ===
    working_proxies = [r for r in results if r['status'] == "alive"]
    print(f"\n[✓] Готово! Сохранено рабочих узлов: {len(working_proxies)}")

    exporter = ProxyExporter(output_dir="results")
    exporter.save_all(working_proxies)
    
    kill_zombie_singbox()


if __name__ == "__main__":
    asyncio.run(main())

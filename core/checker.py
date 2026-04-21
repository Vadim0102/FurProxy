import time
from loguru import logger
from singbox2proxy import SingBoxProxy


class ProxyChecker:
    def __init__(self, timeout=10, test_url="https://api.myip.com"):
        self.timeout = timeout
        self.test_url = test_url

    def check(self, proxy_dict: dict):
        proxy_url = proxy_dict['url']
        proxy = None

        try:
            # Запускаем sing-box
            proxy = SingBoxProxy(proxy_url)

            start_time = time.time()
            # Проверяем (внутри библиотеки есть requests/httpx)
            response = proxy.request("GET", self.test_url, timeout=self.timeout)
            end_time = time.time()

            if response and response.status_code == 200:
                data = response.json()
                proxy_dict.update({
                    "status": "alive",
                    "country": data.get("country", "Unknown"),
                    "cc": data.get("cc", "??"),
                    "latency": int((end_time - start_time) * 1000)
                })
                return proxy_dict

        except Exception as e:
            # Сюда падают недоступные прокси и ошибки плагинов (obfs, v2ray-plugin)
            pass

        finally:
            # САМОЕ ВАЖНОЕ: Жестко гасим процесс sing-box!
            if proxy is not None:
                try:
                    if hasattr(proxy, 'stop'):
                        proxy.stop()
                    elif hasattr(proxy, 'close'):
                        proxy.close()
                except Exception:
                    pass

        proxy_dict["status"] = "dead"
        return proxy_dict

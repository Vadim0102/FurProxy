import time
from loguru import logger
from singbox2proxy import SingBoxProxy

class ProxyChecker:
    def __init__(self, timeout=8, test_url="http://ip-api.com/json"):
        # Увеличили таймаут до 8 секунд и перевели на HTTP для стабильности
        self.timeout = timeout
        self.test_url = test_url

    def check(self, proxy_dict: dict):
        proxy_url = proxy_dict['url']
        proxy = None
        
        try:
            proxy = SingBoxProxy(proxy_url)
            start_time = time.time()
            response = proxy.request("GET", self.test_url, timeout=self.timeout)
            end_time = time.time()

            # ip-api.com возвращает 200 OK и JSON даже если лимит исчерпан, 
            # поэтому проверяем "status": "success"
            if response and response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    proxy_dict.update({
                        "status": "alive",
                        "country": data.get("country", "Unknown"),
                        "cc": data.get("countryCode", "??"), # У ip-api ключ называется countryCode
                        "latency": int((end_time - start_time) * 1000)
                    })
                    return proxy_dict
                    
        except Exception:
            # Игнорируем любые ошибки (таймауты, недоступность)
            pass
            
        finally:
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
    
import re
import base64
import binascii
import urllib.parse

from loguru import logger


class ProxyParser:
    def __init__(self):
        # Группируем так, чтобы match возвращал всю ссылку
        self.proxy_pattern = re.compile(
            r'((?:vmess|vless|ss|ssr|trojan|hy2|hysteria2?|tuic|wg)://[^\s\"\'<>]+)',
            re.IGNORECASE
        )

    def _fix_padding(self, data: str) -> str:
        data = data.strip()
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return data

    def _safe_base64_decode(self, content: str) -> str:
        try:
            decoded_bytes = base64.b64decode(self._fix_padding(content), validate=False)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return content

    def parse_with_metadata(self, raw_content, source_name):
        proxies = []
        decoded_content = self._safe_base64_decode(raw_content)
        found_links = self.proxy_pattern.findall(decoded_content)

        # Если не нашли, пробуем построчно (двойной Base64)
        if not found_links:
            for line in raw_content.splitlines():
                inner = self._safe_base64_decode(line.strip())
                found_links.extend(self.proxy_pattern.findall(inner))

        for link in found_links:
            orig_name = "Unnamed"
            clean_url = link

            if '#' in link:
                clean_url, orig_name = link.split('#', 1)
                orig_name = urllib.parse.unquote(orig_name).strip()

            proxies.append({
                "url": clean_url,
                "orig_name": orig_name,
                "source_name": source_name,
                "protocol": clean_url.split('://')[0].lower()
            })

        return proxies

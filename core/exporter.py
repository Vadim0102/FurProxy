import os
import hashlib
import json
from datetime import datetime
from collections import Counter
from core.geo_config import is_service_supported

class ProxyExporter:
    def __init__(self, output_dir="results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _format_line(self, p):
        # Формат: vless://...#[US] [VPN-Fail] My-Super-Server (150ms)
        cc = p.get('cc', '??')
        return f"{p['url']}#[{cc}] [{p['source_name']}] {p['orig_name']} ({p.get('latency', 0)}ms)\n"

    def _generate_header(self, proxies, title):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        protocols = Counter(p['protocol'] for p in proxies)
        countries = Counter(p.get('cc', '??') for p in proxies)
        sources = Counter(p['source_name'] for p in proxies)

        header =[
            f"# ==========================================",
            f"# Title: {title}",
            f"# Generated: {now}",
            f"# Total Working Nodes: {len(proxies)}",
            f"# ==========================================",
            f"# Protocols: {dict(protocols)}",
            f"# Sources: {dict(sources)}",
            f"# Top Countries: {dict(countries.most_common(5))}",
            f"# ==========================================\n"
        ]
        return "\n".join(header)

    def save_all(self, working_proxies):
        # 1. По пингу (от быстрых к медленным)
        by_ping = sorted(working_proxies, key=lambda x: x.get('latency', 9999))
        self._write_file("nodes_by_ping.txt", by_ping, "Sorted by Latency (Fastest First)")

        # 2. По стране (группировка)
        by_country = sorted(working_proxies, key=lambda x: (x.get('cc', '??'), x.get('latency', 9999)))
        self._write_file("nodes_by_country.txt", by_country, "Sorted by Country Code")

        # 3. Premium/AI Supported (США, Европа и т.д.)
        premium_only =[p for p in by_ping if is_service_supported(p.get('cc', ''))]
        self._write_file("nodes_premium_services.txt", premium_only, "Premium Services & AI Supported")

        # 4. JSON Summary
        self._save_summary(working_proxies)

    def _write_file(self, filename, proxies, title):
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._generate_header(proxies, title))
            for p in proxies:
                f.write(self._format_line(p))

    def _save_summary(self, proxies):
        # Считаем хэш только по самим ссылкам (url), чтобы изменения в пинге не меняли хэш
        all_urls = "".join(sorted([p['url'] for p in proxies])).encode()
        checksum = hashlib.sha256(all_urls).hexdigest()

        summary = {
            "last_update": datetime.now().isoformat(),
            "total_working": len(proxies),
            "checksum_sha256": checksum,
            "stats": {
                "protocols": dict(Counter(p['protocol'] for p in proxies)),
                "countries": dict(Counter(p.get('cc', '??') for p in proxies))
            }
        }

        with open(os.path.join(self.output_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=4)

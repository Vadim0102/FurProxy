# Используем легкий образ Python
FROM python:3.11-slim

# Устанавливаем системные утилиты:
# curl (для скачивания ядра), procps (для команды pkill), ca-certificates (для SSL)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl procps ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Скачиваем стабильное ядро sing-box для Linux (версия 1.8.11, amd64)
# Кладем его в /usr/local/bin, чтобы система видела команду 'sing-box' глобально
RUN curl -fsSL -o sing-box.tar.gz https://github.com/SagerNet/sing-box/releases/download/v1.8.11/sing-box-1.8.11-linux-amd64.tar.gz && \
    tar -xzf sing-box.tar.gz && \
    mv sing-box-1.8.11-linux-amd64/sing-box /usr/local/bin/ && \
    chmod +x /usr/local/bin/sing-box && \
    rm -rf sing-box*

# Задаем рабочую директорию
WORKDIR /app

# Сначала копируем только requirements.txt (для кэширования слоев Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта
COPY . .

# Команда, которая запустится при старте контейнера
CMD ["python", "main.py"]

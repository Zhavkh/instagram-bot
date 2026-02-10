FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование зависимостей
COPY requirements_bot.txt .
RUN pip install --no-cache-dir python-telegram-bot==20.7
RUN pip install --no-cache-dir -r requirements_bot.txt

# Копирование кода
COPY instagram_follower_bot.py .
COPY telegram_control_bot.py .

# Создание директории для данных
RUN mkdir -p /app/data

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Запуск
CMD ["python", "telegram_control_bot.py"]

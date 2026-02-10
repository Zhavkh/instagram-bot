#!/bin/bash

# 🚀 Автоматический деплой Instagram бота на VPS
# Этот скрипт автоматизирует установку и настройку

set -e

echo "=================================="
echo "Instagram Bot VPS Deployment"
echo "=================================="
echo ""

# Проверка root
if [ "$EUID" -eq 0 ]; then 
   echo "⚠️  Не запускайте этот скрипт от root!"
   echo "Используйте: bash deploy.sh"
   exit 1
fi

# Обновление системы
echo "📦 Обновление системы..."
sudo apt update
sudo apt upgrade -y

# Установка Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Установка Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo "✅ Docker уже установлен"
fi

# Установка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Установка Docker Compose..."
    sudo apt install docker-compose -y
else
    echo "✅ Docker Compose уже установлен"
fi

# Создание директории
echo "📁 Создание директории..."
mkdir -p ~/instagram-bot
cd ~/instagram-bot

# Проверка наличия файлов
if [ ! -f "telegram_control_bot.py" ]; then
    echo "❌ Файлы бота не найдены!"
    echo "Загрузите файлы в ~/instagram-bot/"
    echo ""
    echo "Необходимые файлы:"
    echo "  - instagram_follower_bot.py"
    echo "  - telegram_control_bot.py"
    echo "  - Dockerfile"
    echo "  - docker-compose.yml"
    echo "  - requirements_bot.txt"
    exit 1
fi

# Запрос Telegram токена
echo ""
echo "🤖 Настройка Telegram бота..."
echo "Получите токен у @BotFather в Telegram"
read -p "Введите Telegram Bot Token: " TELEGRAM_TOKEN

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "❌ Токен не может быть пустым!"
    exit 1
fi

# Обновление токена в файле
echo "📝 Обновление конфигурации..."
sed -i "s/YOUR_TELEGRAM_BOT_TOKEN/$TELEGRAM_TOKEN/g" telegram_control_bot.py

# Создание директории для данных
mkdir -p data

# Сборка и запуск
echo ""
echo "🚀 Сборка Docker образа..."
docker-compose build

echo ""
echo "▶️  Запуск бота..."
docker-compose up -d

echo ""
echo "=================================="
echo "✅ Установка завершена!"
echo "=================================="
echo ""
echo "📱 Откройте Telegram и найдите вашего бота"
echo "📊 Проверить статус: docker-compose ps"
echo "📋 Посмотреть логи: docker-compose logs -f"
echo "🔄 Перезапустить: docker-compose restart"
echo "⏸️  Остановить: docker-compose down"
echo ""
echo "🎉 Бот готов к работе!"
echo ""

# Показать логи
echo "Логи бота (Ctrl+C для выхода):"
docker-compose logs -f

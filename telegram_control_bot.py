"""
Telegram Bot для управления Instagram Follow Bot
Полное управление через Telegram
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from instagram_follower_bot import FollowerBot
import threading
import time


class TelegramController:
    """Telegram бот для управления Instagram ботом"""
    
    def __init__(self, telegram_token: str):
        self.telegram_token = telegram_token
        self.instagram_bot: Optional[FollowerBot] = None
        self.bot_running = False
        self.bot_thread = None
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Загрузить конфигурацию"""
        try:
            with open('bot_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'instagram': {
                    'username': '',
                    'password': '',
                    'logged_in': False
                },
                'targets': [],
                'mode': 'moderate',
                'auto_mode': False,
                'schedule': {
                    'sessions_per_day': 3,
                    'times': ['09:00', '14:00', '19:00']
                }
            }
    
    def _save_config(self):
        """Сохранить конфигурацию"""
        with open('bot_config.json', 'w') as f:
            json.dump(self.config, f, indent=2)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        keyboard = [
            [InlineKeyboardButton("📊 Статус", callback_data='status')],
            [InlineKeyboardButton("▶️ Запустить", callback_data='start_bot'),
             InlineKeyboardButton("⏸️ Остановить", callback_data='stop_bot')],
            [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
            [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 *Instagram Follower Bot Control Panel*\n\n"
            "Управляйте ботом через эту панель.\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'status':
            await self.show_status(query)
        elif query.data == 'start_bot':
            await self.start_instagram_bot(query)
        elif query.data == 'stop_bot':
            await self.stop_instagram_bot(query)
        elif query.data == 'settings':
            await self.show_settings(query)
        elif query.data == 'stats':
            await self.show_stats(query)
        elif query.data == 'mode_safe':
            await self.change_mode(query, 'safe')
        elif query.data == 'mode_moderate':
            await self.change_mode(query, 'moderate')
        elif query.data == 'mode_aggressive':
            await self.change_mode(query, 'aggressive')
        elif query.data == 'toggle_auto':
            await self.toggle_auto_mode(query)
        elif query.data == 'back_main':
            await self.show_main_menu(query)
    
    async def show_status(self, query):
        """Показать статус бота"""
        status_emoji = "🟢" if self.bot_running else "🔴"
        status_text = "Работает" if self.bot_running else "Остановлен"
        
        ig_status = "✅ Авторизован" if self.config['instagram'].get('logged_in') else "❌ Не авторизован"
        
        mode_names = {
            'safe': '🟢 Безопасный',
            'moderate': '🟡 Умеренный',
            'aggressive': '🔴 Агрессивный'
        }
        current_mode = mode_names.get(self.config['mode'], 'Не установлен')
        
        auto_status = "✅ Включен" if self.config.get('auto_mode') else "❌ Выключен"
        
        text = (
            f"📊 *Статус бота*\n\n"
            f"{status_emoji} Бот: {status_text}\n"
            f"📱 Instagram: {ig_status}\n"
            f"⚙️ Режим: {current_mode}\n"
            f"🤖 Авто-режим: {auto_status}\n"
            f"🎯 Целей: {len(self.config.get('targets', []))}\n"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_settings(self, query):
        """Показать настройки"""
        keyboard = [
            [InlineKeyboardButton("🔐 Instagram логин", callback_data='set_instagram')],
            [InlineKeyboardButton("🎯 Целевая аудитория", callback_data='set_targets')],
            [InlineKeyboardButton("⚙️ Режим работы", callback_data='set_mode')],
            [InlineKeyboardButton("🤖 Авто-режим", callback_data='toggle_auto')],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_main')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ *Настройки*\n\nВыберите что настроить:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_stats(self, query):
        """Показать статистику"""
        if self.instagram_bot:
            stats = self.instagram_bot.stats
            
            text = (
                f"📈 *Статистика сегодня*\n\n"
                f"➕ Подписались: {stats['followed_today']}\n"
                f"➖ Отписались: {stats['unfollowed_today']}\n"
                f"👥 Начало: {stats['start_followers']}\n"
                f"👥 Сейчас: {stats['current_followers']}\n"
                f"📊 Прирост: +{stats['followers_gained']}\n"
            )
        else:
            text = "❌ Бот еще не запускался. Статистика недоступна."
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def change_mode(self, query, mode: str):
        """Изменить режим работы"""
        self.config['mode'] = mode
        self._save_config()
        
        mode_names = {
            'safe': '🟢 Безопасный (30 подписок)',
            'moderate': '🟡 Умеренный (50 подписок)',
            'aggressive': '🔴 Агрессивный (100 подписок)'
        }
        
        await query.answer(f"Режим изменен на {mode_names[mode]}")
        await self.show_settings(query)
    
    async def toggle_auto_mode(self, query):
        """Переключить авто-режим"""
        self.config['auto_mode'] = not self.config.get('auto_mode', False)
        self._save_config()
        
        status = "включен" if self.config['auto_mode'] else "выключен"
        await query.answer(f"Авто-режим {status}")
        await self.show_settings(query)
    
    async def start_instagram_bot(self, query):
        """Запустить Instagram бота"""
        if self.bot_running:
            await query.answer("⚠️ Бот уже работает!")
            return
        
        if not self.config['instagram'].get('username') or not self.config['instagram'].get('password'):
            await query.answer("❌ Сначала настройте Instagram логин!")
            return
        
        if not self.config.get('targets'):
            await query.answer("❌ Сначала добавьте целевую аудиторию!")
            return
        
        await query.answer("▶️ Запускаю бота...")
        
        # Запуск в отдельном потоке
        self.bot_thread = threading.Thread(target=self._run_instagram_bot)
        self.bot_thread.daemon = True
        self.bot_thread.start()
        
        self.bot_running = True
        
        await query.edit_message_text(
            "✅ *Бот запущен!*\n\n"
            "Бот начал работу. Используйте /status для проверки прогресса.",
            parse_mode='Markdown'
        )
    
    async def stop_instagram_bot(self, query):
        """Остановить Instagram бота"""
        if not self.bot_running:
            await query.answer("⚠️ Бот не запущен!")
            return
        
        self.bot_running = False
        await query.answer("⏸️ Останавливаю бота...")
        
        await query.edit_message_text(
            "⏸️ *Бот остановлен*\n\n"
            "Бот завершит текущую операцию и остановится.",
            parse_mode='Markdown'
        )
    
    async def show_main_menu(self, query):
        """Показать главное меню"""
        keyboard = [
            [InlineKeyboardButton("📊 Статус", callback_data='status')],
            [InlineKeyboardButton("▶️ Запустить", callback_data='start_bot'),
             InlineKeyboardButton("⏸️ Остановить", callback_data='stop_bot')],
            [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
            [InlineKeyboardButton("📈 Статистика", callback_data='stats')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤖 *Instagram Follower Bot Control Panel*\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def _run_instagram_bot(self):
        """Запустить Instagram бота (в отдельном потоке)"""
        try:
            # Инициализация
            self.instagram_bot = FollowerBot(
                username=self.config['instagram']['username'],
                password=self.config['instagram']['password']
            )
            
            # Авторизация
            self.instagram_bot.login()
            self.config['instagram']['logged_in'] = True
            self._save_config()
            
            # Параметры режима
            modes = {
                'safe': {'follows': 30, 'delay': (60, 120)},
                'moderate': {'follows': 50, 'delay': (40, 80)},
                'aggressive': {'follows': 100, 'delay': (30, 60)}
            }
            
            mode_config = modes[self.config['mode']]
            
            # Запуск кампании
            while self.bot_running:
                self.instagram_bot.run_follow_campaign(
                    target_sources=self.config['targets'],
                    follows_per_session=mode_config['follows'],
                    delay_range=mode_config['delay']
                )
                
                # Если не авто-режим - останавливаемся после одной сессии
                if not self.config.get('auto_mode'):
                    break
                
                # Ждем до следующей сессии (например, 4 часа)
                if self.bot_running:
                    time.sleep(4 * 60 * 60)
            
        except Exception as e:
            print(f"❌ Error in Instagram bot: {e}")
            self.bot_running = False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text
        
        # Здесь можно добавить обработку текстовых команд
        # Например, для настройки логина/пароля
        
        await update.message.reply_text(
            "Используйте /start для открытия панели управления."
        )
    
    def run(self):
        """Запустить Telegram бота"""
        app = Application.builder().token(self.telegram_token).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        print("🤖 Telegram bot started!")
        app.run_polling()


def main():
    """Запуск Telegram контроллера"""
    
    # Получаем токен из переменной окружения (для Render.com)
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
    
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ Ошибка: Установите TELEGRAM_BOT_TOKEN!")
        print("1. Откройте Telegram")
        print("2. Найдите @BotFather")
        print("3. Создайте бота командой /newbot")
        print("4. Скопируйте токен и установите переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    print(f"✅ Token loaded: {TELEGRAM_TOKEN[:10]}...")
    controller = TelegramController(TELEGRAM_TOKEN)
    controller.run()


if __name__ == "__main__":
    main()

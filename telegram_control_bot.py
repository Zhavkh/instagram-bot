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
                    'proxy': '', # Добавили поле proxy
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
            "🤖 Instagram Follower Bot Control Panel\n\n"
            "Управляйте ботом через эту панель.\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок"""
        query = update.callback_query
        await query.answer()
        
        # Сбрасываем состояние ввода
        context.user_data['state'] = None
        
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
        elif query.data == 'back_main':
            await self.show_main_menu(query)
            
        # --- Settings Handlers ---
        elif query.data == 'set_instagram':
            context.user_data['state'] = 'WAITING_USERNAME'
            await query.edit_message_text(
                "🔐 Настройка Instagram\n\n"
                "Введите ваш Instagram Username:\n"
                "(Отправьте текстом в чат)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data='settings')]])
            )
            
        elif query.data == 'set_proxy':
            context.user_data['state'] = 'WAITING_PROXY'
            current = self.config['instagram'].get('proxy', 'Нет')
            await query.edit_message_text(
                f"🌐 Настройка Прокси\n\n"
                f"Текущий прокси: {current}\n\n"
                "Введите прокси в формате:\n"
                "http://user:pass@host:port\n\n"
                "Или отправьте 'clear' чтобы удалить прокси.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data='settings')]])
            )

        elif query.data == 'set_targets':
            current_targets = ", ".join(self.config.get('targets', [])) or "Нет"
            context.user_data['state'] = 'WAITING_TARGETS'
            await query.edit_message_text(
                f"🎯 Целевая аудитория\n\n"
                f"Текущие цели: {current_targets}\n\n"
                "Отправьте Username конкурента (без @) или Хештег (без #):\n"
                "(Можно несколько через запятую)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data='settings')]])
            )
            
        elif query.data == 'set_mode':
            keyboard = [
                [InlineKeyboardButton("🟢 Безопасный", callback_data='mode_safe')],
                [InlineKeyboardButton("🟡 Умеренный", callback_data='mode_moderate')],
                [InlineKeyboardButton("🔴 Агрессивный", callback_data='mode_aggressive')],
                [InlineKeyboardButton("◀️ Назад", callback_data='settings')]
            ]
            await query.edit_message_text(
                "⚙️ Выберите режим работы:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif query.data.startswith('mode_'):
            mode = query.data.replace('mode_', '')
            await self.change_mode(query, mode)
            
        elif query.data == 'toggle_auto':
            await self.toggle_auto_mode(query)

    async def show_status(self, query):
        """Показать статус бота"""
        status_emoji = "🟢" if self.bot_running else "🔴"
        status_text = "Работает" if self.bot_running else "Остановлен"
        
        if hasattr(self, 'last_error') and self.last_error:
            ig_status = f"❌ Ошибка: {self.last_error}"
        else:
            ig_status = "✅ Авторизован" if self.config['instagram'].get('logged_in') else "❌ Не авторизован"
            
        proxy_status = "✅ Прокси" if self.config['instagram'].get('proxy') else "⚠️ Без прокси (Render IP)"
        
        mode_names = {
            'safe': '🟢 Безопасный',
            'moderate': '🟡 Умеренный',
            'aggressive': '🔴 Агрессивный'
        }
        current_mode = mode_names.get(self.config['mode'], 'Не установлен')
        
        auto_status = "✅ Включен" if self.config.get('auto_mode') else "❌ Выключен"
        
        text = (
            f"📊 Статус бота\n\n"
            f"{status_emoji} Бот: {status_text}\n"
            f"📱 Instagram: {ig_status}\n"
            f"🌐 Сеть: {proxy_status}\n"
            f"⚙️ Режим: {current_mode}\n"
            f"🤖 Авто-режим: {auto_status}\n"
            f"🎯 Целей: {len(self.config.get('targets', []))}\n"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(query, 'edit_message_text'):
             await query.edit_message_text(text, reply_markup=reply_markup)
        else:
             await query.reply_text(text, reply_markup=reply_markup)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        await self.show_status(update.message)
    
    async def show_settings(self, query):
        """Показать настройки"""
        keyboard = [
            [InlineKeyboardButton("🔐 Instagram логин", callback_data='set_instagram')],
            [InlineKeyboardButton("🌐 Настроить Прокси", callback_data='set_proxy')], # Кнопка прокси
            [InlineKeyboardButton("🎯 Целевая аудитория", callback_data='set_targets')],
            [InlineKeyboardButton("⚙️ Режим работы", callback_data='set_mode')],
            [InlineKeyboardButton("🤖 Авто-режим", callback_data='toggle_auto')],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_main')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ Настройки\n\nВыберите что настроить:",
            reply_markup=reply_markup
        )
    
    async def show_stats(self, query):
        """Показать статистику"""
        if self.instagram_bot:
            stats = self.instagram_bot.stats
            
            text = (
                f"📈 Статистика сегодня\n\n"
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
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
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
            "✅ Бот запущен!\n\n"
            "Бот начал работу. Используйте /status для проверки прогресса."
        )
    
    async def stop_instagram_bot(self, query):
        """Остановить Instagram бота"""
        if not self.bot_running:
            await query.answer("⚠️ Бот не запущен!")
            return
        
        self.bot_running = False
        await query.answer("⏸️ Останавливаю бота...")
        
        await query.edit_message_text(
            "⏸️ Бот остановлен\n\n"
            "Бот завершит текущую операцию и остановится."
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
            "🤖 Instagram Follower Bot Control Panel\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    def _run_instagram_bot(self):
        """Запустить Instagram бота (в отдельном потоке)"""
        try:
            # Инициализация
            self.instagram_bot = FollowerBot(
                username=self.config['instagram']['username'],
                password=self.config['instagram']['password'],
                proxy=self.config['instagram'].get('proxy') # Передаем прокси
            )
            
            
            # Сбрасываем ошибку перед запуском
            self.last_error = None

            # Авторизация
            self.instagram_bot.login()
            self.config['instagram']['logged_in'] = True
            
            # Если логин успешен, тоже сбрасываем ошибку (на всякий случай)
            self.last_error = None
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
            error_msg = str(e)
            print(f"❌ Error in Instagram bot: {error_msg}")
            self.last_error = error_msg # Сохраняем ошибку для вывода в TG
            self.bot_running = False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if not state:
            return

        if state == 'WAITING_USERNAME':
            self.config['instagram']['username'] = text
            self._save_config()
            
            context.user_data['state'] = 'WAITING_PASSWORD'
            await update.message.reply_text(
                f"✅ Username сохранен: {text}\n\n"
                "Теперь введите ваш Instagram Пароль:"
            )
            
        elif state == 'WAITING_PASSWORD':
            self.config['instagram']['password'] = text
            self._save_config()
            
            context.user_data['state'] = None
            await update.message.reply_text(
                "✅ Пароль сохранен!\n\n"
                "Логин и пароль настроены. Теперь добавьте целевую аудиторию."
            )
            # Показываем настройки снова
            keyboard = [[InlineKeyboardButton("🔙 В настройки", callback_data='settings')]]
            await update.message.reply_text("Вернуться в меню:", reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif state == 'WAITING_PROXY':
             if text.lower() == 'clear':
                 self.config['instagram']['proxy'] = ''
                 msg = "🗑️ Прокси удален."
             else:
                 self.config['instagram']['proxy'] = text
                 msg = f"✅ Прокси сохранен: {text}"
             
             self._save_config()
             context.user_data['state'] = None
             
             await update.message.reply_text(msg)
             keyboard = [[InlineKeyboardButton("🔙 В настройки", callback_data='settings')]]
             await update.message.reply_text("Вернуться в меню:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif state == 'WAITING_TARGETS':
            new_targets = [t.strip() for t in text.split(',')]
            
            # Добавляем, а не заменяем (или можно заменить)
            current = self.config.get('targets', [])
            for t in new_targets:
                if t not in current:
                    current.append(t)
            
            self.config['targets'] = current
            self._save_config()
            
            context.user_data['state'] = None
            await update.message.reply_text(
                f"✅ Цели добавлены!\n\n"
                f"Всего целей: {len(current)}\n"
                f"Последние добавленные: {', '.join(new_targets)}"
            )
            keyboard = [[InlineKeyboardButton("🔙 В настройки", callback_data='settings')]]
            await update.message.reply_text("Вернуться в меню:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    def run(self):
        """Запустить Telegram бота"""
        app = Application.builder().token(self.telegram_token).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("status", self.status_command))  # Добавили обработчик команды /status
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
    
    # Для Render.com: запускаем фейковый веб-сервер в отдельном потоке
    # чтобы Render видел что порт открыт
    import threading
    from flask import Flask
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "✅ Instagram Bot is running!"
    
    @app.route('/health')
    def health():
        return {"status": "ok", "bot": "running"}
    
    # Запускаем Flask в отдельном потоке
    def run_flask():
        port = int(os.getenv('PORT', 10000))
        app.run(host='0.0.0.0', port=port)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print(f"✅ Web server started on port {os.getenv('PORT', 10000)}")
    
    # Запускаем Telegram бота
    controller = TelegramController(TELEGRAM_TOKEN)
    controller.run()


if __name__ == "__main__":
    main()




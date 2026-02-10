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
                "🔐 *Настройка Instagram*\n\n"
                "Введите ваш **Instagram Username**:\n"
                "(Отправьте текстом в чат)",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data='settings')]])
            )
            
        elif query.data == 'set_targets':
            current_targets = ", ".join(self.config.get('targets', [])) or "Нет"
            context.user_data['state'] = 'WAITING_TARGETS'
            await query.edit_message_text(
                f"🎯 *Целевая аудитория*\n\n"
                f"Текущие цели: `{current_targets}`\n\n"
                "Отправьте **Username конкурента** (без @) или **Хештег** (без #):\n"
                "(Можно несколько через запятую)",
                parse_mode='Markdown',
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
                "⚙️ *Выберите режим работы:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif query.data.startswith('mode_'):
            mode = query.data.replace('mode_', '')
            await self.change_mode(query, mode)
            
        elif query.data == 'toggle_auto':
            await self.toggle_auto_mode(query)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if not state:
            # Если нет активного состояния, игнорируем или шлем меню
            # await self.start(update, context) # Можно раскомментировать
            return

        if state == 'WAITING_USERNAME':
            self.config['instagram']['username'] = text
            self._save_config()
            
            context.user_data['state'] = 'WAITING_PASSWORD'
            await update.message.reply_text(
                f"✅ Username сохранен: `{text}`\n\n"
                "Теперь введите ваш **Instagram Пароль**:",
                parse_mode='Markdown'
            )
            
        elif state == 'WAITING_PASSWORD':
            self.config['instagram']['password'] = text
            self._save_config()
            
            context.user_data['state'] = None
            await update.message.reply_text(
                "✅ **Пароль сохранен!**\n\n"
                "Логин и пароль настроены. Теперь добавьте целевую аудиторию.",
                parse_mode='Markdown'
            )
            # Показываем настройки снова
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
                f"✅ **Цели добавлены!**\n\n"
                f"Всего целей: {len(current)}\n"
                f"Последние добавленные: {', '.join(new_targets)}",
                parse_mode='Markdown'
            )
            keyboard = [[InlineKeyboardButton("🔙 В настройки", callback_data='settings')]]
            await update.message.reply_text("Вернуться в меню:", reply_markup=InlineKeyboardMarkup(keyboard))

    
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


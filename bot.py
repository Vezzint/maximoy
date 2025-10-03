import os
import logging
import sqlite3
import datetime
from datetime import timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class HabitTracker:
    def __init__(self):
        self.db_path = "/tmp/habits.db"
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица привычек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                description TEXT,
                created_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица прогресса
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER,
                date TEXT,
                completed INTEGER DEFAULT 0,
                FOREIGN KEY (habit_id) REFERENCES habits (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")

    def add_habit(self, user_id, name, description=""):
        """Добавление новой привычки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO habits (user_id, name, description, created_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, description, datetime.datetime.now().isoformat()))
        
        habit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Habit added: {name} for user {user_id}")
        return habit_id

    def get_user_habits(self, user_id, active_only=True):
        """Получение привычек пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute('''
                SELECT * FROM habits 
                WHERE user_id = ? AND is_active = 1 
                ORDER BY created_date DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM habits 
                WHERE user_id = ? 
                ORDER BY created_date DESC
            ''', (user_id,))
        
        habits = cursor.fetchall()
        conn.close()
        return habits

    def mark_habit_done(self, habit_id, date=None):
        """Отметка выполнения привычки"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем, не отмечена ли уже привычка на сегодня
        cursor.execute('''
            SELECT id FROM progress 
            WHERE habit_id = ? AND date = ?
        ''', (habit_id, date))
        
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            cursor.execute('''
                UPDATE progress SET completed = 1 
                WHERE id = ?
            ''', (existing[0],))
        else:
            # Создаем новую запись
            cursor.execute('''
                INSERT INTO progress (habit_id, date, completed)
                VALUES (?, ?, 1)
            ''', (habit_id, date))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Habit {habit_id} marked as done for {date}")

    def get_habit_progress(self, habit_id, days=30):
        """Получение прогресса по привычке"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        end_date = datetime.datetime.now()
        start_date = end_date - timedelta(days=days)
        
        cursor.execute('''
            SELECT date, completed FROM progress 
            WHERE habit_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
        ''', (habit_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        
        progress = cursor.fetchall()
        conn.close()
        return progress

    def get_today_progress(self, user_id):
        """Прогресс за сегодня"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT h.id, h.name, p.completed 
            FROM habits h 
            LEFT JOIN progress p ON h.id = p.habit_id AND p.date = ?
            WHERE h.user_id = ? AND h.is_active = 1
        ''', (today, user_id))
        
        progress = cursor.fetchall()
        conn.close()
        return progress

class HabitBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.tracker = HabitTracker()
        logger.info("🤖 Habit Tracker Bot initialized")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        welcome_text = f"""
🌟 **Привет, {user.first_name}!**

Я помогу тебе отслеживать привычки и достигать целей!

📊 **Что я умею:**
• Добавлять новые привычки
• Отмечать выполнение каждый день
• Показывать статистику и прогресс
• Мотивировать к регулярности

🎯 **Доступные команды:**
/add_habit - Добавить привычку
/my_habits - Мои привычки
/today - Прогресс за сегодня
/stats - Статистика
/help - Помощь

**Начни с команды /add_habit чтобы добавить первую привычку!**
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def add_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text(
                "📝 **Добавление привычки**\n\n"
                "Используйте: /add_habit <название>\n"
                "Или: /add_habit <название> | <описание>\n\n"
                "**Примеры:**\n"
                "• `/add_habit Утренняя зарядка`\n"
                "• `/add_habit Чтение | Читать 30 минут в день`\n"
                "• `/add_habit Медитация`",
                parse_mode='Markdown'
            )
            return
        
        text = " ".join(context.args)
        if "|" in text:
            name, description = text.split("|", 1)
            name = name.strip()
            description = description.strip()
        else:
            name = text.strip()
            description = ""
        
        habit_id = self.tracker.add_habit(user_id, name, description)
        
        await update.message.reply_text(
            f"✅ **Привычка добавлена!**\n\n"
            f"**Название:** {name}\n"
            f"**Описание:** {description if description else 'Не указано'}\n\n"
            f"Теперь отмечайте выполнение каждый день через /today",
            parse_mode='Markdown'
        )

    async def my_habits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        habits = self.tracker.get_user_habits(user_id)
        
        if not habits:
            await update.message.reply_text(
                "📝 **У вас пока нет привычек**\n\n"
                "Добавьте первую привычку командой /add_habit",
                parse_mode='Markdown'
            )
            return
        
        text = "📊 **Ваши привычки:**\n\n"
        keyboard = []
        
        for habit in habits:
            habit_id, _, name, description, created_date, _ = habit
            text += f"• **{name}**\n"
            if description:
                text += f"  _{description}_\n"
            
            # Кнопка для отметки выполнения
            keyboard.append([InlineKeyboardButton(
                f"✅ Отметить: {name}", 
                callback_data=f"mark_done:{habit_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        progress = self.tracker.get_today_progress(user_id)
        
        if not progress:
            await update.message.reply_text(
                "📝 **У вас нет активных привычек**\n\n"
                "Добавьте привычки командой /add_habit",
                parse_mode='Markdown'
            )
            return
        
        text = f"📅 **Прогресс за сегодня** ({today}):\n\n"
        completed_count = 0
        total_count = len(progress)
        keyboard = []
        
        for habit_id, name, completed in progress:
            status = "✅" if completed else "⏳"
            if completed:
                completed_count += 1
            
            text += f"{status} **{name}**\n"
            
            if not completed:
                keyboard.append([InlineKeyboardButton(
                    f"✅ Выполнено: {name}", 
                    callback_data=f"mark_done:{habit_id}"
                )])
        
        # Статистика за сегодня
        percentage = (completed_count / total_count * 100) if total_count > 0 else 0
        text += f"\n📈 **Статистика:** {completed_count}/{total_count} ({percentage:.1f}%)"
        
        # Визуализация прогресса
        progress_bar = self._create_progress_bar(percentage)
        text += f"\n{progress_bar}"
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        habits = self.tracker.get_user_habits(user_id)
        
        if not habits:
            await update.message.reply_text(
                "📊 **Нет данных для статистики**\n\n"
                "Добавьте привычки командой /add_habit",
                parse_mode='Markdown'
            )
            return
        
        text = "📊 **Ваша статистика:**\n\n"
        
        for habit in habits:
            habit_id, _, name, _, _, _ = habit
            progress = self.tracker.get_habit_progress(habit_id, 7)  # За последние 7 дней
            
            completed = sum(1 for _, completed in progress if completed)
            total = len(progress)
            percentage = (completed / total * 100) if total > 0 else 0
            
            progress_bar = self._create_progress_bar(percentage)
            
            text += f"**{name}**\n"
            text += f"За неделю: {completed}/{total} дней\n"
            text += f"{progress_bar} {percentage:.1f}%\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith("mark_done:"):
            habit_id = int(data.split(":")[1])
            self.tracker.mark_habit_done(habit_id)
            
            # Получаем название привычки
            habits = self.tracker.get_user_habits(user_id)
            habit_name = next((h[2] for h in habits if h[0] == habit_id), "Привычка")
            
            await query.edit_message_text(
                f"🎉 **Отлично!**\n\n"
                f"Привычка **{habit_name}** отмечена как выполненная сегодня!\n\n"
                f"Продолжайте в том же духе! 💪",
                parse_mode='Markdown'
            )

    def _create_progress_bar(self, percentage, length=10):
        """Создает текстовый прогресс-бар"""
        filled = int(percentage / 100 * length)
        empty = length - filled
        return "█" * filled + "░" * empty

    def run(self):
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            return
        
        application = Application.builder().token(self.token).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("add_habit", self.add_habit))
        application.add_handler(CommandHandler("my_habits", self.my_habits))
        application.add_handler(CommandHandler("today", self.today))
        application.add_handler(CommandHandler("stats", self.stats))
        application.add_handler(CommandHandler("help", self.start))
        
        # Обработчик кнопок
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        logger.info("🚀 Starting Habit Tracker Bot...")
        application.run_polling()

if __name__ == "__main__":
    bot = HabitBot()
    bot.run()
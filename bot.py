import os
import logging
import sqlite3
import datetime
import random
from datetime import timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MaximoyDatabase:
    def __init__(self):
        self.db_path = "/tmp/maximoy.db"
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
                category TEXT,
                difficulty TEXT,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                created_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица прогресса привычек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS habit_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER,
                date TEXT,
                completed INTEGER DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (habit_id) REFERENCES habits (id)
            )
        ''')
        
        # Таблица задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                description TEXT,
                priority TEXT,
                due_date TEXT,
                completed INTEGER DEFAULT 0,
                created_date TEXT
            )
        ''')
        
        # Таблица заметок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                content TEXT,
                category TEXT,
                created_date TEXT,
                updated_date TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Maximoy Database initialized")

    def add_habit(self, user_id, name, description="", category="general", difficulty="medium"):
        """Добавление новой привычки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO habits (user_id, name, description, category, difficulty, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, name, description, category, difficulty, datetime.datetime.now().isoformat()))
        
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
                ORDER BY streak DESC, created_date DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM habits 
                WHERE user_id = ? 
                ORDER BY streak DESC, created_date DESC
            ''', (user_id,))
        
        habits = cursor.fetchall()
        conn.close()
        return habits

    def mark_habit_done(self, habit_id, notes=""):
        """Отметка выполнения привычки"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем, не отмечена ли уже привычка на сегодня
        cursor.execute('''
            SELECT id FROM habit_progress 
            WHERE habit_id = ? AND date = ?
        ''', (habit_id, today))
        
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE habit_progress SET completed = 1, notes = ?
                WHERE id = ?
            ''', (notes, existing[0]))
        else:
            cursor.execute('''
                INSERT INTO habit_progress (habit_id, date, completed, notes)
                VALUES (?, ?, 1, ?)
            ''', (habit_id, today, notes))
        
        # Обновляем streak
        cursor.execute('''
            UPDATE habits SET streak = streak + 1,
            best_streak = CASE WHEN streak + 1 > best_streak THEN streak + 1 ELSE best_streak END
            WHERE id = ?
        ''', (habit_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Habit {habit_id} marked as done")

    def add_task(self, user_id, title, description="", priority="medium", due_date=None):
        """Добавление задачи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (user_id, title, description, priority, due_date, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, title, description, priority, due_date, datetime.datetime.now().isoformat()))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_user_tasks(self, user_id, completed=False):
        """Получение задач пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE user_id = ? AND completed = ?
            ORDER BY 
                CASE priority 
                    WHEN 'high' THEN 1 
                    WHEN 'medium' THEN 2 
                    WHEN 'low' THEN 3 
                END,
                created_date DESC
        ''', (user_id, 1 if completed else 0))
        
        tasks = cursor.fetchall()
        conn.close()
        return tasks

    def mark_task_completed(self, task_id):
        """Отметка задачи как выполненной"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tasks SET completed = 1 WHERE id = ?
        ''', (task_id,))
        
        conn.commit()
        conn.close()

    def add_note(self, user_id, title, content, category="general"):
        """Добавление заметки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO notes (user_id, title, content, category, created_date, updated_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, title, content, category, now, now))
        
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id

    def get_user_notes(self, user_id, category=None):
        """Получение заметок пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT * FROM notes 
                WHERE user_id = ? AND category = ?
                ORDER BY updated_date DESC
            ''', (user_id, category))
        else:
            cursor.execute('''
                SELECT * FROM notes 
                WHERE user_id = ?
                ORDER BY updated_date DESC
            ''', (user_id,))
        
        notes = cursor.fetchall()
        conn.close()
        return notes

class MaximoyBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.db = MaximoyDatabase()
        self.motivational_quotes = [
            "Каждый день - это новый шанс стать лучше! 🌟",
            "Маленькие шаги приводят к большим результатам! 🚶‍♂️",
            "Ты справишься! У тебя всё получается! 💪",
            "Сегодня - идеальный день для новых достижений! 🌈",
            "Помни: даже самые великие дела начинались с первого шага! 🎯",
            "Успех - это сумма маленьких усилий, повторяющихся изо дня в день! 📈",
            "Ты ближе к своей цели, чем был вчера! 🎉",
            "Не откладывай на завтра то, что можно сделать сегодня! ⏰"
        ]
        logger.info("🤖 Maximoy Bot initialized")

    def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        welcome_text = f"""
🌟 **Добро пожаловать в Maximoy, {user.first_name}!**

Я твой персональный ассистент для управления привычками, задачами и заметками!

📊 **Мои возможности:**

🎯 **Привычки**
• Отслеживание ежедневных привычек
• Статистика и стрики
• Категории и уровни сложности

✅ **Задачи** 
• Управление задачами с приоритетами
• Напоминания о дедлайнах
• Прогресс выполнения

📝 **Заметки**
• Быстрые заметки по категориям
• Поиск и организация

📈 **Аналитика**
• Подробная статистика
• Визуализация прогресса

🚀 **Основные команды:**
/add_habit - Добавить привычку
/add_task - Добавить задачу  
/add_note - Добавить заметку
/dashboard - Обзор дня
/stats - Статистика
/help - Помощь

**Maximoy поможет тебе стать продуктивнее каждый день!** ✨
        """
        keyboard = [
            [InlineKeyboardButton("🎯 Добавить привычку", callback_data="quick_add_habit")],
            [InlineKeyboardButton("✅ Добавить задачу", callback_data="quick_add_task")],
            [InlineKeyboardButton("📝 Быстрая заметка", callback_data="quick_note")],
            [InlineKeyboardButton("📊 Дашборд", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    def dashboard(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Получаем данные
        habits = self.db.get_user_habits(user_id)
        tasks = self.db.get_user_tasks(user_id, completed=False)
        
        text = f"📊 **Дашборд Maximoy** • {today}\n\n"
        
        # Прогресс привычек за сегодня
        completed_today = 0
        total_habits = len(habits)
        
        for habit in habits:
            habit_id = habit[0]
            # Простая проверка выполнения сегодня
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM habit_progress 
                WHERE habit_id = ? AND date = ? AND completed = 1
            ''', (habit_id, today))
            if cursor.fetchone()[0] > 0:
                completed_today += 1
            conn.close()
        
        habit_percentage = (completed_today / total_habits * 100) if total_habits > 0 else 0
        
        text += f"🎯 **Привычки сегодня:** {completed_today}/{total_habits}\n"
        text += f"{self._create_progress_bar(habit_percentage)} {habit_percentage:.0f}%\n\n"
        
        # Активные задачи
        high_priority = sum(1 for task in tasks if task[4] == 'high')
        medium_priority = sum(1 for task in tasks if task[4] == 'medium')
        low_priority = sum(1 for task in tasks if task[4] == 'low')
        
        text += f"✅ **Активные задачи:** {len(tasks)}\n"
        text += f"   🔴 Высокий: {high_priority} | 🟡 Средний: {medium_priority} | 🟢 Низкий: {low_priority}\n\n"
        
        # Мотивационная цитата
        quote = random.choice(self.motivational_quotes)
        text += f"💫 *{quote}*"
        
        # Кнопки быстрых действий
        keyboard = [
            [InlineKeyboardButton("✅ Отметить привычки", callback_data="mark_habits")],
            [InlineKeyboardButton("📋 Список задач", callback_data="show_tasks")],
            [InlineKeyboardButton("📈 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🎯 Добавить новое", callback_data="quick_add")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    def add_habit(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text(
                "🎯 **Добавление привычки**\n\n"
                "Формат: /add_habit <название> | <описание> | <категория> | <сложность>\n\n"
                "**Категории:** здоровье, учеба, работа, спорт, творчество\n"
                "**Сложность:** легкая, средняя, сложная\n\n"
                "**Примеры:**\n"
                "• `/add_habit Утренняя зарядка`\n"
                "• `/add_habit Чтение | Читать 30 минут | учеба | средняя`\n"
                "• `/add_habit Медитация | 10 минут утром | здоровье | легкая`",
                parse_mode='Markdown'
            )
            return
        
        text = " ".join(context.args)
        parts = text.split("|")
        
        name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        category = parts[2].strip() if len(parts) > 2 else "general"
        difficulty = parts[3].strip() if len(parts) > 3 else "medium"
        
        habit_id = self.db.add_habit(update.effective_user.id, name, description, category, difficulty)
        
        update.message.reply_text(
            f"✅ **Привычка добавлена!**\n\n"
            f"**Название:** {name}\n"
            f"**Описание:** {description if description else 'Не указано'}\n"
            f"**Категория:** {category}\n"
            f"**Сложность:** {difficulty}\n\n"
            f"Теперь отмечайте выполнение каждый день! 🎯",
            parse_mode='Markdown'
        )

    def add_task(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text(
                "✅ **Добавление задачи**\n\n"
                "Формат: /add_task <название> | <описание> | <приоритет> | <срок>\n\n"
                "**Приоритет:** высокий, средний, низкий\n"
                "**Срок:** ГГГГ-ММ-ДД или 'сегодня', 'завтра'\n\n"
                "**Примеры:**\n"
                "• `/add_task Сделать презентацию`\n"
                "• `/add_task Заказать продукты | Молоко, хлеб | высокий | сегодня`\n"
                "• `/add_task Прочитать книгу | 50 страниц | средний | 2024-12-31`",
                parse_mode='Markdown'
            )
            return
        
        text = " ".join(context.args)
        parts = text.split("|")
        
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        priority = parts[2].strip() if len(parts) > 2 else "medium"
        due_date = parts[3].strip() if len(parts) > 3 else None
        
        # Обработка относительных дат
        if due_date == 'сегодня':
            due_date = datetime.datetime.now().strftime("%Y-%m-%d")
        elif due_date == 'завтра':
            due_date = (datetime.datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        task_id = self.db.add_task(update.effective_user.id, title, description, priority, due_date)
        
        update.message.reply_text(
            f"✅ **Задача добавлена!**\n\n"
            f"**Название:** {title}\n"
            f"**Описание:** {description if description else 'Не указано'}\n"
            f"**Приоритет:** {priority}\n"
            f"**Срок:** {due_date if due_date else 'Не установлен'}\n\n"
            f"Не забудьте выполнить в срок! ⏰",
            parse_mode='Markdown'
        )

    def add_note(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text(
                "📝 **Добавление заметки**\n\n"
                "Формат: /add_note <заголовок> | <текст> | <категория>\n\n"
                "**Категории:** идеи, мысли, задачи, ссылки, личное\n\n"
                "**Примеры:**\n"
                "• `/add_note Идея для проекта | Создать бота для финансов`\n"
                "• `/add_note Мысли | Нужно больше спорта | здоровье`\n"
                "• `/add_note Ссылка | https://example.com | ссылки`",
                parse_mode='Markdown'
            )
            return
        
        text = " ".join(context.args)
        parts = text.split("|")
        
        title = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ""
        category = parts[2].strip() if len(parts) > 2 else "general"
        
        note_id = self.db.add_note(update.effective_user.id, title, content, category)
        
        update.message.reply_text(
            f"📝 **Заметка сохранена!**\n\n"
            f"**Заголовок:** {title}\n"
            f"**Категория:** {category}\n"
            f"**Содержание:** {content if content else 'Пусто'}\n\n"
            f"Заметка №{note_id} успешно сохранена! 💾",
            parse_mode='Markdown'
        )

    def stats(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        habits = self.db.get_user_habits(user_id)
        tasks = self.db.get_user_tasks(user_id)
        notes = self.db.get_user_notes(user_id)
        
        text = "📈 **Статистика Maximoy**\n\n"
        
        # Статистика привычек
        if habits:
            total_streak = sum(habit[6] for habit in habits)
            best_streak = max((habit[7] for habit in habits), default=0)
            
            text += "🎯 **Привычки:**\n"
            text += f"• Всего привычек: {len(habits)}\n"
            text += f"• Общий стрик: {total_streak} дней\n"
            text += f"• Лучший стрик: {best_streak} дней\n\n"
        
        # Статистика задач
        if tasks:
            completed_tasks = sum(1 for task in tasks if task[6])
            total_tasks = len(tasks)
            
            text += "✅ **Задачи:**\n"
            text += f"• Всего задач: {total_tasks}\n"
            text += f"• Выполнено: {completed_tasks}\n"
            text += f"• Прогресс: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%\n\n"
        
        # Статистика заметок
        if notes:
            categories = {}
            for note in notes:
                cat = note[4]
                categories[cat] = categories.get(cat, 0) + 1
            
            text += "📝 **Заметки:**\n"
            text += f"• Всего заметок: {len(notes)}\n"
            text += f"• Категории: {', '.join(categories.keys())}\n\n"
        
        if not habits and not tasks and not notes:
            text += "📊 **Данных пока нет**\n\n"
            text += "Начните добавлять привычки, задачи и заметки, чтобы увидеть статистику!"
        else:
            # Мотивационное сообщение
            quote = random.choice(self.motivational_quotes)
            text += f"💫 *{quote}*"
        
        update.message.reply_text(text, parse_mode='Markdown')

    def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()
        
        if query.data == "dashboard":
            self.dashboard(query, context)
        elif query.data == "show_stats":
            self.stats(query, context)
        elif query.data == "quick_add":
            keyboard = [
                [InlineKeyboardButton("🎯 Привычка", callback_data="quick_habit")],
                [InlineKeyboardButton("✅ Задача", callback_data="quick_task")],
                [InlineKeyboardButton("📝 Заметка", callback_data="quick_note")],
                [InlineKeyboardButton("📊 Назад", callback_data="dashboard")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(
                "🚀 **Быстрое добавление**\n\nВыберите что хотите добавить:",
                reply_markup=reply_markup,
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
        
        updater = Updater(self.token, use_context=True)
        dispatcher = updater.dispatcher
        
        # Команды
        dispatcher.add_handler(CommandHandler("start", self.start))
        dispatcher.add_handler(CommandHandler("dashboard", self.dashboard))
        dispatcher.add_handler(CommandHandler("add_habit", self.add_habit))
        dispatcher.add_handler(CommandHandler("add_task", self.add_task))
        dispatcher.add_handler(CommandHandler("add_note", self.add_note))
        dispatcher.add_handler(CommandHandler("stats", self.stats))
        dispatcher.add_handler(CommandHandler("help", self.start))
        
        # Обработчики кнопок
        dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
        
        logger.info("🚀 Starting Maximoy Bot...")
        updater.start_polling()
        updater.idle()

if __name__ == "__main__":
    bot = MaximoyBot()
    bot.run()

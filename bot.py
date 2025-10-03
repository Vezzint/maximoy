import os
import logging
import json
import datetime
import random
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

class MaximoyStorage:
    def __init__(self):
        self.data_dir = "/tmp/maximoy_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.init_storage()
    
    def init_storage(self):
        """Инициализация хранилища"""
        default_data = {
            "habits": {},
            "tasks": {},
            "notes": {},
            "users": {}
        }
        
        for filename, data in default_data.items():
            filepath = os.path.join(self.data_dir, f"{filename}.json")
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ Maximoy Storage initialized")

    def _load_data(self, data_type):
        """Загрузка данных из файла"""
        filepath = os.path.join(self.data_dir, f"{data_type}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _save_data(self, data_type, data):
        """Сохранение данных в файл"""
        filepath = os.path.join(self.data_dir, f"{data_type}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # === ХАБИТЫ ===
    def add_habit(self, user_id, name, description="", category="general", difficulty="medium"):
        """Добавление привычки"""
        habits = self._load_data("habits")
        
        habit_id = str(int(datetime.datetime.now().timestamp() * 1000))
        habits[habit_id] = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "category": category,
            "difficulty": difficulty,
            "streak": 0,
            "best_streak": 0,
            "created_date": datetime.datetime.now().isoformat(),
            "progress": {}
        }
        
        self._save_data("habits", habits)
        logger.info(f"✅ Habit added: {name} for user {user_id}")
        return habit_id

    def get_user_habits(self, user_id, active_only=True):
        """Получение привычек пользователя"""
        habits = self._load_data("habits")
        user_habits = []
        
        for habit_id, habit in habits.items():
            if habit["user_id"] == user_id:
                user_habits.append((habit_id, habit))
        
        # Сортировка по стрику и дате создания
        user_habits.sort(key=lambda x: (-x[1]["streak"], x[1]["created_date"]), reverse=True)
        return user_habits

    def mark_habit_done(self, habit_id, notes=""):
        """Отметка выполнения привычки"""
        habits = self._load_data("habits")
        
        if habit_id in habits:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            habit = habits[habit_id]
            
            # Отмечаем выполнение
            habit["progress"][today] = {
                "completed": True,
                "notes": notes,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Обновляем стрик
            habit["streak"] += 1
            if habit["streak"] > habit["best_streak"]:
                habit["best_streak"] = habit["streak"]
            
            self._save_data("habits", habits)
            logger.info(f"✅ Habit {habit_id} marked as done")

    # === ЗАДАЧИ ===
    def add_task(self, user_id, title, description="", priority="medium", due_date=None):
        """Добавление задачи"""
        tasks = self._load_data("tasks")
        
        task_id = str(int(datetime.datetime.now().timestamp() * 1000))
        tasks[task_id] = {
            "user_id": user_id,
            "title": title,
            "description": description,
            "priority": priority,
            "due_date": due_date,
            "completed": False,
            "created_date": datetime.datetime.now().isoformat()
        }
        
        self._save_data("tasks", tasks)
        return task_id

    def get_user_tasks(self, user_id, completed=False):
        """Получение задач пользователя"""
        tasks = self._load_data("tasks")
        user_tasks = []
        
        for task_id, task in tasks.items():
            if task["user_id"] == user_id and task["completed"] == completed:
                user_tasks.append((task_id, task))
        
        # Сортировка по приоритету
        priority_order = {"high": 1, "medium": 2, "low": 3}
        user_tasks.sort(key=lambda x: (priority_order.get(x[1]["priority"], 4), x[1]["created_date"]))
        return user_tasks

    def mark_task_completed(self, task_id):
        """Отметка задачи как выполненной"""
        tasks = self._load_data("tasks")
        
        if task_id in tasks:
            tasks[task_id]["completed"] = True
            self._save_data("tasks", tasks)

    # === ЗАМЕТКИ ===
    def add_note(self, user_id, title, content, category="general"):
        """Добавление заметки"""
        notes = self._load_data("notes")
        
        note_id = str(int(datetime.datetime.now().timestamp() * 1000))
        now = datetime.datetime.now().isoformat()
        notes[note_id] = {
            "user_id": user_id,
            "title": title,
            "content": content,
            "category": category,
            "created_date": now,
            "updated_date": now
        }
        
        self._save_data("notes", notes)
        return note_id

    def get_user_notes(self, user_id, category=None):
        """Получение заметок пользователя"""
        notes = self._load_data("notes")
        user_notes = []
        
        for note_id, note in notes.items():
            if note["user_id"] == user_id:
                if category is None or note["category"] == category:
                    user_notes.append((note_id, note))
        
        # Сортировка по дате обновления
        user_notes.sort(key=lambda x: x[1]["updated_date"], reverse=True)
        return user_notes

class MaximoyBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.storage = MaximoyStorage()
        self.motivational_quotes = [
            "Каждый день - это новый шанс стать лучше! 🌟",
            "Маленькие шаги приводят к большим результатам! 🚶‍♂️",
            "Ты справишься! У тебя всё получается! 💪",
            "Сегодня - идеальный день для новых достижений! 🌈",
            "Помни: даже самые великие дела начинались с первого шага! 🎯",
            "Успех - это сумма маленьких усилий, повторяющихся изо дня в день! 📈",
            "Ты ближе к своей цели, чем был вчера! 🎉",
            "Не откладывай на завтра то, что можно сделать сегодня! ⏰",
            "Твоя продуктивность - это твоя суперсила! 🦸‍♂️",
            "Каждая выполненная задача приближает тебя к успеху! 🎯"
        ]
        logger.info("🤖 Maximoy Bot initialized")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        logger.info(f"👤 Start command from user {user.id}")
        
        welcome_text = f"""🌟 *Добро пожаловать в Maximoy, {user.first_name}\!*

Я твой персональный ассистент для управления привычками, задачами и заметками\!

*📊 Мои возможности:*

*🎯 Привычки*
• Отслеживание ежедневных привычек
• Статистика и стрики
• Категории и уровни сложности

*✅ Задачи* 
• Управление задачами с приоритетами
• Напоминания о дедлайнах
• Прогресс выполнения

*📝 Заметки*
• Быстрые заметки по категориям
• Поиск и организация

*📈 Аналитика*
• Подробная статистика
• Визуализация прогресса

*🚀 Основные команды:*
/add\_habit \- Добавить привычку
/add\_task \- Добавить задачу  
/add\_note \- Добавить заметку
/dashboard \- Обзор дня
/stats \- Статистика
/help \- Помощь

*Maximoy поможет тебе стать продуктивнее каждый день\!* ✨"""
        
        keyboard = [
            [InlineKeyboardButton("🎯 Добавить привычку", callback_data="quick_add_habit")],
            [InlineKeyboardButton("✅ Добавить задачу", callback_data="quick_add_task")],
            [InlineKeyboardButton("📝 Быстрая заметка", callback_data="quick_note")],
            [InlineKeyboardButton("📊 Дашборд", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    async def dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Получаем user_id в зависимости от типа update
        if hasattr(update, 'message') and update.message:
            user_id = update.effective_user.id
            message = update.message
        else:
            user_id = update.callback_query.from_user.id
            message = update.callback_query.message
            
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Получаем данные
        habits = self.storage.get_user_habits(user_id)
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        
        text = f"📊 *Дашборд Maximoy* • {today}\n\n"
        
        # Прогресс привычек за сегодня
        completed_today = 0
        total_habits = len(habits)
        
        for habit_id, habit in habits:
            if today in habit.get("progress", {}) and habit["progress"][today].get("completed"):
                completed_today += 1
        
        habit_percentage = (completed_today / total_habits * 100) if total_habits > 0 else 0
        
        text += f"🎯 *Привычки сегодня:* {completed_today}/{total_habits}\n"
        text += f"{self._create_progress_bar(habit_percentage)} {habit_percentage:.0f}%\n\n"
        
        # Активные задачи
        high_priority = sum(1 for task_id, task in tasks if task["priority"] == 'high')
        medium_priority = sum(1 for task_id, task in tasks if task["priority"] == 'medium')
        low_priority = sum(1 for task_id, task in tasks if task["priority"] == 'low')
        
        text += f"✅ *Активные задачи:* {len(tasks)}\n"
        text += f"   🔴 Высокий: {high_priority} | 🟡 Средний: {medium_priority} | 🟢 Низкий: {low_priority}\n\n"
        
        # Мотивационная цитата
        quote = random.choice(self.motivational_quotes)
        text += f"💫 *{quote}*"
        
        # Кнопки быстрых действий
        keyboard = []
        for habit_id, habit in habits[:3]:  # Первые 3 привычки
            if today not in habit.get("progress", {}) or not habit["progress"][today].get("completed"):
                keyboard.append([InlineKeyboardButton(
                    f"✅ {habit['name']}", 
                    callback_data=f"mark_habit:{habit_id}"
                )])
        
        if not keyboard and habits:
            keyboard.append([InlineKeyboardButton("🎉 Все привычки выполнены!", callback_data="celebrate")])
        
        keyboard.extend([
            [InlineKeyboardButton("📋 Список задач", callback_data="show_tasks")],
            [InlineKeyboardButton("📈 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🎯 Добавить новое", callback_data="quick_add")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def add_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text(
                "🎯 *Добавление привычки*\n\n"
                "Формат: /add\_habit <название> | <описание> | <категория> | <сложность>\n\n"
                "*Категории:* здоровье, учеба, работа, спорт, творчество\n"
                "*Сложность:* легкая, средняя, сложная\n\n"
                "*Примеры:*\n"
                "• `/add_habit Утренняя зарядка`\n"
                "• `/add_habit Чтение | Читать 30 минут | учеба | средняя`\n"
                "• `/add_habit Медитация | 10 минут утром | здоровье | легкая`",
                parse_mode='Markdown'
            )
            return
        
        text = " ".join(context.args)
        parts = [part.strip() for part in text.split("|")]
        
        name = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        category = parts[2] if len(parts) > 2 else "general"
        difficulty = parts[3] if len(parts) > 3 else "medium"
        
        habit_id = self.storage.add_habit(update.effective_user.id, name, description, category, difficulty)
        
        await update.message.reply_text(
            f"✅ *Привычка добавлена\!*\n\n"
            f"*Название:* {name}\n"
            f"*Описание:* {description if description else 'Не указано'}\n"
            f"*Категория:* {category}\n"
            f"*Сложность:* {difficulty}\n\n"
            f"Теперь отмечайте выполнение каждый день\! 🎯",
            parse_mode='MarkdownV2'
        )

    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text(
                "✅ *Добавление задачи*\n\n"
                "Формат: /add\_task <название> | <описание> | <приоритет> | <срок>\n\n"
                "*Приоритет:* высокий, средний, низкий\n"
                "*Срок:* ГГГГ\-ММ\-ДД или 'сегодня', 'завтра'\n\n"
                "*Примеры:*\n"
                "• `/add_task Сделать презентацию`\n"
                "• `/add_task Заказать продукты | Молоко, хлеб | высокий | сегодня`\n"
                "• `/add_task Прочитать книгу | 50 страниц | средний | 2024\-12\-31`",
                parse_mode='MarkdownV2'
            )
            return
        
        text = " ".join(context.args)
        parts = [part.strip() for part in text.split("|")]
        
        title = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        priority = parts[2] if len(parts) > 2 else "medium"
        due_date = parts[3] if len(parts) > 3 else None
        
        # Обработка относительных дат
        if due_date == 'сегодня':
            due_date = datetime.datetime.now().strftime("%Y-%m-%d")
        elif due_date == 'завтра':
            due_date = (datetime.datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        task_id = self.storage.add_task(update.effective_user.id, title, description, priority, due_date)
        
        await update.message.reply_text(
            f"✅ *Задача добавлена\!*\n\n"
            f"*Название:* {title}\n"
            f"*Описание:* {description if description else 'Не указано'}\n"
            f"*Приоритет:* {priority}\n"
            f"*Срок:* {due_date if due_date else 'Не установлен'}\n\n"
            f"Не забудьте выполнить в срок\! ⏰",
            parse_mode='MarkdownV2'
        )

    async def add_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text(
                "📝 *Добавление заметки*\n\n"
                "Формат: /add\_note <заголовок> | <текст> | <категория>\n\n"
                "*Категории:* идеи, мысли, задачи, ссылки, личное\n\n"
                "*Примеры:*\n"
                "• `/add_note Идея для проекта | Создать бота для финансов`\n"
                "• `/add_note Мысли | Нужно больше спорта | здоровье`\n"
                "• `/add_note Ссылка | https://example\.com | ссылки`",
                parse_mode='MarkdownV2'
            )
            return
        
        text = " ".join(context.args)
        parts = [part.strip() for part in text.split("|")]
        
        title = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        category = parts[2] if len(parts) > 2 else "general"
        
        note_id = self.storage.add_note(update.effective_user.id, title, content, category)
        
        await update.message.reply_text(
            f"📝 *Заметка сохранена\!*\n\n"
            f"*Заголовок:* {title}\n"
            f"*Категория:* {category}\n"
            f"*Содержание:* {content if content else 'Пусто'}\n\n"
            f"Заметка успешно сохранена\! 💾",
            parse_mode='MarkdownV2'
        )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        habits = self.storage.get_user_habits(user_id)
        tasks = self.storage.get_user_tasks(user_id)
        notes = self.storage.get_user_notes(user_id)
        
        text = "📈 *Статистика Maximoy*\n\n"
        
        # Статистика привычек
        if habits:
            total_streak = sum(habit[1]["streak"] for habit in habits)
            best_streak = max((habit[1]["best_streak"] for habit in habits), default=0)
            
            text += "*🎯 Привычки:*\n"
            text += f"• Всего привычек: {len(habits)}\n"
            text += f"• Общий стрик: {total_streak} дней\n"
            text += f"• Лучший стрик: {best_streak} дней\n\n"
        
        # Статистика задач
        if tasks:
            completed_tasks = sum(1 for task_id, task in tasks if task["completed"])
            total_tasks = len(tasks)
            
            text += "*✅ Задачи:*\n"
            text += f"• Всего задач: {total_tasks}\n"
            text += f"• Выполнено: {completed_tasks}\n"
            text += f"• Прогресс: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%\n\n"
        
        # Статистика заметок
        if notes:
            categories = {}
            for note_id, note in notes:
                cat = note["category"]
                categories[cat] = categories.get(cat, 0) + 1
            
            text += "*📝 Заметки:*\n"
            text += f"• Всего заметок: {len(notes)}\n"
            text += f"• Категории: {', '.join(categories.keys())}\n\n"
        
        if not habits and not tasks and not notes:
            text += "*📊 Данных пока нет*\n\n"
            text += "Начните добавлять привычки, задачи и заметки, чтобы увидеть статистику!"
        else:
            # Мотивационное сообщение
            quote = random.choice(self.motivational_quotes)
            text += f"💫 *{quote}*"
        
        await update.message.reply_text(text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """*📋 Доступные команды Maximoy:*

*🎯 Привычки*
/add\_habit \- Добавить новую привычку
/dashboard \- Обзор привычек за сегодня

*✅ Задачи*
/add\_task \- Добавить новую задачу

*📝 Заметки*
/add\_note \- Добавить новую заметку

*📊 Аналитика*
/stats \- Показать статистику

*🔧 Общее*
/start \- Начать работу
/help \- Показать эту справку

*💫 Maximoy \- твой персональный ассистент продуктивности\!*"""
        
        await update.message.reply_text(help_text, parse_mode='MarkdownV2')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        logger.info(f"🔘 Button pressed by {user_id}: {data}")
        
        try:
            if data == "dashboard":
                await self._send_dashboard(query)
            elif data == "show_stats":
                await self._send_stats(query)
            elif data == "quick_add":
                await self._show_quick_add_menu(query)
            elif data.startswith("mark_habit:"):
                habit_id = data.split(":")[1]
                self.storage.mark_habit_done(habit_id)
                await query.edit_message_text("✅ Привычка отмечена как выполненная! 🎉", parse_mode='Markdown')
            elif data == "celebrate":
                await query.edit_message_text("🎉 Отлично! Все привычки на сегодня выполнены! Ты просто супер! 🌟", parse_mode='Markdown')
            elif data == "quick_add_habit":
                await query.edit_message_text(
                    "🎯 *Добавление привычки*\n\n"
                    "Используйте команду:\n"
                    "`/add_habit <название> | <описание> | <категория> | <сложность>`\n\n"
                    "*Пример:*\n"
                    "`/add_habit Утренняя зарядка | 15 минут утром | здоровье | легкая`",
                    parse_mode='Markdown'
                )
            elif data == "quick_add_task":
                await query.edit_message_text(
                    "✅ *Добавление задачи*\n\n"
                    "Используйте команду:\n"
                    "`/add_task <название> | <описание> | <приоритет> | <срок>`\n\n"
                    "*Пример:*\n"
                    "`/add_task Сделать презентацию | Слайды 1-10 | высокий | сегодня`",
                    parse_mode='Markdown'
                )
            elif data == "quick_note":
                await query.edit_message_text(
                    "📝 *Добавление заметки*\n\n"
                    "Используйте команду:\n"
                    "`/add_note <заголовок> | <текст> | <категория>`\n\n"
                    "*Пример:*\n"
                    "`/add_note Идея проекта | Создать бота для финансов | идеи`",
                    parse_mode='Markdown'
                )
            elif data == "show_tasks":
                await self._show_tasks(query)
                
        except Exception as e:
            logger.error(f"❌ Button handler error: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

    async def _send_dashboard(self, query):
        """Отправка дашборда для callback query"""
        user_id = query.from_user.id
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        habits = self.storage.get_user_habits(user_id)
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        
        text = f"📊 *Дашборд Maximoy* • {today}\n\n"
        
        # Прогресс привычек за сегодня
        completed_today = 0
        total_habits = len(habits)
        
        for habit_id, habit in habits:
            if today in habit.get("progress", {}) and habit["progress"][today].get("completed"):
                completed_today += 1
        
        habit_percentage = (completed_today / total_habits * 100) if total_habits > 0 else 0
        
        text += f"🎯 *Привычки сегодня:* {completed_today}/{total_habits}\n"
        text += f"{self._create_progress_bar(habit_percentage)} {habit_percentage:.0f}%\n\n"
        
        # Активные задачи
        high_priority = sum(1 for task_id, task in tasks if task["priority"] == 'high')
        medium_priority = sum(1 for task_id, task in tasks if task["priority"] == 'medium')
        low_priority = sum(1 for task_id, task in tasks if task["priority"] == 'low')
        
        text += f"✅ *Активные задачи:* {len(tasks)}\n"
        text += f"   🔴 Высокий: {high_priority} | 🟡 Средний: {medium_priority} | 🟢 Низкий: {low_priority}\n\n"
        
        # Мотивационная цитата
        quote = random.choice(self.motivational_quotes)
        text += f"💫 *{quote}*"
        
        # Кнопки
        keyboard = []
        for habit_id, habit in habits[:3]:
            if today not in habit.get("progress", {}) or not habit["progress"][today].get("completed"):
                keyboard.append([InlineKeyboardButton(f"✅ {habit['name']}", callback_data=f"mark_habit:{habit_id}")])
        
        if not keyboard and habits:
            keyboard.append([InlineKeyboardButton("🎉 Все привычки выполнены!", callback_data="celebrate")])
        
        keyboard.extend([
            [InlineKeyboardButton("📋 Список задач", callback_data="show_tasks")],
            [InlineKeyboardButton("📈 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🎯 Добавить новое", callback_data="quick_add")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _send_stats(self, query):
        """Отправка статистики для callback query"""
        user_id = query.from_user.id
        
        habits = self.storage.get_user_habits(user_id)
        tasks = self.storage.get_user_tasks(user_id)
        notes = self.storage.get_user_notes(user_id)
        
        text = "📈 *Статистика Maximoy*\n\n"
        
        if habits:
            total_streak = sum(habit[1]["streak"] for habit in habits)
            best_streak = max((habit[1]["best_streak"] for habit in habits), default=0)
            
            text += "*🎯 Привычки:*\n"
            text += f"• Всего привычек: {len(habits)}\n"
            text += f"• Общий стрик: {total_streak} дней\n"
            text += f"• Лучший стрик: {best_streak} дней\n\n"
        
        if tasks:
            completed_tasks = sum(1 for task_id, task in tasks if task["completed"])
            total_tasks = len(tasks)
            
            text += "*✅ Задачи:*\n"
            text += f"• Всего задач: {total_tasks}\n"
            text += f"• Выполнено: {completed_tasks}\n"
            text += f"• Прогресс: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%\n\n"
        
        if notes:
            categories = {}
            for note_id, note in notes:
                cat = note["category"]
                categories[cat] = categories.get(cat, 0) + 1
            
            text += "*📝 Заметки:*\n"
            text += f"• Всего заметок: {len(notes)}\n"
            text += f"• Категории: {', '.join(categories.keys())}\n\n"
        
        if not habits and not tasks and not notes:
            text += "*📊 Данных пока нет*\n\n"
            text += "Начните добавлять привычки, задачи и заметки!"
        else:
            quote = random.choice(self.motivational_quotes)
            text += f"💫 *{quote}*"
        
        keyboard = [[InlineKeyboardButton("📊 Назад к дашборду", callback_data="dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _show_quick_add_menu(self, query):
        """Показать меню быстрого добавления"""
        keyboard = [
            [InlineKeyboardButton("🎯 Привычка", callback_data="quick_add_habit")],
            [InlineKeyboardButton("✅ Задача", callback_data="quick_add_task")],
            [InlineKeyboardButton("📝 Заметка", callback_data="quick_note")],
            [InlineKeyboardButton("📊 Назад к дашборду", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🚀 *Быстрое добавление*\n\nВыберите что хотите добавить:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def _show_tasks(self, query):
        """Показать список задач"""
        user_id = query.from_user.id
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        
        if not tasks:
            text = "✅ *Нет активных задач*\n\nДобавьте задачу командой /add_task"
        else:
            text = "✅ *Активные задачи:*\n\n"
            for i, (task_id, task) in enumerate(tasks[:5], 1):
                priority_icon = "🔴" if task["priority"] == "high" else "🟡" if task["priority"] == "medium" else "🟢"
                due_text = f" (до {task['due_date']})" if task["due_date"] else ""
                text += f"{i}. {priority_icon} {task['title']}{due_text}\n"
                if task["description"]:
                    text += f"   📝 {task['description']}\n"
        
        keyboard = [[InlineKeyboardButton("📊 Назад к дашборду", callback_data="dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

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
        
        # Команды
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("dashboard", self.dashboard))
        application.add_handler(CommandHandler("add_habit", self.add_habit))
        application.add_handler(CommandHandler("add_task", self.add_task))
        application.add_handler(CommandHandler("add_note", self.add_note))
        application.add_handler(CommandHandler("stats", self.stats))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Обработчики кнопок
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        logger.info("🚀 Starting Maximoy Bot...")
        application.run_polling()

if __name__ == "__main__":
    bot = MaximoyBot()
    bot.run()

import os
import logging
import json
import datetime
import random
import asyncio
from datetime import timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
            "mood": {},
            "achievements": {},
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
            "total_completed": 0,
            "created_date": datetime.datetime.now().isoformat(),
            "progress": {}
        }
        
        self._save_data("habits", habits)
        return habit_id

    def get_user_habits(self, user_id):
        habits = self._load_data("habits")
        user_habits = []
        
        for habit_id, habit in habits.items():
            if habit["user_id"] == user_id:
                user_habits.append((habit_id, habit))
        
        user_habits.sort(key=lambda x: (-x[1]["streak"], x[1]["created_date"]), reverse=True)
        return user_habits

    def mark_habit_done(self, habit_id):
        habits = self._load_data("habits")
        
        if habit_id in habits:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            habit = habits[habit_id]
            
            habit["progress"][today] = {
                "completed": True,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            habit["streak"] += 1
            habit["total_completed"] += 1
            if habit["streak"] > habit["best_streak"]:
                habit["best_streak"] = habit["streak"]
            
            self._save_data("habits", habits)
            return True
        return False

    # === ЗАДАЧИ ===
    def add_task(self, user_id, title, description="", priority="medium", due_date=None):
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
        tasks = self._load_data("tasks")
        user_tasks = []
        
        for task_id, task in tasks.items():
            if task["user_id"] == user_id and task["completed"] == completed:
                user_tasks.append((task_id, task))
        
        priority_order = {"high": 1, "medium": 2, "low": 3}
        user_tasks.sort(key=lambda x: (priority_order.get(x[1]["priority"], 4), x[1]["created_date"]))
        return user_tasks

    def mark_task_completed(self, task_id):
        tasks = self._load_data("tasks")
        
        if task_id in tasks:
            tasks[task_id]["completed"] = True
            self._save_data("tasks", tasks)
            return True
        return False

    # === НАСТРОЕНИЕ ===
    def add_mood_entry(self, user_id, mood, notes=""):
        mood_data = self._load_data("mood")
        
        entry_id = str(int(datetime.datetime.now().timestamp() * 1000))
        mood_data[entry_id] = {
            "user_id": user_id,
            "mood": mood,
            "notes": notes,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        self._save_data("mood", mood_data)
        return entry_id

    def get_user_mood_stats(self, user_id, days=7):
        mood_data = self._load_data("mood")
        user_moods = []
        
        cutoff_date = datetime.datetime.now() - timedelta(days=days)
        
        for entry_id, entry in mood_data.items():
            if entry["user_id"] == user_id:
                entry_date = datetime.datetime.fromisoformat(entry["timestamp"])
                if entry_date >= cutoff_date:
                    user_moods.append(entry)
        
        return user_moods

    # === ДОСТИЖЕНИЯ ===
    def unlock_achievement(self, user_id, achievement_id):
        achievements = self._load_data("achievements")
        
        if user_id not in achievements:
            achievements[user_id] = {}
        
        achievements[user_id][achievement_id] = {
            "unlocked_at": datetime.datetime.now().isoformat()
        }
        
        self._save_data("achievements", achievements)

    def get_user_achievements(self, user_id):
        achievements = self._load_data("achievements")
        return achievements.get(user_id, {})

class MaximoyBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.storage = MaximoyStorage()
        
        # Эмодзи для настроения
        self.mood_emojis = {
            "awesome": "😎",
            "happy": "😊", 
            "neutral": "😐",
            "sad": "😔",
            "angry": "😠"
        }
        
        # Достижения
        self.achievements = {
            "first_habit": {"name": "🎯 Первая привычка", "desc": "Создал первую привычку"},
            "streak_3": {"name": "🔥 Серия из 3 дней", "desc": "Выполнял привычку 3 дня подряд"},
            "streak_7": {"name": "⚡ Серия из 7 дней", "desc": "Неделя регулярности!"},
            "task_master": {"name": "✅ Мастер задач", "desc": "Выполнил 5 задач"},
            "mood_tracker": {"name": "📊 Трекер настроения", "desc": "Отметил настроение 5 раз"}
        }
        
        self.motivational_quotes = [
            "Сегодня ты ближе к цели, чем вчера! 🚀",
            "Маленькие шаги творят большие чудеса! ✨",
            "Ты справляешься лучше, чем думаешь! 💪",
            "Каждый день - новый шанс стать лучше! 🌟",
            "Успех складывается из маленьких побед! 🏆"
        ]
        
        logger.info("🤖 Maximoy Bot initialized")

    def get_main_keyboard(self):
        """Основная панель команд"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("📊 Мой прогресс"), KeyboardButton("🎯 Привычки")],
            [KeyboardButton("✅ Задачи"), KeyboardButton("😊 Настроение")],
            [KeyboardButton("🏆 Достижения"), KeyboardButton("💫 Мотивация")],
            [KeyboardButton("ℹ️ Помощь")]
        ], resize_keyboard=True)

    def get_habits_keyboard(self):
        """Панель для привычек"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("📋 Мои привычки"), KeyboardButton("➕ Новая привычка")],
            [KeyboardButton("✅ Отметить выполнение"), KeyboardButton("📈 Статистика")],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)

    def get_tasks_keyboard(self):
        """Панель для задач"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("📝 Активные задачи"), KeyboardButton("🆕 Новая задача")],
            [KeyboardButton("✔️ Завершить задачу"), KeyboardButton("📊 Прогресс")],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)

    def get_mood_keyboard(self):
        """Панель для настроения"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("😎 Отлично"), KeyboardButton("😊 Хорошо")],
            [KeyboardButton("😐 Нормально"), KeyboardButton("😔 Плохо")],
            [KeyboardButton("😠 Ужасно"), KeyboardButton("📈 Статистика")],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        logger.info(f"👤 Start command from user {user.id}")
        
        welcome_text = f"""🌟 *Добро пожаловать в Maximoy, {user.first_name}\!* 🚀

*Я твой персональный ассистент для:* 
🎯 • Отслеживания привычек
✅ • Управления задачами  
😊 • Анализа настроения
🏆 • Достижения целей

*Используй панель команд ниже чтобы начать\!* 👇"""

        await update.message.reply_text(
            welcome_text, 
            reply_markup=self.get_main_keyboard(),
            parse_mode='MarkdownV2'
        )

        # Отправляем анимированное сообщение
        await self._send_welcome_animation(update, context)

    async def _send_welcome_animation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет анимированное приветствие"""
        messages = [
            "🎯 Настраиваем систему...",
            "✅ Загружаем мотивацию...", 
            "🚀 Maximoy готов к работе!",
            "💫 Начни свой путь к продуктивности!"
        ]
        
        sent_message = await update.message.reply_text("⚡ *Запускаем Maximoy...*", parse_mode='MarkdownV2')
        
        for msg in messages:
            await asyncio.sleep(1)
            await sent_message.edit_text(f"⚡ *{msg}*", parse_mode='MarkdownV2')
        
        await asyncio.sleep(1)
        await sent_message.edit_text("🎉 *Готово\! Теперь у тебя есть супер\-сила продуктивности\!* ✨", parse_mode='MarkdownV2')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений с кнопок"""
        text = update.message.text
        user_id = update.effective_user.id
        
        logger.info(f"📨 Message from {user_id}: {text}")
        
        if text == "📊 Мой прогресс":
            await self.show_progress(update, context)
        elif text == "🎯 Привычки":
            await update.message.reply_text(
                "🎯 *Управление привычками*\n\nВыбери действие:",
                reply_markup=self.get_habits_keyboard(),
                parse_mode='MarkdownV2'
            )
        elif text == "✅ Задачи":
            await update.message.reply_text(
                "✅ *Управление задачами*\n\nВыбери действие:",
                reply_markup=self.get_tasks_keyboard(),
                parse_mode='MarkdownV2'
            )
        elif text == "😊 Настроение":
            await update.message.reply_text(
                "😊 *Как твое настроение сегодня?*\n\nВыбери подходящий вариант:",
                reply_markup=self.get_mood_keyboard(),
                parse_mode='MarkdownV2'
            )
        elif text == "🏆 Достижения":
            await self.show_achievements(update, context)
        elif text == "💫 Мотивация":
            await self.send_motivation(update, context)
        elif text == "ℹ️ Помощь":
            await self.show_help(update, context)
        elif text == "🔙 Назад":
            await update.message.reply_text(
                "🔙 *Возвращаемся в главное меню*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='MarkdownV2'
            )
        
        # Обработка привычек
        elif text == "📋 Мои привычки":
            await self.show_habits(update, context)
        elif text == "➕ Новая привычка":
            await update.message.reply_text(
                "🎯 *Создание новой привычки*\n\n"
                "Отправь сообщение в формате:\n"
                "`Название | Описание | Категория`\n\n"
                "*Пример:*\n"
                "`Утренняя зарядка | 15 минут упражнений | Здоровье`\n\n"
                "*Категории:* Здоровье, Учеба, Работа, Спорт, Творчество",
                parse_mode='MarkdownV2'
            )
            context.user_data['waiting_for'] = 'new_habit'
        elif text == "✅ Отметить выполнение":
            await self.show_habits_to_mark(update, context)
        elif text == "📈 Статистика":
            await self.show_habits_stats(update, context)
        
        # Обработка задач
        elif text == "📝 Активные задачи":
            await self.show_tasks(update, context)
        elif text == "🆕 Новая задача":
            await update.message.reply_text(
                "✅ *Создание новой задачи*\n\n"
                "Отправь сообщение в формате:\n"
                "`Название | Описание | Приоритет`\n\n"
                "*Пример:*\n"
                "`Сделать презентацию | Слайды 1\-10 | высокий`\n\n"
                "*Приоритет:* высокий, средний, низкий",
                parse_mode='MarkdownV2'
            )
            context.user_data['waiting_for'] = 'new_task'
        elif text == "✔️ Завершить задачу":
            await self.show_tasks_to_complete(update, context)
        
        # Обработка настроения
        elif text in ["😎 Отлично", "😊 Хорошо", "😐 Нормально", "😔 Плохо", "😠 Ужасно"]:
            mood_map = {
                "😎 Отлично": "awesome",
                "😊 Хорошо": "happy", 
                "😐 Нормально": "neutral",
                "😔 Плохо": "sad",
                "😠 Ужасно": "angry"
            }
            await self.record_mood(update, context, mood_map[text])
        elif text == "📈 Статистика" and update.message.reply_to_message and "настроение" in update.message.reply_to_message.text.lower():
            await self.show_mood_stats(update, context)
        
        # Обработка ввода данных
        elif context.user_data.get('waiting_for') == 'new_habit':
            await self.process_new_habit(update, context)
        elif context.user_data.get('waiting_for') == 'new_task':
            await self.process_new_task(update, context)
        elif context.user_data.get('waiting_for') == 'complete_task':
            await self.process_complete_task(update, context)
        elif context.user_data.get('waiting_for') == 'mark_habit':
            await self.process_mark_habit(update, context)

    async def show_progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает общий прогресс"""
        user_id = update.effective_user.id
        
        habits = self.storage.get_user_habits(user_id)
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        completed_tasks = self.storage.get_user_tasks(user_id, completed=True)
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        completed_today = sum(1 for habit_id, habit in habits 
                            if today in habit.get("progress", {}) and habit["progress"][today].get("completed"))
        
        text = "📊 *Твой прогресс сегодня*\n\n"
        
        # Привычки
        text += f"🎯 *Привычки:* {completed_today}/{len(habits)} выполнено\n"
        if habits:
            total_streak = sum(habit[1]["streak"] for habit in habits)
            text += f"   🔥 Общий стрик: {total_streak} дней\n"
        
        # Задачи
        text += f"\n✅ *Задачи:* {len(tasks)} активных\n"
        text += f"   🏁 Выполнено: {len(completed_tasks)}\n"
        
        # Мотивация
        if completed_today == len(habits) and len(habits) > 0:
            text += "\n🎉 *Отличная работа! Все привычки выполнены!* 🌟"
        elif completed_today > 0:
            text += f"\n💪 *Так держать! Продолжай в том же духе!*"
        else:
            text += f"\n🚀 *Время действовать! Начни с маленьких шагов!*"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def show_habits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список привычек"""
        user_id = update.effective_user.id
        habits = self.storage.get_user_habits(user_id)
        
        if not habits:
            await update.message.reply_text(
                "📝 *У тебя пока нет привычек*\n\n"
                "Нажми '➕ Новая привычка' чтобы создать первую! 🎯",
                parse_mode='MarkdownV2'
            )
            return
        
        text = "🎯 *Твои привычки:*\n\n"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for i, (habit_id, habit) in enumerate(habits, 1):
            completed = today in habit.get("progress", {}) and habit["progress"][today].get("completed")
            status = "✅" if completed else "⏳"
            text += f"{i}. {status} *{habit['name']}*\n"
            text += f"   📅 Стрик: {habit['streak']} дней"
            if habit['best_streak'] > 0:
                text += f" | 🏆 Лучший: {habit['best_streak']} дней"
            text += "\n\n"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def process_new_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает создание новой привычки"""
        text = update.message.text
        parts = [part.strip() for part in text.split("|")]
        
        if len(parts) < 1:
            await update.message.reply_text("❌ *Неверный формат\!* Нужно: `Название \| Описание \| Категория`", parse_mode='MarkdownV2')
            return
        
        name = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        category = parts[2] if len(parts) > 2 else "Общее"
        
        habit_id = self.storage.add_habit(update.effective_user.id, name, description, category)
        
        # Проверяем достижение
        habits = self.storage.get_user_habits(update.effective_user.id)
        if len(habits) == 1:
            self.storage.unlock_achievement(update.effective_user.id, "first_habit")
        
        context.user_data.pop('waiting_for', None)
        
        await update.message.reply_text(
            f"🎉 *Привычка создана\!*\n\n"
            f"*{name}*\n"
            f"📝 {description if description else 'Без описания'}\n"
            f"🏷️ {category}\n\n"
            f"Теперь отмечай выполнение каждый день\! 🔥",
            parse_mode='MarkdownV2'
        )

    async def show_habits_to_mark(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает привычки для отметки выполнения"""
        user_id = update.effective_user.id
        habits = self.storage.get_user_habits(user_id)
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        uncompleted_habits = []
        
        for habit_id, habit in habits:
            if today not in habit.get("progress", {}) or not habit["progress"][today].get("completed"):
                uncompleted_habits.append((habit_id, habit))
        
        if not uncompleted_habits:
            await update.message.reply_text("🎉 *Все привычки на сегодня выполнены\!* Ты молодец\! 🌟", parse_mode='MarkdownV2')
            return
        
        text = "✅ *Отметить выполнение:*\n\n"
        for i, (habit_id, habit) in enumerate(uncompleted_habits, 1):
            text += f"{i}. {habit['name']}\n"
        
        text += "\n*Отправь номер привычки чтобы отметить выполнение*"
        
        context.user_data['habits_to_mark'] = uncompleted_habits
        context.user_data['waiting_for'] = 'mark_habit'
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def process_mark_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает отметку выполнения привычки"""
        try:
            habit_num = int(update.message.text) - 1
            habits_to_mark = context.user_data.get('habits_to_mark', [])
            
            if 0 <= habit_num < len(habits_to_mark):
                habit_id, habit = habits_to_mark[habit_num]
                
                if self.storage.mark_habit_done(habit_id):
                    # Проверяем достижения
                    user_id = update.effective_user.id
                    habits = self.storage.get_user_habits(user_id)
                    
                    for habit_id, habit_data in habits:
                        if habit_data["streak"] == 3:
                            self.storage.unlock_achievement(user_id, "streak_3")
                        elif habit_data["streak"] == 7:
                            self.storage.unlock_achievement(user_id, "streak_7")
                    
                    context.user_data.pop('waiting_for', None)
                    context.user_data.pop('habits_to_mark', None)
                    
                    await update.message.reply_text(
                        f"🎉 *{habit['name']} отмечена как выполненная\!*\n\n"
                        f"🔥 Текущий стрик: {habit['streak'] + 1} дней\n"
                        f"💪 Так держать\!",
                        parse_mode='MarkdownV2'
                    )
                else:
                    await update.message.reply_text("❌ *Ошибка при отметке привычки*", parse_mode='MarkdownV2')
            else:
                await update.message.reply_text("❌ *Неверный номер привычки*", parse_mode='MarkdownV2')
                
        except ValueError:
            await update.message.reply_text("❌ *Отправь номер привычки* \(например: 1\)", parse_mode='MarkdownV2')

    async def show_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает активные задачи"""
        user_id = update.effective_user.id
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        
        if not tasks:
            await update.message.reply_text(
                "✅ *Нет активных задач*\n\n"
                "Нажми '🆕 Новая задача' чтобы создать первую\!",
                parse_mode='MarkdownV2'
            )
            return
        
        text = "✅ *Активные задачи:*\n\n"
        
        for i, (task_id, task) in enumerate(tasks, 1):
            priority_icon = "🔴" if task["priority"] == "high" else "🟡" if task["priority"] == "medium" else "🟢"
            due_text = f" ⏰ {task['due_date']}" if task["due_date"] else ""
            text += f"{i}. {priority_icon} *{task['title']}*{due_text}\n"
            if task["description"]:
                text += f"   📝 {task['description']}\n"
            text += "\n"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def process_new_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает создание новой задачи"""
        text = update.message.text
        parts = [part.strip() for part in text.split("|")]
        
        if len(parts) < 1:
            await update.message.reply_text("❌ *Неверный формат\!* Нужно: `Название \| Описание \| Приоритет`", parse_mode='MarkdownV2')
            return
        
        title = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        priority = parts[2] if len(parts) > 2 else "medium"
        
        task_id = self.storage.add_task(update.effective_user.id, title, description, priority)
        
        context.user_data.pop('waiting_for', None)
        
        await update.message.reply_text(
            f"✅ *Задача создана\!*\n\n"
            f"*{title}*\n"
            f"📝 {description if description else 'Без описания'}\n"
            f"🎯 Приоритет: {priority}\n\n"
            f"Не забудь выполнить\! 💪",
            parse_mode='MarkdownV2'
        )

    async def show_tasks_to_complete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает задачи для завершения"""
        user_id = update.effective_user.id
        tasks = self.storage.get_user_tasks(user_id, completed=False)
        
        if not tasks:
            await update.message.reply_text("✅ *Нет активных задач для завершения*", parse_mode='MarkdownV2')
            return
        
        text = "✔️ *Завершить задачу:*\n\n"
        for i, (task_id, task) in enumerate(tasks, 1):
            text += f"{i}. {task['title']}\n"
        
        text += "\n*Отправь номер задачи чтобы отметить как выполненную*"
        
        context.user_data['tasks_to_complete'] = tasks
        context.user_data['waiting_for'] = 'complete_task'
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def process_complete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает завершение задачи"""
        try:
            task_num = int(update.message.text) - 1
            tasks_to_complete = context.user_data.get('tasks_to_complete', [])
            
            if 0 <= task_num < len(tasks_to_complete):
                task_id, task = tasks_to_complete[task_num]
                
                if self.storage.mark_task_completed(task_id):
                    # Проверяем достижение
                    user_id = update.effective_user.id
                    completed_tasks = self.storage.get_user_tasks(user_id, completed=True)
                    if len(completed_tasks) >= 5:
                        self.storage.unlock_achievement(user_id, "task_master")
                    
                    context.user_data.pop('waiting_for', None)
                    context.user_data.pop('tasks_to_complete', None)
                    
                    await update.message.reply_text(
                        f"🎉 *Задача выполнена\!*\n\n"
                        f"*{task['title']}* \- ✅ ВЫПОЛНЕНО\n\n"
                        f"Отличная работа\! Продолжай в том же духе\! 🚀",
                        parse_mode='MarkdownV2'
                    )
                else:
                    await update.message.reply_text("❌ *Ошибка при завершении задачи*", parse_mode='MarkdownV2')
            else:
                await update.message.reply_text("❌ *Неверный номер задачи*", parse_mode='MarkdownV2')
                
        except ValueError:
            await update.message.reply_text("❌ *Отправь номер задачи* \(например: 1\)", parse_mode='MarkdownV2')

    async def record_mood(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mood: str):
        """Записывает настроение пользователя"""
        user_id = update.effective_user.id
        mood_emoji = self.mood_emojis.get(mood, "😐")
        
        self.storage.add_mood_entry(user_id, mood)
        
        # Проверяем достижение
        mood_entries = self.storage.get_user_mood_stats(user_id, days=30)
        if len(mood_entries) >= 5:
            self.storage.unlock_achievement(user_id, "mood_tracker")
        
        mood_responses = {
            "awesome": "😎 *Супер\!* Рад что у тебя отличный день\! Продолжай в том же духе\! 🌟",
            "happy": "😊 *Отлично\!* Хорошее настроение \- залог продуктивности\! 💪", 
            "neutral": "😐 *Понятно\.* Иногда спокойный день \- это тоже хорошо\! 🌈",
            "sad": "😔 *Сочувствую\.* Помни: после дождя всегда выходит солнце\! ☀️",
            "angry": "😠 *Понимаю\.* Попробуй сделать паузу и подышать глубоко\! 🧘‍♂️"
        }
        
        response = mood_responses.get(mood, "Спасибо за分享 настроения\!")
        
        await update.message.reply_text(
            f"{mood_emoji} *Настроение записано\!*\n\n{response}",
            parse_mode='MarkdownV2'
        )

    async def show_mood_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику настроения"""
        user_id = update.effective_user.id
        mood_entries = self.storage.get_user_mood_stats(user_id, days=7)
        
        if not mood_entries:
            await update.message.reply_text(
                "📊 *Нет данных о настроении за последнюю неделю*\n\n"
                "Отмечай настроение каждый день чтобы видеть статистику\!",
                parse_mode='MarkdownV2'
            )
            return
        
        mood_count = {}
        for entry in mood_entries:
            mood = entry["mood"]
            mood_count[mood] = mood_count.get(mood, 0) + 1
        
        text = "📊 *Статистика настроения за неделю:*\n\n"
        
        for mood, count in mood_count.items():
            emoji = self.mood_emojis.get(mood, "😐")
            percentage = (count / len(mood_entries)) * 100
            text += f"{emoji} {mood.capitalize()}: {count} раз ({percentage:.1f}%)\n"
        
        most_common_mood = max(mood_count.items(), key=lambda x: x[1])[0] if mood_count else None
        if most_common_mood:
            emoji = self.mood_emojis.get(most_common_mood, "😐")
            text += f"\n🎯 *Преобладающее настроение:* {emoji} {most_common_mood.capitalize()}"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def show_achievements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает достижения пользователя"""
        user_id = update.effective_user.id
        user_achievements = self.storage.get_user_achievements(user_id)
        
        text = "🏆 *Твои достижения:*\n\n"
        
        if not user_achievements:
            text += "🎯 *Достижений пока нет*\n\n"
            text += "Создавай привычки, выполняй задачи и отмечай настроение чтобы открывать достижения\! 🔓"
        else:
            for achievement_id, achievement_data in user_achievements.items():
                achievement = self.achievements.get(achievement_id, {})
                text += f"✅ *{achievement.get('name', 'Достижение')}*\n"
                text += f"   📝 {achievement.get('desc', '')}\n"
                unlocked_at = datetime.datetime.fromisoformat(achievement_data['unlocked_at']).strftime("%d.%m.%Y")
                text += f"   🗓️ Получено: {unlocked_at}\n\n"
        
        total_achievements = len(self.achievements)
        unlocked_count = len(user_achievements)
        text += f"📊 *Прогресс:* {unlocked_count}/{total_achievements} достижений"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def send_motivation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет мотивационное сообщение"""
        quote = random.choice(self.motivational_quotes)
        
        # Добавляем случайный эмодзи
        emojis = ["💫", "🚀", "🌟", "🔥", "⚡", "🎯", "🏆", "💪"]
        emoji = random.choice(emojis)
        
        await update.message.reply_text(
            f"{emoji} *Мотивация на сегодня:*\n\n{quote}",
            parse_mode='MarkdownV2'
        )

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает справку"""
        help_text = """ℹ️ *Помощь по Maximoy* 🤖

*🎯 Привычки*
• Создавай привычки и отслеживай ежедневное выполнение
• Строй стрики и ставь рекорды
• Категории: Здоровье, Учеба, Работа, Спорт, Творчество

*✅ Задачи*  
• Создавай задачи с приоритетами
• Отмечай выполнение
• Приоритеты: высокий, средний, низкий

*😊 Настроение*
• Отмечай настроение каждый день
• Следи за статистикой
• Эмодзи: 😎 Отлично, 😊 Хорошо, 😐 Нормально, 😔 Плохо, 😠 Ужасно

*🏆 Достижения*
• Открывай достижения за активность
• Собирай всю коллекцию

*💫 Советы:*
• Начинай с маленьких привычек
• Отмечай выполнение утром
• Используй панель команд для быстрого доступа

*Maximoy поможет тебе стать лучше каждый день\!* 🌟"""

        await update.message.reply_text(help_text, parse_mode='MarkdownV2')

    def run(self):
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            return
        
        application = Application.builder().token(self.token).build()
        
        # Команды
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.show_help))
        
        # Обработка текстовых сообщений (кнопки)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("🚀 Starting Maximoy Bot...")
        application.run_polling()

if __name__ == "__main__":
    bot = MaximoyBot()
    bot.run()

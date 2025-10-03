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

# ID администратора
ADMIN_ID = 6584350034

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
            "users": {},
            "admin_stats": {
                "total_users": 0,
                "total_habits": 0,
                "total_tasks": 0,
                "last_reset": None
            }
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
        admin_stats = self._load_data("admin_stats")
        
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
        
        admin_stats["total_habits"] += 1
        self._save_data("habits", habits)
        self._save_data("admin_stats", admin_stats)
        return habit_id

    def get_user_habits(self, user_id):
        habits = self._load_data("habits")
        user_habits = []
        
        for habit_id, habit in habits.items():
            if habit["user_id"] == user_id:
                user_habits.append((habit_id, habit))
        
        user_habits.sort(key=lambda x: (-x[1]["streak"], x[1]["created_date"]), reverse=True)
        return user_habits

    def get_all_habits(self):
        """Получить все привычки (для админа)"""
        return self._load_data("habits")

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
        admin_stats = self._load_data("admin_stats")
        
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
        
        admin_stats["total_tasks"] += 1
        self._save_data("tasks", tasks)
        self._save_data("admin_stats", admin_stats)
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

    def get_all_tasks(self):
        """Получить все задачи (для админа)"""
        return self._load_data("tasks")

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

    # === АДМИН ФУНКЦИИ ===
    def get_admin_stats(self):
        """Получить статистику для админа"""
        return self._load_data("admin_stats")

    def get_all_users(self):
        """Получить всех пользователей"""
        habits = self._load_data("habits")
        tasks = self._load_data("tasks")
        mood = self._load_data("mood")
        
        users = set()
        for data in [habits, tasks, mood]:
            for item in data.values():
                users.add(item["user_id"])
        
        return list(users)

    def reset_all_data(self):
        """Сбросить все данные (опасно!)"""
        default_data = {
            "habits": {},
            "tasks": {},
            "mood": {},
            "achievements": {},
            "admin_stats": {
                "total_users": 0,
                "total_habits": 0,
                "total_tasks": 0,
                "last_reset": datetime.datetime.now().isoformat()
            }
        }
        
        for filename, data in default_data.items():
            filepath = os.path.join(self.data_dir, f"{filename}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True

    def export_data(self):
        """Экспорт всех данных"""
        data = {}
        for filename in ["habits", "tasks", "mood", "achievements", "admin_stats"]:
            data[filename] = self._load_data(filename)
        return json.dumps(data, ensure_ascii=False, indent=2)

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
            "mood_tracker": {"name": "📊 Трекер настроения", "desc": "Отметил настроение 5 раз"},
            "productivity_king": {"name": "👑 Король продуктивности", "desc": "Выполнил 10 привычек и 10 задач"}
        }
        
        self.motivational_quotes = [
            "Сегодня ты ближе к цели, чем вчера! 🚀",
            "Маленькие шаги творят большие чудеса! ✨",
            "Ты справляешься лучше, чем думаешь! 💪",
            "Каждый день - новый шанс стать лучше! 🌟",
            "Успех складывается из маленьких побед! 🏆",
            "Твоя продуктивность - это суперсила! 🦸‍♂️",
            "Не сдавайся! Великие дела требуют времени! ⏳",
            "Ты создаешь свое будущее прямо сейчас! 🔮"
        ]

        # Категории для быстрого выбора
        self.categories = ["💪 Здоровье", "📚 Учеба", "💼 Работа", "🏃 Спорт", "🎨 Творчество", "🧘 Отдых", "💰 Финансы", "👥 Общение"]
        
        logger.info("🤖 Maximoy Bot initialized")

    def is_admin(self, user_id):
        """Проверка является ли пользователь админом"""
        return user_id == ADMIN_ID

    def get_main_keyboard(self, user_id):
        """Основная панель команд"""
        buttons = [
            [KeyboardButton("📊 Мой прогресс"), KeyboardButton("🎯 Привычки")],
            [KeyboardButton("✅ Задачи"), KeyboardButton("😊 Настроение")],
            [KeyboardButton("🏆 Достижения"), KeyboardButton("💫 Мотивация")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        
        # Добавляем админ-панель для админа
        if self.is_admin(user_id):
            buttons.append([KeyboardButton("👑 Админ-панель")])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

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

    def get_admin_keyboard(self):
        """Панель для админа"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("📊 Статистика системы"), KeyboardButton("👥 Все пользователи")],
            [KeyboardButton("📈 Аналитика привычек"), KeyboardButton("✅ Аналитика задач")],
            [KeyboardButton("🔄 Сбросить данные"), KeyboardButton("📤 Экспорт данных")],
            [KeyboardButton("🎮 Тестовые функции"), KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        logger.info(f"👤 Start command from user {user.id}")
        
        # Приветствие для админа
        if self.is_admin(user.id):
            welcome_text = f"""👑 *Добро пожаловать, Владыка Maximoy\!* 🎭

*Ты вошел в систему как АДМИНИСТРАТОР* ⚡

*Доступные режимы:*
🎯 • Обычный пользователь
👑 • Админ\-панель \(секретные функции\)

*Используй панель команд ниже\!* 👇"""
        else:
            welcome_text = f"""🌟 *Добро пожаловать в Maximoy, {user.first_name}\!* 🚀

*Я твой персональный ассистент для:* 
🎯 • Отслеживания привычек
✅ • Управления задачами  
😊 • Анализа настроения
🏆 • Достижения целей

*Используй панель команд ниже чтобы начать\!* 👇"""

        await update.message.reply_text(
            welcome_text, 
            reply_markup=self.get_main_keyboard(user.id),
            parse_mode='MarkdownV2'
        )

        # Анимированное приветствие
        await self._send_welcome_animation(update, context, user.id)

    async def _send_welcome_animation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Отправляет анимированное приветствие"""
        if self.is_admin(user_id):
            messages = [
                "⚡ Активируем админ-режим...",
                "🔐 Загружаются секретные функции...", 
                "👑 Админ-панель готова!",
                "🎭 Добро пожаловать в панель управления!"
            ]
        else:
            messages = [
                "🎯 Настраиваем систему...",
                "✅ Загружаем мотивацию...", 
                "🚀 Maximoy готов к работе!",
                "💫 Начни свой путь к продуктивности!"
            ]
        
        sent_message = await update.message.reply_text("⚡ *Запускаем Maximoy...*", parse_mode='MarkdownV2')
        
        for msg in messages:
            await asyncio.sleep(0.8)
            await sent_message.edit_text(f"⚡ *{msg}*", parse_mode='MarkdownV2')
        
        await asyncio.sleep(1)
        if self.is_admin(user_id):
            await sent_message.edit_text("🎭 *Режим БОГА активирован\! Все функции под контролем\!* 👑", parse_mode='MarkdownV2')
        else:
            await sent_message.edit_text("🎉 *Готово\! Теперь у тебя есть супер\-сила продуктивности\!* ✨", parse_mode='MarkdownV2')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений с кнопок"""
        text = update.message.text
        user_id = update.effective_user.id
        
        logger.info(f"📨 Message from {user_id}: {text}")
        
        # Главное меню
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
                reply_markup=self.get_main_keyboard(user_id),
                parse_mode='MarkdownV2'
            )
        
        # Админ-панель
        elif text == "👑 Админ-панель" and self.is_admin(user_id):
            await update.message.reply_text(
                "👑 *Панель управления Maximoy*\n\nВыбери действие:",
                reply_markup=self.get_admin_keyboard(),
                parse_mode='MarkdownV2'
            )
        elif text == "📊 Статистика системы" and self.is_admin(user_id):
            await self.show_system_stats(update, context)
        elif text == "👥 Все пользователи" and self.is_admin(user_id):
            await self.show_all_users(update, context)
        elif text == "📈 Аналитика привычек" and self.is_admin(user_id):
            await self.show_habits_analytics(update, context)
        elif text == "✅ Аналитика задач" and self.is_admin(user_id):
            await self.show_tasks_analytics(update, context)
        elif text == "🔄 Сбросить данные" and self.is_admin(user_id):
            await self.confirm_reset_data(update, context)
        elif text == "📤 Экспорт данных" and self.is_admin(user_id):
            await self.export_all_data(update, context)
        elif text == "🎮 Тестовые функции" and self.is_admin(user_id):
            await self.show_test_functions(update, context)
        
        # Обработка привычек
        elif text == "📋 Мои привычки":
            await self.show_habits(update, context)
        elif text == "➕ Новая привычка":
            await self.show_habit_categories(update, context)
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
        
        # Обработка категорий привычек
        elif text in self.categories and context.user_data.get('waiting_for') == 'new_habit_category':
            category = text.split(" ", 1)[1]  # Убираем эмодзи
            context.user_data['new_habit_category'] = category
            await update.message.reply_text(
                f"🎯 *Отлично\! Категория: {category}*\n\n"
                f"Теперь отправь название и описание привычки в формате:\n"
                f"`Название | Описание`\n\n"
                f"*Пример:*\n"
                f"`Утренняя зарядка | 15 минут упражнений`\n\n"
                f"*Или просто отправь название:*\n"
                f"`Чтение книги`",
                parse_mode='MarkdownV2'
            )
            context.user_data['waiting_for'] = 'new_habit_details'
        
        # Обработка ввода данных
        elif context.user_data.get('waiting_for') == 'new_habit_details':
            await self.process_new_habit(update, context)
        elif context.user_data.get('waiting_for') == 'new_task':
            await self.process_new_task(update, context)
        elif context.user_data.get('waiting_for') == 'complete_task':
            await self.process_complete_task(update, context)
        elif context.user_data.get('waiting_for') == 'mark_habit':
            await self.process_mark_habit(update, context)
        elif context.user_data.get('waiting_for') == 'confirm_reset' and self.is_admin(user_id):
            await self.process_reset_data(update, context)

    async def show_habit_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает категории для выбора"""
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton(cat) for cat in self.categories[:4]],
            [KeyboardButton(cat) for cat in self.categories[4:]],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            "🎯 *Выбери категорию для новой привычки:*\n\n"
            "💪 *Здоровье* \- спорт, питание, сон\n"
            "📚 *Учеба* \- обучение, чтение, курсы\n"
            "💼 *Работа* \- проекты, карьера\n"
            "🏃 *Спорт* \- тренировки, активность\n"
            "🎨 *Творчество* \- хобби, искусство\n"
            "🧘 *Отдых* \- медитация, релакс\n"
            "💰 *Финансы* \- бюджет, инвестиции\n"
            "👥 *Общение* \- отношения, социальная активность",
            reply_markup=keyboard,
            parse_mode='MarkdownV2'
        )
        context.user_data['waiting_for'] = 'new_habit_category'

    async def process_new_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает создание новой привычки"""
        text = update.message.text
        user_id = update.effective_user.id
        
        # Обрабатываем разные форматы ввода
        if "|" in text:
            parts = [part.strip() for part in text.split("|")]
            name = parts[0]
            description = parts[1] if len(parts) > 1 else ""
        else:
            name = text.strip()
            description = ""
        
        category = context.user_data.get('new_habit_category', 'Общее')
        
        habit_id = self.storage.add_habit(user_id, name, description, category)
        
        # Проверяем достижение
        habits = self.storage.get_user_habits(user_id)
        if len(habits) == 1:
            self.storage.unlock_achievement(user_id, "first_habit")
        
        # Очищаем временные данные
        context.user_data.pop('waiting_for', None)
        context.user_data.pop('new_habit_category', None)
        
        await update.message.reply_text(
            f"🎉 *Привычка создана\!*\n\n"
            f"*{name}*\n"
            f"📝 {description if description else 'Без описания'}\n"
            f"🏷️ {category}\n\n"
            f"Теперь отмечай выполнение каждый день\! 🔥",
            reply_markup=self.get_habits_keyboard(),
            parse_mode='MarkdownV2'
        )

    # ... (остальные методы остаются похожими, но добавляем админ-функции)

    async def show_system_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику системы для админа"""
        stats = self.storage.get_admin_stats()
        all_users = self.storage.get_all_users()
        all_habits = self.storage.get_all_habits()
        all_tasks = self.storage.get_all_tasks()
        
        # Анализируем активность
        active_today = 0
        for habit_id, habit in all_habits.items():
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            if today in habit.get("progress", {}) and habit["progress"][today].get("completed"):
                active_today += 1
        
        text = "👑 *Статистика системы Maximoy*\n\n"
        text += f"👥 *Пользователи:* {len(all_users)}\n"
        text += f"🎯 *Привычки:* {stats['total_habits']}\n"
        text += f"✅ *Задачи:* {stats['total_tasks']}\n"
        text += f"🔥 *Активных сегодня:* {active_today}\n\n"
        
        # Топ категорий привычек
        categories = {}
        for habit in all_habits.values():
            cat = habit.get('category', 'Общее')
            categories[cat] = categories.get(cat, 0) + 1
        
        if categories:
            text += "*🏆 Топ категорий:*\n"
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                text += f"• {cat}: {count}\n"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def show_all_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает всех пользователей"""
        users = self.storage.get_all_users()
        all_habits = self.storage.get_all_habits()
        all_tasks = self.storage.get_all_tasks()
        
        text = "👥 *Все пользователи системы:*\n\n"
        
        for i, user_id in enumerate(users[:20], 1):  # Ограничиваем вывод
            user_habits = [h for h in all_habits.values() if h['user_id'] == user_id]
            user_tasks = [t for t in all_tasks.values() if t['user_id'] == user_id]
            
            text += f"{i}. ID: `{user_id}`\n"
            text += f"   🎯 Привычек: {len(user_habits)}\n"
            text += f"   ✅ Задач: {len(user_tasks)}\n\n"
        
        if len(users) > 20:
            text += f"... и еще {len(users) - 20} пользователей"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def show_habits_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Аналитика привычек"""
        all_habits = self.storage.get_all_habits()
        
        if not all_habits:
            await update.message.reply_text("📊 *Нет данных о привычках*", parse_mode='MarkdownV2')
            return
        
        text = "📈 *Аналитика привычек*\n\n"
        
        # Статистика по стрикам
        streaks = [habit['streak'] for habit in all_habits.values()]
        avg_streak = sum(streaks) / len(streaks) if streaks else 0
        max_streak = max(streaks) if streaks else 0
        
        text += f"📊 *Общая статистика:*\n"
        text += f"• Всего привычек: {len(all_habits)}\n"
        text += f"• Средний стрик: {avg_streak:.1f} дней\n"
        text += f"• Максимальный стрик: {max_streak} дней\n\n"
        
        # Самые популярные привычки
        habit_names = {}
        for habit in all_habits.values():
            name = habit['name']
            habit_names[name] = habit_names.get(name, 0) + 1
        
        if habit_names:
            text += "🏆 *Самые популярные привычки:*\n"
            for name, count in sorted(habit_names.items(), key=lambda x: x[1], reverse=True)[:5]:
                text += f"• {name}: {count}\n"
        
        await update.message.reply_text(text, parse_mode='MarkdownV2')

    async def confirm_reset_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение сброса данных"""
        await update.message.reply_text(
            "⚠️ *ВНИМАНИЕ: ОПАСНАЯ ОПЕРАЦИЯ*\n\n"
            "Ты собираешься удалить ВСЕ данные системы:\n"
            "• Все привычки пользователей\n"
            "• Все задачи\n"
            "• Всю статистику\n"
            "• Все достижения\n\n"
            "❌ *ЭТО ДЕЙСТВИЕ НЕОБРАТИМО*\n\n"
            "Для подтверждения отправь: `ДА, УДАЛИТЬ ВСЕ`",
            parse_mode='MarkdownV2'
        )
        context.user_data['waiting_for'] = 'confirm_reset'

    async def process_reset_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает сброс данных"""
        if update.message.text == "ДА, УДАЛИТЬ ВСЕ":
            if self.storage.reset_all_data():
                await update.message.reply_text(
                    "♻️ *Все данные системы были сброшены\!*\n\n"
                    "База данных очищена\. Начинаем с чистого листа\! 📝",
                    parse_mode='MarkdownV2'
                )
            else:
                await update.message.reply_text("❌ *Ошибка при сбросе данных*", parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("✅ *Операция отменена*", parse_mode='MarkdownV2')
        
        context.user_data.pop('waiting_for', None)

    async def export_all_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт всех данных"""
        try:
            data = self.storage.export_data()
            # Сохраняем во временный файл
            filename = f"maximoy_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # В реальном боте здесь был бы код для сохранения файла
            # Для демонстрации отправляем как сообщение (ограничение по длине)
            preview = data[:4000] + "\n\n..." if len(data) > 4000 else data
            
            await update.message.reply_text(
                f"📤 *Экспорт данных системы*\n\n"
                f"```json\n{preview}\n```\n\n"
                f"*Всего данных:* {len(data)} символов",
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ *Ошибка экспорта:* {e}", parse_mode='MarkdownV2')

    async def show_test_functions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовые функции для админа"""
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("🎲 Тест уведомление"), KeyboardButton("🎯 Тест достижение")],
            [KeyboardButton("📊 Тест статистика"), KeyboardButton("🔙 Назад в админку")]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            "🎮 *Тестовые функции*\n\n"
            "Здесь можно тестировать различные функции системы:",
            reply_markup=keyboard,
            parse_mode='MarkdownV2'
        )

    # ... (остальные методы привычек, задач, настроения остаются похожими)

    def run(self):
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            return
        
        application = Application.builder().token(self.token).build()
        
        # Команды
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.show_help))
        application.add_handler(CommandHandler("admin", self.show_admin_panel))
        
        # Обработка текстовых сообщений (кнопки)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("🚀 Starting Maximoy Bot...")
        application.run_polling()

    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает админ-панель по команде /admin"""
        if self.is_admin(update.effective_user.id):
            await update.message.reply_text(
                "👑 *Админ-панель активирована по команде*\n\nВыбери действие:",
                reply_markup=self.get_admin_keyboard(),
                parse_mode='MarkdownV2'
            )
        else:
            await update.message.reply_text("❌ *У тебя нет доступа к этой команде*", parse_mode='MarkdownV2')

if __name__ == "__main__":
    bot = MaximoyBot()
    bot.run()

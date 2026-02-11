import telebot
from telebot import types
import os
from dotenv import load_dotenv
import psycopg2
from datetime import datetime, timedelta
import threading
import pandas as pd
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import time
from flask import Flask, request
import json
import socket
import sys
import atexit

# Путь к файлу блокировки
LOCK_FILE = "bot.lock"

def check_if_running():
    """Проверяет, запущен ли другой экземпляр, используя файл блокировки."""
    if os.path.exists(LOCK_FILE):
        try:
            # Пытаемся удалить устаревший файл блокировки
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                # Проверяем, работает ли процесс
                os.kill(pid, 0)
                print(f"Другой экземпляр бота уже запущен с PID {pid}")
                sys.exit(1)
            except OSError:
                # Процесс не работает, удаляем устаревший файл блокировки
                os.remove(LOCK_FILE)
        except (ValueError, OSError):
            # Неверный PID в файле или ошибка при удалении
            os.remove(LOCK_FILE)
    
    # Создаем файл блокировки
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup():
    """Удаляет файл блокировки при выходе."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        print(f"Ошибка при удалении файла блокировки: {e}")

# Регистрируем функцию очистки
atexit.register(cleanup)

# Проверяем, запущен ли другой экземпляр
check_if_running()

# Создаем Flask приложение
app = Flask(__name__)

# Укажите путь к файлу .env вручную
dotenv_path = os.path.join(os.path.dirname(__file__), 'Bot.env')
load_dotenv(dotenv_path=dotenv_path)

# Получаем токен бота из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    print("Ошибка: Не найдена переменная окружения BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для отслеживания времени последнего уведомления по задаче
last_notification = {}


def get_duty_person_id():
    """Получает Telegram ID текущего дежурного."""
    try:
        # Получаем имя текущего дежурного из расписания
        responsible_person = get_responsible_person()
        if not responsible_person or responsible_person == "Ответственный сотрудник не найден.":
            print("Не удалось найти дежурного в расписании")
            return None

        # Разбиваем полное имя на имя и фамилию
        name_parts = responsible_person.split()
        if len(name_parts) != 2:
            print(f"Неверный формат имени дежурного: {responsible_person}")
            return None

        first_name, last_name = name_parts

        # Ищем пользователя в базе данных
        conn = get_db_connection()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id 
            FROM users 
            WHERE first_name = %s AND last_name = %s
            """,
            (first_name, last_name)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return result[0]
        else:
            print(f"Дежурный {responsible_person} не найден в базе пользователей")
            return None

    except Exception as e:
        print(f"Ошибка при получении ID дежурного: {e}")
        return None

def notify_duty_person(task_id, description, priority):
    """Отправляет уведомление текущему дежурному."""
    try:
        # Получаем ID дежурного
        duty_person_id = get_duty_person_id()
        if not duty_person_id:
            print("Не удалось определить ID дежурного")
            return False

        # Создаем клавиатуру с кнопкой взятия в работу
        markup = types.InlineKeyboardMarkup()
        take_task = types.InlineKeyboardButton(
            "✅ Взять в работу",
            callback_data=f"select_problem_{task_id}"
        )
        markup.add(take_task)

        # Формируем текст уведомления
        message_text = (
            f"🔔 *Напоминание о задаче*\n\n"
            f"📋 Задача #{task_id}\n"
            f"📝 Описание: {description}\n"
            f"🎯 Приоритет: {priority}\n\n"
            f"❗️ Эта задача требует внимания"
        )

        # Отправляем сообщение
        bot.send_message(
            duty_person_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return True

    except Exception as e:
        print(f"Ошибка при отправке уведомления дежурному: {e}")
        return False

def check_open_tasks():
    """Проверяет открытые задачи и отправляет уведомления дежурному."""
    while True:
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, description, priority 
                    FROM problems 
                    WHERE status = 'open'
                    """
                )
                open_tasks = cursor.fetchall()
                cursor.close()
                conn.close()

                current_time = time.time()
                
                if open_tasks:
                    for task in open_tasks:
                        task_id = task[0]
                        # Проверяем, прошла ли минута с последнего уведомления
                        if task_id not in last_notification or \
                           (current_time - last_notification[task_id]) >= 60:
                            if notify_duty_person(task_id, task[1], task[2]):
                                last_notification[task_id] = current_time
                                print(f"Отправлено уведомление о задаче #{task_id}")
                            else:
                                print(f"Не удалось отправить уведомление о задаче #{task_id}")

        except Exception as e:
            print(f"Ошибка при проверке открытых задач: {e}")
        
        time.sleep(60)  # Пауза в 60 секунд

# Подключение к базе данных PostgreSQL
def get_db_connection():
    """Устанавливает соединение с базой данных PostgreSQL."""
    try:
        # Выводим параметры подключения (без пароля)
        print(f"\nПодключение к БД:")
        print(f"dbname: {os.getenv('DB_NAME')}")
        print(f"user: {os.getenv('DB_USER')}")
        print(f"host: {os.getenv('DB_HOST')}")
        print(f"port: {os.getenv('DB_PORT')}")
        
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        
        # Проверяем существование таблиц
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        print("\nНайденные таблицы:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Показываем количество записей в каждой таблице
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  Количество записей: {count}")
        
        print("\nУспешное подключение к базе данных")
        return conn
    except Exception as e:
        print(f"\nОшибка при подключении к базе данных: {e}")
        return None

# --- Функции для работы с системой мониторинга ---
active_users = {}  # Словарь для хранения пользователей, взявших алерты в работу

def mute_user_for_alert(user_id, duration):
    """Отключает уведомления для пользователя на указанное время."""
    active_users[user_id] = True
    update_active_users()  # <--- добавьте это
    threading.Timer(duration * 60, unmute_user, args=[user_id]).start()

def unmute_user(user_id):
    """Снимает мут с пользователя."""
    if user_id in active_users:
        del active_users[user_id]
        update_active_users()  # <--- добавьте это
        print(f"Пользователь {user_id} снова получает уведомления.")

def get_schedule_from_db():
    """Получает расписание из базы данных."""
    try:
        conn = get_db_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        cursor.execute("SELECT name, shift_start, shift_end FROM schedule")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Ошибка при выполнении запроса к базе данных: {e}")
        return []

def get_schedule_from_excel():
    """Читает расписание из CSV-файла и преобразует столбец 'Дата' в формат datetime."""
    schedule_path = os.path.join(os.path.dirname(__file__), 'schedule.csv')
    try:
        # Пробуем разные варианты чтения файла
        try:
            df = pd.read_csv(schedule_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(schedule_path, encoding='cp1251')
            except UnicodeDecodeError:
                df = pd.read_csv(schedule_path, encoding='utf-8-sig')
        
        # Проверяем и исправляем заголовки если они неправильные
        if 'Дата' not in df.columns:
            # Переименовываем колонки
            df.columns = ['Дата', 'Дежурный']
        
        # Преобразуем 'Дата' в формат datetime
        df['Дата'] = pd.to_datetime(df['Дата'], format='%Y-%m-%d').dt.date
        return df
    except FileNotFoundError:
        print(f"Ошибка: Файл расписания не найден: {schedule_path}")
        return pd.DataFrame(columns=['Дата', 'Дежурный'])
    except Exception as e:
        print(f"Ошибка при чтении файла расписания: {e}")
        print("Текущие колонки в файле:", df.columns if 'df' in locals() else "файл не прочитан")
        return pd.DataFrame(columns=['Дата', 'Дежурный'])

def get_responsible_person():
    """Определяет ответственного сотрудника на основе текущего расписания."""
    df = get_schedule_from_excel()
    today = datetime.now().date()
    current_shift = df[df['Дата'] == today]
    if not current_shift.empty:
        return current_shift.iloc[0]['Дежурный']
    return "Ответственный сотрудник не найден."

def get_current_duty():
    """Получает текущих дежурных из базы данных."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM schedule WHERE shift_start <= NOW() AND shift_end >= NOW()")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Ошибка при выполнении запроса к базе данных: {e}")
        return []

def update_monitoring_data():
    """Обновляет данные из системы мониторинга."""
    print("Данные обновлены.")

def add_user_to_db(user_id, username, first_name, last_name):
    """Добавляет нового пользователя в базу данных, если его там нет."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            # Если пользователь не найден, добавляем его
            cursor.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (user_id, username, first_name, last_name)
            )
            conn.commit()
            print(f"Пользователь {user_id} добавлен в базу данных.")
        conn.close()
    except Exception as e:
        print(f"Ошибка при добавлении пользователя в базу данных: {e}")

def get_open_problems():
    """Получает список открытых проблем из базы данных, отсортированных по номеру."""
    try:
        conn = get_db_connection()
        if conn is None:
            print("Ошибка: Не удалось подключиться к базе данных")
            return []
        cursor = conn.cursor()
        
        # Проверяем содержимое таблицы problems
        cursor.execute("SELECT COUNT(*) FROM problems")
        total_count = cursor.fetchone()[0]
        print(f"\nВсего задач в таблице: {total_count}")
        
        cursor.execute("SELECT id, description, status, priority FROM problems")
        all_problems = cursor.fetchall()
        print("\nВсе задачи в таблице:")
        for p in all_problems:
            print(f"ID: {p[0]}, Статус: {p[2]}, Приоритет: {p[3]}, Описание: {p[1][:50]}...")
        
        # Получаем открытые задачи
        print("\nВыполняем запрос для получения открытых задач...")
        cursor.execute("""
            SELECT id, description, priority 
            FROM problems 
            WHERE status = 'open' 
            ORDER BY 
                CASE priority
                    WHEN 'критический' THEN 1
                    WHEN 'высокий' THEN 2
                    WHEN 'нормальный' THEN 3
                    WHEN 'низкий' THEN 4
                END,
                id ASC
        """)
        problems = cursor.fetchall()
        
        print(f"\nНайдено {len(problems)} открытых задач:")
        for problem in problems:
            print(f"Задача #{problem[0]}: {problem[1][:50]}... (Приоритет: {problem[2]})")
        
        conn.close()
        return problems
    except Exception as e:
        print(f"Ошибка при получении списка проблем: {e}")
        print(f"Тип ошибки: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return []

def assign_problem_to_user(problem_id, user_id):
    """Назначает проблему пользователю."""
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE problems
            SET status = 'in_progress', assigned_user_id = %s, assigned_at = NOW()
            WHERE id = %s AND status = 'open'
            RETURNING id
            """,
            (user_id, problem_id)
        )
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if result:
            update_open_problems()
            print(f"Проблема {problem_id} назначена пользователю {user_id}.")
            return True
        return False
        
    except Exception as e:
        print(f"Ошибка при назначении проблемы: {e}")
        return False

def get_user_current_problem(user_id):
    """Получает текущую проблему пользователя."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, description, priority FROM problems
            WHERE assigned_user_id = %s AND status = 'in_progress'
            """,
            (user_id,)
        )
        problem = cursor.fetchone()
        conn.close()
        return problem
    except Exception as e:
        print(f"Ошибка при получении текущей проблемы: {e}")
        return None

def is_user_registered(user_id):
    """Проверяет, зарегистрирован ли пользователь в системе."""
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке регистрации пользователя: {e}")
        return False

# --- Метрики для Prometheus ---
REQUEST_COUNT = Counter('bot_requests_total', 'Общее количество запросов к боту', ['command'])
DB_CONNECTION_ERRORS = Counter('db_connection_errors_total', 'Количество ошибок подключения к базе данных')
MESSAGE_PROCESSING_TIME = Histogram('message_processing_time_seconds', 'Время обработки сообщений')
ACTIVE_USERS = Gauge('bot_active_users', 'Количество активных пользователей')
OPEN_PROBLEMS = Gauge('bot_open_problems', 'Количество открытых инцидентов')
MESSAGE_ERRORS = Counter('bot_message_errors_total', 'Количество ошибок при обработке сообщений')

# Запуск HTTP-сервера для метрик Prometheus
def start_metrics_server():
    start_http_server(8000)  # Метрики будут доступны на порту 8000
    print("Сервер метрик Prometheus запущен на порту 8000")

# Обновление метрики активных пользователей
def update_active_users():
    ACTIVE_USERS.set(len(active_users))

# Обновление метрики открытых инцидентов
def update_open_problems():
    try:
        problems = get_open_problems()
        OPEN_PROBLEMS.set(len(problems))
    except Exception as e:
        print(f"Ошибка при обновлении метрики открытых инцидентов: {e}")

# Обертка для измерения времени обработки сообщений
def track_processing_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        MESSAGE_PROCESSING_TIME.observe(duration)
        return result
    return wrapper

# Обертка для обработки ошибок сообщений
def track_message_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            MESSAGE_ERRORS.inc()  # Увеличиваем счетчик ошибок
            print(f"Ошибка при обработке сообщения: {e}")
            raise e
    return wrapper

# --- Аутентификация и авторизация операторов ---

# Список разрешённых операторов (user_id Telegram)
AUTHORIZED_OPERATORS = set([
    1528818749,
    1257518328,
    987654321,  # Добавьте user_id разрешённых операторов
    # ...
])

def is_authorized(user_id):
    """Проверяет, является ли пользователь авторизованным оператором."""
    return user_id in AUTHORIZED_OPERATORS

def require_operator(func):
    """Декоратор для проверки авторизации оператора."""
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        if not is_authorized(user_id):
            bot.send_message(message.chat.id, "❌ У вас нет прав для выполнения этой операции.")
            return
        return func(message, *args, **kwargs)
    return wrapper

def require_operator_callback(func):
    """Декоратор для проверки авторизации оператора в callback."""
    def wrapper(call, *args, **kwargs):
        user_id = call.from_user.id
        if not is_authorized(user_id):
            bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой операции.", show_alert=True)
            return
        return func(call, *args, **kwargs)
    return wrapper

# --- Применение авторизации к критическим функциям ---

@bot.message_handler(commands=['addshift'])
@require_operator
def add_shift_command(message):
    """Обработчик команды добавления смены."""
    bot.send_message(
        message.chat.id,
        "Введите дату и ФИО дежурного в формате:\n"
        "ДД.ММ Имя Фамилия\n\n"
        "Например: 25.05 Иван Иванов"
    )
    bot.register_next_step_handler(message, process_add_shift)

@bot.message_handler(func=lambda message: message.text == "Назначить смену")
@require_operator
def add_shift_button(message):
    """Обработчик кнопки 'Назначить смену'."""
    add_shift_command(message)

def process_add_shift(message):
    """Обрабатывает ввод данных для новой смены."""
    try:
        # Разбираем сообщение
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат. Используйте: ДД.ММ Имя Фамилия"
            )
            return

        date_str, first_name, last_name = parts

        # Проверяем формат даты
        try:
            # Добавляем текущий год к введенной дате
            current_year = datetime.now().year
            date = datetime.strptime(f"{date_str}.{current_year}", '%d.%m.%Y')
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат даты. Используйте ДД.ММ"
            )
            return

        # Получаем текущую дату для сравнения
        current_date = datetime.now()
        if date.date() < current_date.date():
            # Если дата в прошлом текущего года, добавляем год
            date = date.replace(year=current_year + 1)

        # Загружаем текущее расписание
        df = get_schedule_from_excel()
        new_duty = f"{first_name} {last_name}"

        # Преобразуем дату в строку в формате YYYY-MM-DD для сохранения
        date_for_csv = date.strftime('%Y-%m-%d')

        # Проверяем, есть ли уже дежурный на эту дату
        if not df.empty and (df['Дата'] == date.date()).any():
            # Получаем старого дежурного
            old_duty = df.loc[df['Дата'] == date.date(), 'Дежурный'].iloc[0]
            # Обновляем дежурного
            df.loc[df['Дата'] == date.date(), 'Дежурный'] = new_duty
            bot.send_message(
                message.chat.id,
                f"✅ Дежурство обновлено:\n"
                f"Дата: {date.strftime('%d.%m')}\n"
                f"👤 Старый дежурный: {old_duty}\n"
                f"👤 Новый дежурный: {new_duty}"
            )
        else:
            # Добавляем новую смену в расписание
            new_row = {'Дата': date_for_csv, 'Дежурный': new_duty}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            bot.send_message(
                message.chat.id,
                f"✅ Дежурство добавлено:\n"
                f"Дата: {date.strftime('%d.%m')}\n"
                f"👤 Дежурный: {new_duty}"
            )
        
        # Сортируем по дате
        df = df.sort_values('Дата')
        
        # Сохраняем обновленное расписание
        schedule_path = os.path.join(os.path.dirname(__file__), 'schedule.csv')
        df.to_csv(schedule_path, index=False)

    except Exception as e:
        print(f"Ошибка при добавлении смены: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при добавлении дежурства"
        )

@bot.message_handler(func=lambda message: message.text == "Информация о боте")
def bot_info(message):
    """Обработчик команды 'Информация о боте'. Возвращает описание функционала."""
    info_text = (
        "👋 *Привет! Я бот для управления инцидентами и дежурствами.*\n\n"
        "📋 *Основные возможности:*\n"
        "1️⃣ *Управление задачами:*\n"
        "   • Просмотр открытых задач\n"
        "   • Взятие задач в работу\n"
        "   • Отслеживание статуса задач\n"
        "   • Отложение задач\n\n"
        "2️⃣ *Система дежурств:*\n"
        "   • Просмотр текущего дежурного\n"
        "   • Расписание на неделю\n"
        "   • Автоматическое оповещение дежурных\n\n"
        "3️⃣ *Интеграции:*\n"
        "   • Получение алертов от Prometheus\n"
        "   • Метрики в реальном времени\n"
        "   • Webhook для внешних систем\n\n"
        "⚙️ *Команды:*\n"
        "• /start - запуск бота и главное меню\n"
        "• /register - регистрация в системе\n"
        "• /addshift - добавить смену (для админов)\n"
        "• /users - список пользователей (для админов)\n\n"
        "🔔 *Уведомления:*\n"
        "• Автоматические напоминания о задачах\n"
        "• Оповещения о новых инцидентах\n"
        "• Уведомления о смене дежурного\n\n"
        "💡 *Полезные функции:*\n"
        "• Автоматическое назначение задач\n"
        "• Приоритизация инцидентов\n"
        "• Отслеживание времени реакции\n"
        "• Защита от дублирования запуска\n\n"
        "🔐 *Безопасность:*\n"
        "• Разграничение прав доступа\n"
        "• Защита админских функций\n"
        "• Безопасное хранение токенов\n\n"
        "По всем вопросам обращайтесь к администратору системы 👨‍💻"
    )
    bot.send_message(message.chat.id, info_text, parse_mode="Markdown")

# --- Обработчики команд бота ---
@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start. Создает клавиатуру с меню."""
    print(f"Получена команда /start от пользователя {message.from_user.id}")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Работа")
    item2 = types.KeyboardButton("Текущее расписание")
    item3 = types.KeyboardButton("Текущие дежурные")
    item5 = types.KeyboardButton("Информация о боте")
    item6 = types.KeyboardButton("Регистрация")
    item7 = types.KeyboardButton("Список пользователей")
    item8 = types.KeyboardButton("Назначить смену")
    markup.add(item1, item2, item3)
    markup.add(item5, item6)
    if is_authorized(message.from_user.id):  # Показываем админские кнопки только администраторам
        markup.add(item7, item8)
    bot.send_message(message.chat.id, "Привет! Что хотите сделать?", reply_markup=markup)

@bot.message_handler(commands=['register'])
def register_command(message):
    """Обработчик команды /register. Запрашивает у пользователя его имя и фамилию."""
    bot.send_message(message.chat.id, "Пожалуйста, введите ваше имя и фамилию в формате: Имя Фамилия")
    bot.register_next_step_handler(message, process_registration)

@bot.message_handler(func=lambda message: message.text == "Регистрация")
def register_button(message):
    """Обработчик кнопки 'Регистрация'."""
    register_command(message)

def process_registration(message):
    """Обрабатывает ввод имени и фамилии пользователя."""
    try:
        # Разбиваем сообщение на имя и фамилию
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "Пожалуйста, введите только имя и фамилию, разделенные пробелом.")
            register_command(message)
            return

        first_name, last_name = parts
        user_id = message.from_user.id
        username = message.from_user.username

        # Подключаемся к базе данных
        conn = get_db_connection()
        if conn is None:
            bot.send_message(message.chat.id, "Извините, произошла ошибка при подключении к базе данных.")
            return

        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        existing_user = cursor.fetchone()

        if existing_user:
            # Обновляем данные существующего пользователя
            cursor.execute(
                """
                UPDATE users 
                SET first_name = %s, last_name = %s, username = %s
                WHERE user_id = %s
                """,
                (first_name, last_name, username, user_id)
            )
            response_message = "Ваши данные успешно обновлены!"
        else:
            # Добавляем нового пользователя
            cursor.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, username, first_name, last_name)
            )
            response_message = "Регистрация успешно завершена!"

        conn.commit()
        conn.close()

        # Создаем клавиатуру с главным меню
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("Работа")
        item2 = types.KeyboardButton("Текущее расписание")
        item3 = types.KeyboardButton("Текущие дежурные")
        item5 = types.KeyboardButton("Информация о боте")
        item6 = types.KeyboardButton("Регистрация")
        item7 = types.KeyboardButton("Список пользователей")
        item8 = types.KeyboardButton("Назначить смену")
        markup.add(item1, item2, item3)
        markup.add(item5, item6)
        if is_authorized(user_id):  # Показываем админские кнопки только администраторам
            markup.add(item7, item8)

        # Отправляем сообщение об успешной регистрации вместе с меню
        bot.send_message(message.chat.id, response_message, reply_markup=markup)

    except Exception as e:
        print(f"Ошибка при регистрации пользователя: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при регистрации. Пожалуйста, попробуйте еще раз.")

@bot.message_handler(func=lambda message: message.text == "Работа")
def work_on_problem(message):
    """Обработчик команды 'Работа'. Показывает меню управления задачами."""
    markup = types.InlineKeyboardMarkup()
    
    # Основные кнопки
    view_my_task = types.InlineKeyboardButton(
        text="Моя текущая задача",
        callback_data="view_my_task"
    )
    take_task = types.InlineKeyboardButton(
        text="Взять задачу",
        callback_data="take_task"
    )
    view_active = types.InlineKeyboardButton(
        text="Активные задачи",
        callback_data="view_active_tasks"
    )
    back_button = types.InlineKeyboardButton(
        text="Назад в главное меню",
        callback_data="back_to_main_menu"
    )
    
    markup.add(view_my_task)
    markup.add(take_task)
    markup.add(view_active)
    markup.add(back_button)
    
    bot.send_message(
        message.chat.id,
        "Выберите действие:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "view_my_task")
def view_my_task(call):
    """Показывает текущую задачу пользователя."""
    user_id = call.from_user.id
    current_problem = get_user_current_problem(user_id)
    
    if current_problem:
        problem_id, description, priority = current_problem
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Кнопки управления задачей
        pause = types.InlineKeyboardButton("⏸ Отложить", callback_data=f"pause_{problem_id}")
        back = types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_work_menu")
        
        markup.add(pause)
        markup.add(back)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📋 Ваша текущая задача:\n\n🔹 Задача #{problem_id}\n📝 {description}\n🎯 Приоритет: {priority}",
            reply_markup=markup
        )
    else:
        markup = types.InlineKeyboardMarkup()
        back = types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_work_menu")
        markup.add(back)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="У вас нет текущих задач в работе.",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('pause_'))
def pause_task(call):
    """Обработчик кнопки 'Отложить'."""
    try:
        problem_id = int(call.data.split('_')[1])
        
        # Подключаемся к базе данных
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Обновляем статус задачи
        cursor.execute(
            """
            UPDATE problems 
            SET status = 'open', 
                assigned_user_id = NULL, 
                assigned_at = NULL 
            WHERE id = %s AND status = 'in_progress'
            RETURNING id
            """,
            (problem_id,)
        )
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        if result:
            # Возвращаемся в меню работы
            markup = types.InlineKeyboardMarkup()
            back = types.InlineKeyboardButton("◀️ В меню работы", callback_data="back_to_work_menu")
            markup.add(back)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Задача #{problem_id} отложена и возвращена в общий список",
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "❌ Не удалось отложить задачу", show_alert=True)
    
    except Exception as e:
        print(f"Ошибка при откладывании задачи: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка", show_alert=True)

def is_user_registered(user_id):
    """Проверяет, зарегистрирован ли пользователь в системе."""
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке регистрации пользователя: {e}")
        return False

@bot.callback_query_handler(func=lambda call: call.data == "take_task")
def take_task(call):
    """Показывает список доступных задач."""
    user_id = call.from_user.id
    
    # Проверяем регистрацию пользователя
    if not is_user_registered(user_id):
        markup = types.InlineKeyboardMarkup()
        register_button = types.InlineKeyboardButton(
            "Зарегистрироваться",
            callback_data="start_registration"
        )
        back_button = types.InlineKeyboardButton(
            "Назад",
            callback_data="back_to_work_menu"
        )
        markup.add(register_button)
        markup.add(back_button)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="⚠️ Для взятия задач в работу необходимо зарегистрироваться в системе.",
            reply_markup=markup
        )
        return

    print("Вызвана функция take_task")
    problems = get_open_problems()
    print(f"Получено {len(problems)} открытых задач")
    
    markup = types.InlineKeyboardMarkup()
    if problems:
        for problem in problems:
            problem_id, description, priority = problem
            print(f"Добавляем кнопку для задачи #{problem_id}")
            button = types.InlineKeyboardButton(
                text=f"#{problem_id}: {description[:50]} [{priority}]",
                callback_data=f"select_problem_{problem_id}"
            )
            markup.add(button)
    
    back_button = types.InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_work_menu"
    )
    markup.add(back_button)
    
    message_text = "Выберите задачу из списка:" if problems else "Нет доступных задач для выбора."
    print(f"Отправляем сообщение: {message_text}")
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message_text,
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "start_registration")
def start_registration(call):
    """Начинает процесс регистрации."""
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    register_command(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_problem_"))
def select_problem(call):
    """Обработчик выбора задачи."""
    try:
        user_id = call.from_user.id
        
        # Проверяем регистрацию пользователя
        if not is_user_registered(user_id):
            bot.answer_callback_query(
                call.id,
                text="⚠️ Для взятия задач в работу необходимо зарегистрироваться в системе.",
                show_alert=True
            )
            return
            
        problem_id = int(call.data.split('_')[2])
        
        # Проверяем, нет ли у пользователя уже взятой задачи
        current_task = get_user_current_problem(user_id)
        if current_task:
            bot.answer_callback_query(
                call.id,
                text="У вас уже есть активная задача. Сначала завершите её.",
                show_alert=True
            )
            return
        
        # Назначаем задачу пользователю
        if assign_problem_to_user(problem_id, user_id):
            # Отключаем уведомления для этой задачи
            if problem_id in last_notification:
                del last_notification[problem_id]
            
            markup = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="Назад",
                callback_data="back_to_work_menu"
            )
            markup.add(back_button)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Вы взяли задачу #{problem_id} в работу",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id, text="Задача успешно взята в работу")
        else:
            bot.answer_callback_query(
                call.id,
                text="Не удалось взять задачу. Возможно, она уже взята другим пользователем.",
                show_alert=True
            )
    except Exception as e:
        print(f"Ошибка при выборе задачи: {e}")
        bot.answer_callback_query(
            call.id,
            text="Произошла ошибка при выборе задачи",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "view_active_tasks")
def view_active_tasks_callback(call):
    """Показывает список активных задач."""
    try:
        conn = get_db_connection()
        if conn is None:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Ошибка подключения к базе данных."
            )
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.description, p.priority, p.assigned_at,
                   u.first_name, u.last_name, u.username
            FROM problems p
            LEFT JOIN users u ON p.assigned_user_id = u.user_id
            WHERE p.status = 'in_progress'
            ORDER BY p.priority DESC, p.assigned_at ASC
        """)
        tasks = cursor.fetchall()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(
            text="Назад",
            callback_data="back_to_work_menu"
        )
        markup.add(back_button)

        if not tasks:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="В данный момент нет активных задач.",
                reply_markup=markup
            )
            return

        # Формируем сообщение со списком активных задач
        message_text = "📋 *Активные задачи:*\n\n"
        for task in tasks:
            task_id, description, priority, assigned_at, first_name, last_name, username = task
            message_text += f"🔸 *Задача #{task_id}*\n"
            message_text += f"└ Описание: {description[:100]}\n"
            message_text += f"└ Приоритет: {priority}\n"
            message_text += f"└ Исполнитель: {first_name} {last_name}"
            if username:
                message_text += f" (@{username})"
            message_text += f"\n└ Взята в работу: {assigned_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        # Отправляем сообщение
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        print(f"Ошибка при получении списка активных задач: {e}")
        markup = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(
            text="Назад",
            callback_data="back_to_work_menu"
        )
        markup.add(back_button)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Произошла ошибка при получении списка активных задач.",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_work_menu")
def back_to_work_menu(call):
    """Возвращает в главное меню работы."""
    markup = types.InlineKeyboardMarkup()
    
    view_my_task = types.InlineKeyboardButton(
        text="Моя текущая задача",
        callback_data="view_my_task"
    )
    take_task = types.InlineKeyboardButton(
        text="Взять задачу",
        callback_data="take_task"
    )
    view_active = types.InlineKeyboardButton(
        text="Активные задачи",
        callback_data="view_active_tasks"
    )
    back_button = types.InlineKeyboardButton(
        text="Назад в главное меню",
        callback_data="back_to_main_menu"
    )
    
    markup.add(view_my_task)
    markup.add(take_task)
    markup.add(view_active)
    markup.add(back_button)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Выберите действие:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main_menu")
def back_to_main_menu(call):
    """Возвращает пользователя в главное меню."""
    try:
        # Удаляем инлайн-клавиатуру
        bot.delete_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        
        # Отправляем новое сообщение с главным меню
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("Работа")
        item2 = types.KeyboardButton("Текущее расписание")
        item3 = types.KeyboardButton("Текущие дежурные")
        item5 = types.KeyboardButton("Информация о боте")
        item6 = types.KeyboardButton("Регистрация")
        item7 = types.KeyboardButton("Список пользователей")
        item8 = types.KeyboardButton("Назначить смену")
        markup.add(item1, item2, item3)
        markup.add(item5, item6)
        if is_authorized(call.from_user.id):
            markup.add(item7, item8)
        
        bot.send_message(
            call.message.chat.id,
            "Выберите действие:",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка при возврате в главное меню: {e}")
        bot.answer_callback_query(
            call.id,
            text="Произошла ошибка при возврате в главное меню"
        )

@bot.message_handler(func=lambda message: message.text == "Текущее расписание")
def current_schedule(message):
    """Обработчик команды 'Текущее расписание'. Возвращает расписание на текущую неделю."""
    df = get_schedule_from_excel()
    today = datetime.now().date()
    week_schedule = df[(df['Дата'] >= today) & (df['Дата'] <= today + timedelta(days=7))]
    
    if week_schedule.empty:
        bot.send_message(message.chat.id, "На ближайшую неделю расписание не найдено.")
        return
        
    # Форматируем каждую строку расписания
    schedule_lines = []
    for _, row in week_schedule.iterrows():
        # Преобразуем дату в формат "ДД.ММ"
        date_str = row['Дата'].strftime('%d.%m')
        schedule_lines.append(f"{date_str}: 👤 {row['Дежурный']}")
    
    schedule_text = "\n".join(schedule_lines)
    bot.send_message(
        message.chat.id,
        f"📋 *Расписание дежурств на неделю:*\n\n{schedule_text}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "Текущие дежурные")
def current_duty(message):
    """Обработчик команды 'Текущие дежурные'. Возвращает текущего дежурного."""
    responsible_person = get_responsible_person()
    bot.send_message(message.chat.id, f"Текущий дежурный: {responsible_person}")

@bot.message_handler(commands=['users'])
@require_operator
def list_users_command(message):
    """Показывает список зарегистрированных пользователей."""
    show_users_list(message)

@bot.message_handler(func=lambda message: message.text == "Список пользователей")
@require_operator
def list_users_button(message):
    """Обработчик кнопки 'Список пользователей'."""
    show_users_list(message)

def show_users_list(message):
    """Показывает список зарегистрированных пользователей."""
    try:
        conn = get_db_connection()
        if conn is None:
            bot.send_message(message.chat.id, "Ошибка подключения к базе данных.")
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT first_name, last_name, username, user_id, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        conn.close()

        if not users:
            bot.send_message(message.chat.id, "Пока нет зарегистрированных пользователей.")
            return

        # Формируем сообщение со списком пользователей
        message_text = "📋 *Список зарегистрированных пользователей:*\n\n"
        for user in users:
            first_name, last_name, username, user_id, created_at = user
            message_text += f"👤 *{first_name} {last_name}*\n"
            if username:
                message_text += f"└ Username: @{username}\n"
            message_text += f"└ ID: `{user_id}`\n"
            message_text += f"└ Зарегистрирован: {created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        # Отправляем сообщение
        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")

    except Exception as e:
        print(f"Ошибка при получении списка пользователей: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении списка пользователей.")

# Функция для отправки алерта в Telegram
def send_alert_to_telegram(alert_data):
    """Отправляет алерт в Telegram дежурному."""
    try:
        # Получаем текущего дежурного
        responsible_person = get_responsible_person()
        
        # Формируем сообщение
        message = f"🚨 *Alert*\n\n"
        message += f"*Status:* {alert_data.get('status', 'unknown')}\n"
        message += f"*Alert:* {alert_data.get('labels', {}).get('alertname', 'Unknown')}\n"
        message += f"*Description:* {alert_data.get('annotations', {}).get('description', 'No description')}\n"
        
        # Подключаемся к базе данных для поиска user_id дежурного
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Ищем пользователя по имени и фамилии
            full_name_parts = responsible_person.split()
            if len(full_name_parts) == 2:
                first_name, last_name = full_name_parts
                cursor.execute(
                    """
                    SELECT user_id FROM users 
                    WHERE first_name = %s AND last_name = %s
                    """,
                    (first_name, last_name)
                )
                result = cursor.fetchone()
                if result:
                    duty_user_id = result[0]
                    try:
                        # Отправляем сообщение дежурному
                        bot.send_message(
                            duty_user_id,
                            message,
                            parse_mode="Markdown"
                        )
                        print(f"Alert sent to duty person {responsible_person} (ID: {duty_user_id})")
                    except Exception as e:
                        print(f"Error sending alert to duty person: {e}")
                        # Если не удалось отправить дежурному, отправляем всем операторам
                        for user_id in AUTHORIZED_OPERATORS:
                            try:
                                bot.send_message(
                                    user_id,
                                    f"❗️ Не удалось отправить алерт дежурному ({responsible_person}). "
                                    f"Пожалуйста, свяжитесь с ним.\n\n{message}",
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                print(f"Error sending alert to operator {user_id}: {e}")
                else:
                    print(f"Duty person {responsible_person} not found in database")
                    # Если дежурный не найден в базе, отправляем всем операторам
                    for user_id in AUTHORIZED_OPERATORS:
                        try:
                            bot.send_message(
                                user_id,
                                f"❗️ Дежурный ({responsible_person}) не найден в базе данных.\n\n{message}",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            print(f"Error sending alert to operator {user_id}: {e}")
            conn.close()
    except Exception as e:
        print(f"Error in send_alert_to_telegram: {e}")

# Маршрут для получения webhook'ов от Prometheus
@app.route('/alert', methods=['POST'])
def alert():
    """Обрабатывает webhook'и от Prometheus."""
    try:
        if request.method == 'POST':
            data = request.get_json()
            print(f"Received alert: {json.dumps(data, indent=2)}")
            
            # Обрабатываем каждый алерт
            for alert in data.get('alerts', []):
                send_alert_to_telegram(alert)
            
            return "OK", 200
    except Exception as e:
        print(f"Error processing alert: {e}")
        return "Error", 500

# Функция для запуска веб-сервера
def run_webhook_server():
    """Запускает веб-сервер для обработки webhook'ов."""
    app.run(host='0.0.0.0', port=5000)

# Функция для получения IP-адреса
def get_server_ip():
    try:
        # Получаем имя хоста
        hostname = socket.gethostname()
        # Получаем IP-адрес
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except Exception as e:
        print(f"Ошибка при получении IP-адреса: {e}")
        return "Не удалось определить IP-адрес"

# Модифицируем основной блок запуска
if __name__ == '__main__':
    start_metrics_server()  # Запускаем сервер метрик
    
    # Показываем IP-адрес сервера
    server_ip = get_server_ip()
    print(f"\n=== Информация о сервере ===")
    print(f"IP-адрес сервера: {server_ip}")
    print(f"Порт для webhook'ов: 5000")
    print(f"URL для настройки Alertmanager: http://{server_ip}:5000/alert")
    print("===========================\n")
    
    # Запускаем веб-сервер для webhook'ов в отдельном потоке
    webhook_thread = threading.Thread(target=run_webhook_server)
    webhook_thread.daemon = True
    webhook_thread.start()
    
    # Запускаем поток проверки открытых задач
    tasks_check_thread = threading.Thread(target=check_open_tasks)
    tasks_check_thread.daemon = True
    tasks_check_thread.start()
    
    print("Бот запущен...")
    bot.polling(none_stop=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_task_"))
def view_task_details(call):
    """Показывает детали задачи."""
    try:
        task_id = int(call.data.split('_')[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, description, priority, status, assigned_user_id
            FROM problems 
            WHERE id = %s
            """,
            (task_id,)
        )
        task = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if task:
            task_id, description, priority, status, assigned_user_id = task
            
            # Формируем статус задачи
            status_text = {
                'open': '🟢 Открыта',
                'in_progress': '🔵 В работе',
                'closed': '⚫️ Закрыта'
            }.get(status, status)
            
            markup = types.InlineKeyboardMarkup()
            if status == 'open':
                take_task = types.InlineKeyboardButton(
                    "✅ Взять в работу",
                    callback_data=f"select_problem_{task_id}"
                )
                markup.add(take_task)
            
            back = types.InlineKeyboardButton(
                "◀️ Назад",
                callback_data="back_to_work_menu"
            )
            markup.add(back)
            
            message_text = (
                f"📋 Задача #{task_id}\n\n"
                f"📝 Описание: {description}\n"
                f"🎯 Приоритет: {priority}\n"
                f"📊 Статус: {status_text}"
            )
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=message_text,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "❌ Задача не найдена", show_alert=True)
            
    except Exception as e:
        print(f"Ошибка при показе деталей задачи: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка", show_alert=True)

@bot.message_handler(commands=['new_task'])
@require_operator
def new_task_command(message):
    """Обработчик команды создания новой задачи."""
    bot.send_message(message.chat.id, "Эта функция больше не поддерживается.")

@bot.message_handler(func=lambda message: message.text == "Создать задачу")
@require_operator
def new_task_button(message):
    """Обработчик кнопки создания новой задачи."""
    bot.send_message(message.chat.id, "Эта функция больше не поддерживается.")
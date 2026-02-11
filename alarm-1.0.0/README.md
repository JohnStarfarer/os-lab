
# Telegram Бот для Мониторинга Задач 🤖

## Что умеет бот? 🎯

1.**Основные функции:**

- Показывает список открытых задач
- Позволяет брать задачи в работу
- Отслеживает кто сейчас дежурный
- Отправляет уведомления о новых проблемах
- Ведёт расписание дежурств

2.**Команды бота:**

   -`/start` - запускает бота и показывает главное меню

   -`/register` - регистрация нового пользователя

   -`/addshift` - добавить смену в расписание (только для админов)

   -`/users` - показать список пользователей (только для админов)

3.**Кнопки в меню:**

- "Работа" - управление задачами
- "Текущее расписание" - показывает кто когда дежурит
- "Текущие дежурные" - кто сейчас на смене
- "Информация о боте" - справка по боту
- "Регистрация" - зарегистрироваться в системе

## Как запустить бота 🚀

1. Установите и запустите Docker 🐳

2. Клонируйте репозиторий проекта

3. Измените переменные окружения в `Bot.env`:

    ```
    BOT_TOKEN=ваш_токен_от_бота
    DB_NAME=имя_базы_данных
    DB_USER=пользователь_базы
    DB_PASSWORD=пароль_от_базы
    DB_HOST=хост_базы
    DB_PORT=порт_базы

    POSTGRES_DB=имя_базы_данных
    POSTGRES_USER=пользователь_базы
    POSTGRES_PASSWORD=пароль_от_базы
    ```


4. Перейдите в директорию с проектом через терминал

5. Создайте и запустите образ:

    ```
    docker-compose build

    docker-compose up -d
    ```

6. Бот запущен в контейнере

Для завершения работы контейнера (бота):

```
docker-compose down
```

Для удаления образа:

```
docker-compose down -v
```

## База данных 📊

Бот использует PostgreSQL. В базе есть такие таблицы:

-`users` - пользователи бота

-`problems` - задачи и проблемы

-`schedule` - расписание дежурств

## Как это работает 🛠

1.**Мониторинг задач:**

- Бот постоянно проверяет открытые задачи
- Если задача висит без обработки, бот пингует дежурного
- Можно взять задачу в работу или отложить её

2.**Дежурства:**

- Расписание хранится в файле `schedule.csv`
- Бот знает, кто сейчас дежурный
- Уведомления о проблемах идут текущему дежурному

3.**Метрики:**

- Бот собирает всякую статистику через Prometheus
- Метрики доступны на порту 8000
- Алерты приходят через webhook на порт 5000

### Основные функции и их описание:

#### Работа с задачами:

```python

defget_open_problems():

    """Получает список открытых задач из базы данных.

    Возвращает: список кортежей (id, description, priority)

    """


defassign_problem_to_user(problem_id, user_id):

    """Назначает задачу пользователю.

    Args:

        problem_id (int): ID задачи

        user_id (int): Telegram ID пользователя

    Returns:

        bool: True если успешно, False если ошибка

    """


defget_user_current_problem(user_id):

    """Получает текущую задачу пользователя.

    Args:

        user_id (int): Telegram ID пользователя

    Returns:

        tuple: (id, description, priority) или None

    """

```

#### Управление дежурствами:

```python

defget_duty_person_id():

    """Получает Telegram ID текущего дежурного.

    Returns:

        int: Telegram ID или None

    """


defget_responsible_person():

    """Определяет ответственного сотрудника из расписания.

    Returns:

        str: Имя и фамилия дежурного

    """


defget_schedule_from_excel():

    """Читает расписание из CSV файла.

    Returns:

        DataFrame: Таблица с расписанием

    """

```

#### Система уведомлений:

```python

defnotify_duty_person(task_id, description, priority):

    """Отправляет уведомление дежурному.

    Args:

        task_id (int): ID задачи

        description (str): Описание задачи

        priority (str): Приоритет

    Returns:

        bool: True если отправлено, False если ошибка

    """


defsend_alert_to_telegram(alert_data):

    """Отправляет алерт от Prometheus в Telegram.

    Args:

        alert_data (dict): Данные алерта

    """

```

#### Безопасность:

```python

defis_authorized(user_id):

    """Проверяет, является ли пользователь админом.

    Args:

        user_id (int): Telegram ID пользователя

    Returns:

        bool: True если админ

    """


@require_operator

defsome_admin_function():

    """Декоратор для защиты админских функций"""

```

### Структура базы данных:

#### Таблица users:

```sql

CREATETABLEusers (

    user_id BIGINTPRIMARY KEY,  -- Telegram ID пользователя

    username VARCHAR(255),       -- Username в Telegram

    first_name VARCHAR(255),    -- Имя

    last_name VARCHAR(255),     -- Фамилия

    created_at TIMESTAMP        -- Дата регистрации

);

```

#### Таблица problems:

```sql

CREATETABLEproblems (

    id SERIALPRIMARY KEY,           -- ID задачи

    descriptionTEXT,                -- Описание проблемы

    statusVARCHAR(50),             -- Статус (open/in_progress/closed)

    priority VARCHAR(50),           -- Приоритет

    assigned_user_id BIGINT,        -- ID назначенного пользователя

    assigned_at TIMESTAMP           -- Время назначения

);

```

### Метрики Prometheus:

```python

REQUEST_COUNT = Counter('bot_requests_total', 'Общее количество запросов к боту')

DB_CONNECTION_ERRORS = Counter('db_connection_errors_total', 'Ошибки подключения к БД')

MESSAGE_PROCESSING_TIME = Histogram('message_processing_time_seconds', 'Время обработки')

ACTIVE_USERS = Gauge('bot_active_users', 'Количество активных пользователей')

OPEN_PROBLEMS = Gauge('bot_open_problems', 'Количество открытых инцидентов')

```

**Многопоточность:**

- Бот использует несколько потоков:

  * Основной поток для обработки сообщений
  * Поток для проверки открытых задач
  * Поток для веб-сервера (Flask)
  * Поток для метрик Prometheus

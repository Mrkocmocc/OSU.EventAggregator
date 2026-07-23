# OSU.EventAggregator

Агрегатор мероприятий Оренбургского государственного университета. Собирает информацию о событиях из новостей и дней открытых дверей, предоставляя единый REST API для доступа к данным.

<div align="center"> 
  <img src="assets/screen-1.png" alt="screenshot1" />
  <img src="assets/screen-2.png" alt="screenshot2" />
</div>


## 📋 Оглавление

- [Архитектура](#архитектура)
- [Установка и запуск](#установка-и-запуск)
- [Конфигурация](#конфигурация)
- [API Endpoints](#api-endpoints)
- [Модель данных](#модель-данных)
- [Парсеры](#парсеры)
- [Импорт/Экспорт](#импорэкспорт)
- [Технологии](#технологии)
- [Разработка](#разработка)

---

## 🏗 Архитектура

```

osu/
├── app/
│   ├── api/
│   │   └── routes.py          # REST API эндпоинты
│   ├── parsers/
│   │   ├── news_parser.py     # Парсинг новостей
│   │   └── dod_parser.py      # Парсинг дней открытых дверей
│   ├── templates/
│   │   └── index.html         # Веб-интерфейс
│   ├── **init**.py            # Инициализация Flask приложения
│   ├── config.py              # Конфигурация
│   └── models.py              # SQLAlchemy модели
├── .env                       # Переменные окружения
├── docker-compose.yaml        # Docker Compose конфигурация
├── requirements.txt           # Python зависимости
└── run.py                     # Точка входа

```

### Компоненты

1. **Flask приложение** (`app/__init__.py`) — основной веб-сервер
2. **REST API** (`app/api/routes.py`) — эндпоинты для работы с событиями
3. **Парсеры** (`app/parsers/`) — сбор данных из внешних источников
4. **База данных** — PostgreSQL для хранения событий
5. **Веб-интерфейс** — удобная панель управления

---

## 🚀 Установка и запуск

### Через Docker (рекомендуется)

```bash
# Клонировать репозиторий
git clone <repository-url>
cd osu

# Запустить контейнеры
docker-compose up --build
```

Приложение будет доступно по адресу: `http://localhost:5000`

### Локальный запуск

```
# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt

# Настроить .env файл
cp .env.example .env

# Запустить приложение
python run.py
```

### PostgreSQL локально

Если вы запускаете PostgreSQL отдельно:

```
# Установить PostgreSQL
# Создать базу данных
createdb osu_events

# Применить миграции (если есть)
flask db upgrade
```

---

## ⚙ Конфигурация

### Переменные окружения (`.env`)

| Переменная | Описание | Пример |
|---|---|---|
| `DATABASE_URL` | URL для подключения к PostgreSQL | `postgresql://user:pass@localhost:5432/osu_events` |
| `POSTGRES_USER` | Имя пользователя БД | `test` |
| `POSTGRES_PASSWORD` | Пароль БД | `test` |
| `POSTGRES_DB` | Название базы данных | `osu_events` |
| `SECRET_KEY` | Секретный ключ Flask | `...` |

### Docker конфигурация

В `docker-compose.yaml` настроены:

- **web**: Flask приложение на порту 5000
- **db**: PostgreSQL на порту 5432
- **volumes**: постоянное хранение данных БД

---

## 📡 API Endpoints

### Базовый URL: `/api`

### GET /events

Получение списка событий с пагинацией.

**Параметры запроса:**

| Параметр | Тип | Описание |
|---|---|---|
| `page` | int | Номер страницы (по умолчанию: 1) |
| `per_page` | int | Элементов на странице (макс: 100, по умолчанию: 20) |
| `event_type` | string | Фильтр по типу события |
| `source_name` | string | Фильтр по источнику |
| `is_active` | boolean | Фильтр по активности |
| `from_date` | date | Начальная дата (YYYY-MM-DD) |
| `to_date` | date | Конечная дата (YYYY-MM-DD) |

**Пример ответа:**

```
{
  "items": [...],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8,
  "has_prev": false,
  "has_next": true
}
```

### GET /events/<id>

Получение события по ID.

**Параметры:** `id` — числовой идентификатор события

### GET /events/upcoming

Получение предстоящих активных событий (сортировка по дате).

### GET /stats

Статистика по событиям.

**Пример ответа:**

```
{
  "total_events": 150,
  "sources_count": 2,
  "last_parsed_at": "2026-07-23T12:00:00",
  "active": 45,
  "inactive": 105,
  "upcoming": 12,
  "added_last_7_days": 8,
  "by_source": {
    "Новости ОГУ": 120,
    "Дни открытых дверей ОГУ": 30
  },
  "by_type": {
    "день открытых дверей": 30,
    "семинар": 45,
    "конкурс": 25
  }
}
```

### POST /parse

Запуск парсинга данных.

**Параметры URL:**

| Параметр | Описание |
|---|---|
| `source` | `news` или `dod` (если не указан, оба источника) |
| `month` | Месяц для новостей (1-12) |
| `year` | Год для новостей |

**Примеры:**

```
# Парсинг новостей за июль 2026
POST /api/parse?source=news&month=07&year=2026

# Парсинг дней открытых дверей
POST /api/parse?source=dod

# Парсинг всех источников
POST /api/parse
```

### GET /export

Экспорт событий в JSON.

**Параметры запроса:** такие же, как в `GET /events` (фильтры)

**Ответ:** файл `events_export_YYYYMMDD_HHMMSS.json`

### POST /import

Импорт событий из JSON.

**Тело запроса:** массив объектов Event

**Пример:**

```
[
  {
    "external_id": "news_12345",
    "title": "Название события",
    "description": "Описание",
    "event_date": "2026-07-25T14:00:00",
    "location": "ауд. 123",
    "event_type": "семинар",
    "source_url": "https://...",
    "source_name": "Новости ОГУ",
    "is_active": true
  }
]
```

**Ответ:**

```
{
  "success": true,
  "imported": 10,
  "skipped": 0,
  "created": 8,
  "updated": 2,
  "errors": []
}
```

---

## 📊 Модель данных

### Event

| Поле | Тип | Описание |
|---|---|---|
| `id` | Integer | Уникальный идентификатор |
| `external_id` | String(255) | Внешний ID из источника (уникальный) |
| `title` | String(500) | Название события |
| `description` | Text | Полное описание |
| `event_date` | DateTime | Дата и время события |
| `location` | String(255) | Место проведения |
| `event_type` | String(50) | Тип события |
| `source_url` | String(500) | Ссылка на источник |
| `source_name` | String(100) | Название источника |
| `parsed_at` | DateTime | Дата парсинга |
| `is_active` | Boolean | Актуально ли событие |
| `created_at` | DateTime | Дата создания записи |
| `updated_at` | DateTime | Дата обновления |

---

## 🔍 Парсеры

### NewsParser (`app/parsers/news_parser.py`)

Парсит новости с сайта ОГУ: `https://www.osu.ru/doc/135/type/2`

**Особенности:**

- Извлекает события из новостных блоков
- Парсит дату и время из текста новости
- Обрабатывает таблицы и списки в описании
- Определяет тип события по ключевым словам

**Методы:**

- `parse(month=None, year=None)` — парсинг новостей за месяц
- `_extract_events(soup)` — извлечение событий из HTML
- `_get_full_description(url)` — получение полного текста новости

### DodParser (`app/parsers/dod_parser.py`)

Парсит дни открытых дверей: `http://abiturient.osu.ru/step1/dod`

**Особенности:**

- Обрабатывает HTML таблицу с датами
- Поддерживает объединенные ячейки (`rowspan`)
- Извлекает время и место проведения
- Автоматически определяет тип мероприятия

---

## 💾 Импорт/Экспорт

### Экспорт данных

```
# Экспорт всех событий
curl http://localhost:5000/api/export -o events.json

# Экспорт с фильтрами
curl "http://localhost:5000/api/export?source_name=Новости%20ОГУ&is_active=true" -o news_events.json
```

### Импорт данных

```
curl -X POST http://localhost:5000/api/import \
  -H "Content-Type: application/json" \
  -d @events.json
```

---

## 🛠 Технологии

| Компонент | Технология |
|---|---|
| Backend | Flask 2.x |
| ORM | SQLAlchemy |
| База данных | PostgreSQL 15 |
| Миграции | Flask-Migrate |
| Парсинг | BeautifulSoup4, Requests |
| Контейнеризация | Docker, Docker Compose |
| Frontend | Bootstrap 5, Vanilla JS |

---

## 👨‍💻 Разработка

### Добавление нового парсера

1. Создать класс в `app/parsers/`
2. Реализовать метод `parse()` → возвращает список событий
3. Реализовать метод `save_events(events)`
4. Зарегистрировать в `routes.py` в эндпоинте `/parse`

### Структура события

```
{
  'external_id': 'unique_id',  # Обязательно! Уникальный ключ
  'title': 'Название',          # Обязательно!
  'description': 'Описание',
  'event_date': datetime(2026, 7, 25, 14, 0),
  'location': 'Место проведения',
  'event_type': 'Тип события',
  'source_url': 'Ссылка',
  'source_name': 'Название источника',
  'is_active': True  # или False
}
```

### Тестирование

```
# Запуск тестов (если есть)
pytest

# Тестирование API через curl
curl http://localhost:5000/api/stats
```

---

## 🤝 Контрибьюция

1. Форкните репозиторий
2. Создайте ветку для фичи (`git checkout -b feature/amazing`)
3. Сделайте коммит (`git commit -m 'Add some amazing feature'`)
4. Запушьте ветку (`git push origin feature/amazing`)
5. Откройте Pull Request


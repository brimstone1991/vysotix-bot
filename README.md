# Vysotix Bot — деплой на Railway

## Что внутри
- Регистрация героя с именем и классом (Воин / Лучник / Маг / Разбойник)
- 5 атрибутов: Сила, Интеллект, Здоровье, Ловкость, Воля
- Задания с тегом атрибута — каждое задание прокачивает нужную характеристику
- Система уровней и снаряжения
- Семейный отряд — создать и пригласить по ссылке
- Ежедневный стрик

## Деплой (15 минут, без кода)

### Шаг 1 — GitHub
1. Зайди на github.com, создай аккаунт если нет
2. Нажми "+" → "New repository"
3. Название: `vysotix-bot`, Public, нажми "Create repository"
4. Нажми "uploading an existing file"
5. Перетащи все файлы из папки (bot.py, requirements.txt, Procfile)
6. Нажми "Commit changes"

### Шаг 2 — Railway
1. Зайди на railway.app
2. "Start a New Project" → "Deploy from GitHub repo"
3. Подключи GitHub и выбери `vysotix-bot`
4. Railway автоматически определит что это Python-проект

### Шаг 3 — Переменная окружения
1. В Railway открой проект → вкладка "Variables"
2. Нажми "New Variable"
3. Имя: `BOT_TOKEN`
4. Значение: вставь токен от BotFather
5. Нажми "Add"

### Шаг 4 — Запуск
1. Перейди на вкладку "Deployments"
2. Нажми "Deploy" — Railway запустит бота
3. Зайди в Telegram, найди @vysotix_bot и напиши /start

## Команды бота
- `/start` — регистрация нового героя
- `/menu` — главное меню

## Структура данных
Все данные хранятся в `data/users.json` на сервере Railway.

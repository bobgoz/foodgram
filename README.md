Foodgram - продуктовый помощник
Описание приложения
Foodgram - это веб-приложение "Продуктовый помощник", которое позволяет:

Публиковать рецепты

Подписываться на авторов

Добавлять рецепты в избранное

Создавать списки покупок

Скачивать сводный список продуктов

Приложение предоставляет API для взаимодействия с базой рецептов и пользователями.

Необходимые инструменты
Для запуска проекта локально вам понадобится:

Docker (версия 20.10.0 или выше)

Docker Compose (версия 1.29.0 или выше)

Python 3.9 (если требуется разработка вне контейнеров)

Инструкция по установке и запуску
Клонируйте репозиторий:

bash
git clone https://github.com/bobgoz/foodgram-project-react.git
cd foodgram-project-react
Создайте файл .env в директории infra/ с необходимыми переменными окружения (образец в .env.example)

Запустите приложение в контейнерах:

bash
cd infra/
docker-compose up -d
После запуска выполните миграции:

bash
docker-compose exec backend python manage.py migrate
Создайте суперпользователя (опционально):

bash
docker-compose exec backend python manage.py createsuperuser
Соберите статические файлы:

bash
docker-compose exec backend python manage.py collectstatic --no-input
Приложение будет доступно по адресу: http://localhost/

Развернутое приложение
Проект доступен в сети по адресу:
https://foodgram-bobgoz.duckdns.org/

Используемые технологии
Backend
Python 3.9

Django 3.2

Django REST Framework 3.12

PostgreSQL

Gunicorn

Nginx

Frontend
React

JavaScript

HTML/CSS

Инфраструктура
Docker

Docker Compose

CI/CD (GitHub Actions)

Яндекс.Облако (для развернутой версии)

Автор
Проект разработан bobgoz
GitHub: bobgoz
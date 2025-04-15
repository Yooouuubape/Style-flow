# Руководство по развертыванию микросервисов в Railway

## Шаг 1: Создание аккаунта в Railway
1. Зарегистрируйтесь на [Railway.app](https://railway.app)
2. Подключите свой GitHub аккаунт

## Шаг 2: Подготовка инфраструктуры

### Создание общей инфраструктуры
1. В Railway создайте новый проект "shared-infrastructure"
2. Добавьте PostgreSQL: **New** → **Database** → **PostgreSQL**
3. Добавьте Redis (опционально): **New** → **Database** → **Redis**
4. Запишите параметры подключения к базе данных

### Настройка переменных окружения для общей инфраструктуры
- В разделе **Variables** для проекта "shared-infrastructure" создайте следующие переменные:
  - `POSTGRES_USER`: ваш_пользователь
  - `POSTGRES_PASSWORD`: ваш_пароль
  - `POSTGRES_DB`: ваша_база_данных

## Шаг 3: Развертывание микросервисов
Для каждого микросервиса выполните следующие действия:

### 1. Admin Dashboard
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "admin-dashboard"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 5000

### 2. Auth Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "auth-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8000
   - `JWT_SECRET`: ваш_jwt_секрет

### 3. User Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "user-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8001

### 4. Gateway Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "gateway-service"
4. Настройте переменные окружения:
   - `PORT`: 8000
   - `AUTH_SERVICE_URL`: https://auth-service-****.railway.app
   - `USER_SERVICE_URL`: https://user-service-****.railway.app
   - `EVENT_SERVICE_URL`: https://event-service-****.railway.app
   - `RESOURCE_SERVICE_URL`: https://resource-service-****.railway.app
   - `CLIENT_SERVICE_URL`: https://client-service-****.railway.app
   - `PAYMENT_SERVICE_URL`: https://payment-service-****.railway.app

### 5. Event Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "event-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8002

### 6. Resource Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "resource-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8003

### 7. Client Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "client-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8004

### 8. Payment Service
1. Создайте новый проект в Railway: **New** → **GitHub Repo**
2. Выберите репозиторий и ветку
3. В настройках проекта (**Settings**) установите корневую директорию "payment-service"
4. Настройте переменные окружения:
   - `DATABASE_URL`: postgresql://postgres:password@containers-us-west-****.railway.app:7049/railway
   - `SECRET_KEY`: ваш_секретный_ключ
   - `PORT`: 8005
   - `STRIPE_API_KEY`: ваш_ключ_stripe (если используется)

## Шаг 4: Инициализация базы данных
1. Подключитесь к базе данных PostgreSQL через Railway CLI или веб-интерфейс
2. Выполните SQL скрипты из директории `init-scripts` для создания всех необходимых таблиц и индексов

## Шаг 5: Настройка сетевой маршрутизации
Railway автоматически предоставляет публичные URL для каждого проекта. Используйте эти URL в переменных окружения для связи между сервисами.

## Шаг 6: Мониторинг и логирование
1. Просматривайте логи каждого сервиса в разделе **Deployments** → **View Logs**
2. Настройте оповещения о сбоях в разделе **Settings** → **Notifications**

## Шаг 7: Обновление микросервисов
1. Просто внесите изменения в GitHub репозиторий
2. Railway автоматически обнаружит изменения и выполнит новое развертывание

## Важные примечания
- Убедитесь, что в каждом сервисе установлен Gunicorn для продакшн-деплоя
- Все микросервисы должны обрабатывать переменную окружения PORT для правильного прослушивания входящих соединений
- Если возникает ошибка "Healthcheck failure", проверьте, что у вас есть маршрут, указанный в healthcheckPath (по умолчанию "/")
- Для добавления эндпоинта health check добавьте в app.py каждого сервиса:
```python
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "service": "название-сервиса"}), 200
```
- Для использования Railway CLI установите его с помощью `npm i -g @railway/cli`
- Для подключения к проекту через CLI выполните `railway login` и `railway link` 
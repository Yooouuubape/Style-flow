FROM python:3.9-slim

# Install build dependencies for confluent-kafka
RUN apt-get update && apt-get install -y gcc librdkafka-dev

WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы приложения
COPY . .

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Открываем порт
EXPOSE 5000

# Запускаем приложение
CMD ["python", "app.py"] 
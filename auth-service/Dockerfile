FROM python:3.10-slim

WORKDIR /app

# Установка необходимых зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов требований
COPY requirements.txt /app/

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего проекта
COPY . /app/

# Указание переменных окружения
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Порт, на котором будет работать приложение
EXPOSE 8000

# Запуск приложения
CMD ["python", "-m", "gunicorn", "app:app", "--bind", "0.0.0.0:8000"] 
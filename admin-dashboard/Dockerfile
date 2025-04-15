FROM python:3.9-slim

WORKDIR /app

# Install PostgreSQL client libraries
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Создаем инициализационный скрипт
RUN echo '#!/usr/bin/env python3\nimport time\nfrom app import init_db\n\ntime.sleep(5)  # Wait for DB\ninit_db()\n' > /app/init_db.py

CMD ["sh", "-c", "python /app/init_db.py && gunicorn -b 0.0.0.0:5000 app:app"] 
FROM python:3.9-slim

# Install build dependencies for confluent-kafka
RUN apt-get update && apt-get install -y gcc librdkafka-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5004

CMD ["python", "app.py"] 
FROM python:3.9-slim

# Install build dependencies for confluent-kafka
RUN apt-get update && apt-get install -y gcc librdkafka-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

CMD ["python", "app.py"] 
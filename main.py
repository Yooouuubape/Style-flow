#!/usr/bin/env python
import os
import sys

# Добавляем путь к директории admin-dashboard
sys.path.append(os.path.join(os.path.dirname(__file__), 'admin-dashboard'))

# Импортируем приложение из admin-dashboard
try:
    from app import app
except ImportError:
    print("Не удалось импортировать приложение из admin-dashboard")
    sys.exit(1)

# Запускаем приложение, если скрипт запущен напрямую
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port) 
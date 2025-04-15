import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime
from dotenv import load_dotenv
import json

# Загрузка переменных окружения
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://salyukovgleb033:v0AOP4yzg5rZVVUl@db:5432/user_service')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = False  # Allow non-HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Модели
class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    api_keys = db.relationship('ApiKey', backref='admin', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    allowed_services = db.Column(db.Text, nullable=False, default='[]')  # JSON строка с перечнем разрешенных сервисов

    def get_allowed_services(self):
        return json.loads(self.allowed_services)
    
    def set_allowed_services(self, services_list):
        self.allowed_services = json.dumps(services_list)

# Функция для загрузки пользователя
@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

# Роуты для аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('dashboard'))
        
        flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Основные роуты
@app.route('/')
@login_required
def dashboard():
    api_keys = ApiKey.query.filter_by(admin_id=current_user.id).all()
    services_list = Service.query.all()
    databases_list = Database.query.all()
    
    # Подсчет активных сервисов
    active_services = [s for s in services_list if s.active]
    
    # Список доступных микросервисов
    available_services = [
        {'id': 'auth_service', 'name': 'Auth Service'},
        {'id': 'user_service', 'name': 'User Service'},
        {'id': 'event_service', 'name': 'Event Service'},
        {'id': 'resource_service', 'name': 'Resource Service'},
        {'id': 'client_service', 'name': 'Client Service'},
        {'id': 'payment_service', 'name': 'Payment Service'}
    ]
    
    return render_template('dashboard.html', 
                          api_keys=api_keys, 
                          available_services=available_services,
                          services=active_services,
                          databases=databases_list)

@app.route('/api-keys', methods=['GET', 'POST'])
@login_required
def api_keys():
    if request.method == 'POST':
        name = request.form.get('name')
        services = request.form.getlist('services')
        
        if not name:
            flash('Имя для ключа обязательно', 'danger')
            return redirect(url_for('api_keys'))
            
        # Генерация API ключа
        api_key = ApiKey(
            key=str(uuid.uuid4()),
            name=name,
            admin_id=current_user.id
        )
        api_key.set_allowed_services(services)
        
        db.session.add(api_key)
        db.session.commit()
        
        flash(f'API ключ {name} успешно создан', 'success')
        return redirect(url_for('api_keys'))
    
    api_keys = ApiKey.query.filter_by(admin_id=current_user.id).all()
    
    # Список доступных микросервисов
    available_services = [
        {'id': 'auth_service', 'name': 'Auth Service'},
        {'id': 'user_service', 'name': 'User Service'},
        {'id': 'event_service', 'name': 'Event Service'},
        {'id': 'resource_service', 'name': 'Resource Service'},
        {'id': 'client_service', 'name': 'Client Service'},
        {'id': 'payment_service', 'name': 'Payment Service'}
    ]
    
    return render_template('api_keys.html', 
                          api_keys=api_keys, 
                          available_services=available_services)

@app.route('/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
def delete_api_key(key_id):
    api_key = ApiKey.query.filter_by(id=key_id, admin_id=current_user.id).first_or_404()
    
    db.session.delete(api_key)
    db.session.commit()
    
    flash(f'API ключ {api_key.name} успешно удален', 'success')
    return redirect(url_for('api_keys'))

@app.route('/api-keys/<int:key_id>/toggle', methods=['POST'])
@login_required
def toggle_api_key(key_id):
    api_key = ApiKey.query.filter_by(id=key_id, admin_id=current_user.id).first_or_404()
    
    api_key.is_active = not api_key.is_active
    db.session.commit()
    
    status = 'активирован' if api_key.is_active else 'деактивирован'
    flash(f'API ключ {api_key.name} {status}', 'success')
    return redirect(url_for('api_keys'))

# Маршруты для просмотра данных из баз данных
@app.route('/tables')
@login_required
def tables():
    service = request.args.get('service', 'user_service')
    
    # Список доступных микросервисов
    available_services = [
        {'id': 'auth_service', 'name': 'Auth Service'},
        {'id': 'user_service', 'name': 'User Service'},
        {'id': 'event_service', 'name': 'Event Service'},
        {'id': 'resource_service', 'name': 'Resource Service'},
        {'id': 'client_service', 'name': 'Client Service'},
        {'id': 'payment_service', 'name': 'Payment Service'}
    ]
    
    # Здесь должна быть логика для получения списка таблиц из выбранной базы данных
    # В простом случае можно использовать SQL запрос к информационной схеме
    with db.engine.connect() as conn:
        tables_result = conn.execute(db.text("""
            SELECT tablename FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
        """))
    
        tables = [table[0] for table in tables_result]
    
    return render_template('tables.html', 
                          service=service, 
                          tables=tables, 
                          available_services=available_services)

@app.route('/table-data')
@login_required
def table_data():
    service = request.args.get('service', 'user_service')
    table_name = request.args.get('table')
    
    if not table_name:
        flash('Выберите таблицу', 'danger')
        return redirect(url_for('tables', service=service))
    
    # Здесь нужно подключиться к правильной базе данных в зависимости от сервиса
    # В простом случае можно использовать SQL запрос для получения данных
    try:
        # Получаем информацию о колонках
        with db.engine.connect() as conn:
            columns_result = conn.execute(db.text(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
            """))
            
            columns = [{'name': col[0], 'type': col[1]} for col in columns_result]
            
            # Получаем данные из таблицы (ограничиваем 100 строками)
            data_result = conn.execute(db.text(f"SELECT * FROM {table_name} LIMIT 100"))
            
            rows = [dict(row._mapping) for row in data_result]
        
        return render_template('table_data.html', 
                            service=service,
                            table_name=table_name,
                            columns=columns,
                            rows=rows)
    except Exception as e:
        flash(f'Ошибка при получении данных: {str(e)}', 'danger')
        return redirect(url_for('tables', service=service))

# Создание первого администратора
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    # Проверка, существуют ли уже админы
    if Admin.query.count() > 0:
        flash('Настройка уже выполнена', 'info')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        if not username or not password or not email:
            flash('Все поля обязательны', 'danger')
            return render_template('setup.html')
        
        admin = Admin(
            username=username,
            email=email
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        flash('Администратор успешно создан, теперь вы можете войти', 'success')
        return redirect(url_for('login'))
    
    return render_template('setup.html')

# Added models for Services and Databases
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(20), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)
    database = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Database(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='online')
    schema_count = db.Column(db.Integer, default=0)
    size = db.Column(db.String(20), default='0 MB')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Routes for services management
@app.route('/services', methods=['GET'])
@login_required
def services():
    services_list = Service.query.all()
    databases_list = Database.query.all()
    
    return render_template('services.html', 
                          services=services_list,
                          databases=databases_list)

@app.route('/services/add', methods=['POST'])
@login_required
def add_service():
    name = request.form.get('name')
    version = request.form.get('version')
    url = request.form.get('url')
    port = request.form.get('port')
    database = request.form.get('database')
    
    service = Service(
        name=name,
        version=version,
        url=url,
        port=port,
        database=database
    )
    
    db.session.add(service)
    db.session.commit()
    
    flash(f'Микросервис {name} успешно добавлен', 'success')
    return redirect(url_for('services'))

@app.route('/services/<int:service_id>/toggle-status', methods=['POST'])
@login_required
def toggle_service_status(service_id):
    service = Service.query.get_or_404(service_id)
    
    service.active = not service.active
    db.session.commit()
    
    status = 'запущен' if service.active else 'остановлен'
    return jsonify({'success': True, 'message': f'Сервис {service.name} {status}'})

@app.route('/services/<int:service_id>/delete', methods=['DELETE'])
@login_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    db.session.delete(service)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Сервис {service.name} удален'})

# Routes for databases management
@app.route('/databases', methods=['GET'])
@login_required
def databases():
    databases_list = Database.query.all()
    
    return render_template('databases.html', 
                          databases=databases_list)

@app.route('/databases/add', methods=['POST'])
@login_required
def add_database():
    name = request.form.get('name')
    db_type = request.form.get('type')
    host = request.form.get('host')
    port = request.form.get('port')
    username = request.form.get('username')
    password = request.form.get('password')
    
    database = Database(
        name=name,
        type=db_type,
        host=host,
        port=port,
        username=username,
        password=password
    )
    
    db.session.add(database)
    db.session.commit()
    
    flash(f'База данных {name} успешно добавлена', 'success')
    return redirect(url_for('databases'))

@app.route('/databases/<int:db_id>/edit', methods=['POST'])
@login_required
def edit_database(db_id):
    database = Database.query.get_or_404(db_id)
    
    database.name = request.form.get('name')
    database.type = request.form.get('type')
    database.host = request.form.get('host')
    database.port = request.form.get('port')
    database.username = request.form.get('username')
    
    # Only update password if provided
    new_password = request.form.get('password')
    if new_password:
        database.password = new_password
    
    db.session.commit()
    
    flash(f'База данных {database.name} обновлена', 'success')
    return redirect(url_for('databases'))

@app.route('/databases/<int:db_id>/toggle-status', methods=['POST'])
@login_required
def toggle_database_status(db_id):
    database = Database.query.get_or_404(db_id)
    
    database.status = 'offline' if database.status == 'online' else 'online'
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Статус базы данных {database.name} изменен на {database.status}'})

@app.route('/databases/<int:db_id>/delete', methods=['DELETE'])
@login_required
def delete_database(db_id):
    database = Database.query.get_or_404(db_id)
    
    db.session.delete(database)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'База данных {database.name} удалена'})

@app.route('/databases/<int:db_id>', methods=['GET'])
@login_required
def database_details(db_id):
    database = Database.query.get_or_404(db_id)
    
    # Получаем сервисы, которые используют эту базу данных
    database.services = Service.query.filter_by(database=database.name).all()
    
    # Here you would connect to the database and get schema information
    # This is just a placeholder
    schemas = [
        {'name': 'public', 'table_count': 5, 'size': '2.3 MB'},
        {'name': 'auth', 'table_count': 3, 'size': '1.1 MB'}
    ]
    
    return render_template('database_details.html', 
                          database=database,
                          schemas=schemas)

# Инициализация базы данных
def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created.")
        
        # Добавление начальных данных о микросервисах, если их нет
        if Service.query.count() == 0:
            services = [
                Service(name="Auth Service", version="1.0", url="http://auth", port=8000, database="auth_service", active=True),
                Service(name="User Service", version="1.0", url="http://user", port=8000, database="user_service", active=True),
                Service(name="Event Service", version="1.0", url="http://event", port=8000, database="event_service", active=True),
                Service(name="Resource Service", version="1.0", url="http://resource", port=8000, database="resource_service", active=True),
                Service(name="Client Service", version="1.0", url="http://client", port=8000, database="client_service", active=True),
                Service(name="Payment Service", version="1.0", url="http://payment", port=8000, database="payment_service", active=True)
            ]
            db.session.add_all(services)
            db.session.commit()
            print("Initial microservices added.")
        
        # Добавление начальных данных о базах данных, если их нет
        if Database.query.count() == 0:
            databases = [
                Database(name="auth_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=1, size="10 MB"),
                Database(name="user_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=4, size="25 MB"),
                Database(name="event_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=2, size="15 MB"),
                Database(name="resource_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=2, size="12 MB"),
                Database(name="client_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=3, size="18 MB"),
                Database(name="payment_service", type="postgres", host="db", port=5432, username="salyukovgleb033", password="v0AOP4yzg5rZVVUl", status="online", schema_count=2, size="14 MB")
            ]
            db.session.add_all(databases)
            db.session.commit()
            print("Initial databases added.")

# Запуск приложения
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # Для Gunicorn и других WSGI серверов
    init_db() 
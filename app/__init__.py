import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from app.config import Config
from logging.handlers import RotatingFileHandler
import time
import logging

db = SQLAlchemy()
migrate = Migrate()
time.tzset()

def setup_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler(
        'logs/events.log',
        maxBytes=10485760,
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    for logger_name in ['app', 'app.api', 'app.parsers']:
        logger = logging.getLogger(logger_name)
        logger.addHandler(file_handler)
        logger.setLevel(log_level)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    setup_logging(app)
    
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        return {'status': 'ok', 'message': 'OSU.EventAggregator is running'}, 200

    with app.app_context():
        max_retries = 5
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                db.create_all()
                app.logger.info("Database connection successful")
                break
            except Exception as e:
                app.logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    app.logger.error("Max retries reached, could not connect to database")
                    raise
    
    return app
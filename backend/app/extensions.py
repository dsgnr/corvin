from apscheduler.schedulers.background import BackgroundScheduler
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
scheduler = BackgroundScheduler()

from flask import Flask
from flask_socketio import SocketIO
from celery import Celery

app = Flask(__name__)
app.clients = {}
app.config['SECRET_KEY'] = 'hmmm..'

# Celery stuff
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

socketio = SocketIO(app)

from app import routes  # nopep8

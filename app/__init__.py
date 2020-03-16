# import eventlet
from gevent import monkey
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hmmm..'
# async_mode = 'eventlet'
async_mode = 'gevent'
# eventlet.monkey_patch()
monkey.patch_all()


socketio = SocketIO(app, async_mode=async_mode)

from app import routes  # nopep8

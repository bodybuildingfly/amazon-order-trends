from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_apscheduler import APScheduler

cors = CORS(supports_credentials=True)
jwt = JWTManager()
scheduler = APScheduler()

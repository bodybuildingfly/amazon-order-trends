from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

cors = CORS(supports_credentials=True)
jwt = JWTManager()
scheduler = APScheduler()
limiter = Limiter(key_func=get_remote_address)

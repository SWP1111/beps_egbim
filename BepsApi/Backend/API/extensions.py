from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_caching import Cache
import redis

db = SQLAlchemy()   # SQLAlchemy 초기화
jwt = JWTManager()  # JWT 초기화
cache = Cache()     # Cache 초기화
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)  # Redis 초기화

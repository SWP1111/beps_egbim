import os
from flask import Blueprint

api_leaning_bp = Blueprint('leaning', __name__) # 🔹 블루프린트 생성
yaml_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'learning')

from . import leaning_routes
from . import leaning_ranking_routes
from . import leaning_activity_routes

__all__ = ['api_leaning_bp']  # 🔹 모듈에서 사용할 객체를 지정
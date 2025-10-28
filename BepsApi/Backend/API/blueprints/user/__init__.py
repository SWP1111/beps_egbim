import os
from flask import Blueprint

api_user_bp = Blueprint('user', __name__)
yaml_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'user')

from . import user_routes
from . import user_auth_routes
from . import user_roles_routes
from . import user_statistic_routes

__all__ = ['api_user_bp']

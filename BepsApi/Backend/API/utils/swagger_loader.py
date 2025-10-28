# utils/swagger_loader.py
import yaml
import os
from flasgger import swag_from
from config import Config

def get_swag_from(yaml_folder_path, filename):
    yaml_path = os.path.join(yaml_folder_path, filename)
    if Config.ENV == "development":
        return swag_from(yaml_path)
    else:
        def dummy_decorator(f):
            return f
        return dummy_decorator
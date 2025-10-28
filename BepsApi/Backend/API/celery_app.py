from celery import Celery
from config import Config # Config 클래스 임포트
from extensions import db # db 임포트

import sys
print("=== sys.path ===")
for p in sys.path:
    print(p)
    
# Initialize Celery directly with broker and backend from Config
celery_app = Celery(
    'beps_api',
    broker=Config.broker_url,  # Config에서 Redis 브로커 URL 사용
    backend=Config.result_backend # Config에서 Redis 백엔드 URL 사용
)

# Explicitly import the module containing your Celery tasks
celery_app.conf.imports = ('services.statistics_excel_service',)

# This function will be called by the Flask app to configure Celery
def init_app_for_celery(app):
    # Update other Celery configurations from Flask app's config
    # Note: broker and backend are already set above for worker startup
    celery_app.conf.update(app.config)
    db.init_app(app) # CRITICAL: Initialize db for the Celery's Flask app instance

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            # Removed with app.app_context(): as it will be handled in the task itself
            return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
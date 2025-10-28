import logging
import os
from concurrent_log_handler import ConcurrentRotatingFileHandler

# 🔹 로그 폴더 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 크기별 로그 파일 핸들러 (최대 300MB, 10개 파일 보관) -> 멀티프로세스 안전
log_handler = ConcurrentRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "connect.log"),
    maxBytes=300*1024*1024, # 300MB
    backupCount=10,         # 최대 10개 파일 보관
    encoding="utf-8",
)
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    logger.addHandler(log_handler)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    logger.addHandler(logging.StreamHandler())
    
# 🚀 로그 설정 완료
logging.info("🚀**안전한 크기별 로그 (300MB)** 설정 완료.")
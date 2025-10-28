import logging
import os
import time
import glob
import threading
from concurrent_log_handler import ConcurrentRotatingFileHandler

# 🔹 로그 폴더 설정
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 🔹 공통 포매터 설정
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 🔹 기본 앱 로그 핸들러 (기존 app.log 유지)
app_log_handler = ConcurrentRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "app.log"),
    maxBytes=300*1024*1024, # 300MB
    backupCount=10,         # 최대 10개 파일 보관
    encoding="utf-8",
)
app_log_handler.setLevel(logging.DEBUG)
app_log_handler.setFormatter(log_formatter)

# 🔹 콘텐츠 로그 핸들러 (content.log)
content_log_handler = ConcurrentRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "content.log"),
    maxBytes=300*1024*1024, # 300MB
    backupCount=10,         # 최대 10개 파일 보관
    encoding="utf-8",
)
content_log_handler.setLevel(logging.DEBUG)
content_log_handler.setFormatter(log_formatter)

# 🔹 메모 로그 핸들러 (memo.log)
memo_log_handler = ConcurrentRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "memo.log"),
    maxBytes=300*1024*1024, # 300MB
    backupCount=10,         # 최대 10개 파일 보관
    encoding="utf-8",
)
memo_log_handler.setLevel(logging.DEBUG)
memo_log_handler.setFormatter(log_formatter)

# 🔹 기본 루트 로거 설정 (기존 동작 유지)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 기존 핸들러가 없는 경우에만 추가
if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    root_logger.addHandler(app_log_handler)
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(logging.StreamHandler())

# 🔹 콘텐츠 전용 로거 설정
content_logger = logging.getLogger('content')
content_logger.setLevel(logging.DEBUG)
content_logger.propagate = False  # 루트 로거로 전파 방지
content_logger.addHandler(content_log_handler)
content_logger.addHandler(logging.StreamHandler())  # 콘솔 출력도 유지

# 🔹 메모 전용 로거 설정
memo_logger = logging.getLogger('memo')
memo_logger.setLevel(logging.DEBUG)
memo_logger.propagate = False  # 루트 로거로 전파 방지
memo_logger.addHandler(memo_log_handler)
memo_logger.addHandler(logging.StreamHandler())  # 콘솔 출력도 유지

# 🔹 편의 함수들
def get_content_logger():
    """콘텐츠 관련 로깅을 위한 로거 반환"""
    return content_logger

def get_memo_logger():
    """메모 관련 로깅을 위한 로거 반환"""
    return memo_logger

def get_app_logger():
    """일반 앱 로깅을 위한 기본 로거 반환"""
    return root_logger

# 🚀 로그 설정 완료
logging.info("🚀 Gunicorn 멀티프로세스 + **안전한 크기별 로그 (300MB)** 설정 완료.")
logging.info("📁 로그 파일들: app.log, content.log, memo.log")
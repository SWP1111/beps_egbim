import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

class Config:
    # API 서버 설정
    API_BASE_URL = os.getenv("API_BASE_URL", "http://172.16.40.192:20000")  # 🔹 API 서버 기본 URL
    
    # WebSocket 서버 설정
    WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "0.0.0.0")  # 🔹 WebSocket 서버 호스트
    WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", 2002))  # 🔹 WebSocket 서버 포트
    
    # 타임아웃 설정
    CLIENT_TIMEOUT = int(os.getenv("CLIENT_TIMEOUT", 40))  # 🔹 클라이언트 타임아웃 시간 (초)
    PING_INTERVAL = int(os.getenv("PING_INTERVAL", 10))  # 🔹 PING 간격 (초)
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 20))  # 🔹 비활성 클라이언트 확인 간격 (초)
    
    # WebSocket 서버 고급 설정
    MAX_SIZE = int(os.getenv("MAX_SIZE", 2**20))  # 🔹 최대 메시지 크기
    MAX_QUEUE = int(os.getenv("MAX_QUEUE", 32))  # 🔹 최대 큐 크기
    PING_TIMEOUT = int(os.getenv("PING_TIMEOUT", 20))  # 🔹 PING 타임아웃
    BACKLOG = int(os.getenv("BACKLOG", 100))  # 🔹 백로그 크기

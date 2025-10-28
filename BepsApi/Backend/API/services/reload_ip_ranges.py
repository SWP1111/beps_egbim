from app import app
from ip_range_cache import load_ip_ranges, ip_range_list
import logging
import log_config

with app.app_context():
    ip_range_list[:] = load_ip_ranges()  # 캐시 갱신(in-place update)
    logging.info(f"IP Range Cache Reloaded: {len(ip_range_list)} ranges loaded.")
    
    #실행 방법(가상환경 터미널에서) - DB 테이블의 값이 변경되면 실행해서 값 업데이트
    # python reload_ip_ranges.py     


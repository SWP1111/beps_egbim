import os
import uuid
from datetime import datetime
import logging
import re  # 정규식을 사용하기 위해 추가

# 로그 설정
logging.basicConfig(
    filename='process_log.txt',  # 로그 파일 이름
    level=logging.INFO,          # 로그 레벨
    #format='%(asctime)s - %(levelname)s - %(message)s'
    format='%(message)s'
)

# ==== 유틸 함수 ====
def is_media_file(filename):
    return filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.webm'))

def now():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def escape(s):
    return s.replace("'", "''")

def insert_channel(id, name):
    query = (
        f"INSERT INTO content_rel_channels (id, name, description, created_at, updated_at, is_deleted) "
        f"VALUES ({id}, '{escape(name)}', '', '{now()}', '{now()}', false);"
    )
    logging.info(query)
    return query

def insert_folder(id, channel_id, parent_id, name):
    parent = "NULL" if parent_id is None else str(parent_id)
    query = (
        f"INSERT INTO content_rel_folders (id, channel_id, parent_id, name, description, created_at, updated_at, is_deleted) "
        f"VALUES ({id}, {channel_id}, {parent}, '{escape(name)}', '', '{now()}', '{now()}', false);"
    )
    logging.info(query)
    return query

def insert_page(id, folder_id, name, object_id):
    query = (
        f"INSERT INTO content_rel_pages (id, folder_id, name, description, object_id, created_at, updated_at, is_deleted) "
        f"VALUES ({id}, {folder_id}, '{escape(name)}', '', '{object_id}', '{now()}', '{now()}', false);"
    )
    logging.info(query)
    return query

def insert_page_detail(id, page_id, name, object_id):
    query = (
        f"INSERT INTO content_rel_page_details (id, page_id, name, description, object_id, created_at, updated_at, is_deleted) "
        f"VALUES ({id}, {page_id}, '{escape(name)}', '', '{object_id}', '{now()}', '{now()}', false);"
    )
    logging.info(query)
    return query

# variables
channel_id = 1
folder_id  = 1
page_id    = 1
detail_id = 1

# 컨텐츠 여부 체크
def is_valid_file(filename):
    """
    파일 이름이 3자리 숫자로 시작하고 "_" 기호가 있는 경우에만 유효
    """
    return bool(re.match(r"^\d{3}_", filename))

# ==== 폴더 재귀 처리 함수 ====
def process_folder(path, channel):
    global folder_id, page_id, detail_id

    # ── 이 폴더를 folders 테이블에 등록 ──
    current_folder = folder_id
    folder_name = os.path.basename(path)
    if not is_valid_file(folder_name):
        return
    
    print(insert_folder(current_folder, channel, process_folder.parent_id, folder_name))
    folder_id += 1

    entries = sorted(os.listdir(path))

    # 해당 폴더 안에서 만든 페이지 이름 → id 맵
    page_name_to_id_map = {}

    # 1) 파일(페이지) 처리
    for entry in entries:
        full = os.path.join(path, entry)
        if os.path.isfile(full) and is_media_file(entry) and is_valid_file(entry):
            name = os.path.splitext(entry)[0]
            obj_id = ""
            print(insert_page(page_id, current_folder, name, obj_id))
            page_name_to_id_map[name] = page_id
            page_id += 1

    # 2) 하위 폴더 처리 (상세보기 제외)
    for entry in entries:
        full = os.path.join(path, entry)
        if os.path.isdir(full) and entry != "상세보기":
            old_parent = process_folder.parent_id
            process_folder.parent_id = current_folder
            process_folder(full, channel)
            process_folder.parent_id = old_parent

    # 3) "상세보기" 폴더 처리
    detail_folder_path = os.path.join(path, "상세보기")
    if os.path.exists(detail_folder_path) and os.path.isdir(detail_folder_path):
        for folder_name in sorted(os.listdir(detail_folder_path)):
            full_detail_folder = os.path.join(detail_folder_path, folder_name)
            if os.path.isdir(full_detail_folder):
                # page 이름과 일치하는지 확인
                matched_page_id = page_name_to_id_map.get(folder_name)
                if matched_page_id:
                    for fname in sorted(os.listdir(full_detail_folder)):
                        if is_media_file(fname) and is_valid_file(fname):
                            obj_id = ""
                            print(insert_page_detail(detail_id, matched_page_id, fname, obj_id))
                            detail_id += 1

# 초기 부모 아이디
process_folder.parent_id = None

# ==== 채널 루프 ====
def process_contents(root):
    global channel_id
    for ch in sorted(os.listdir(root)):
        ch_path = os.path.join(root, ch)
        if os.path.isdir(ch_path):
            # 채널 등록
            print(insert_channel(channel_id, ch))

            # 채널의 하위 폴더부터 탐색
            process_folder.parent_id = None
            for subfolder in sorted(os.listdir(ch_path)):
                subfolder_path = os.path.join(ch_path, subfolder)
                if os.path.isdir(subfolder_path):
                    process_folder(subfolder_path, channel_id)

            channel_id += 1

# ==== 실행 예 ====
if __name__ == "__main__":
    base_path = r"/mnt/beps_contents"  # 실제 경로로 바꿔주세요
    process_contents(base_path)
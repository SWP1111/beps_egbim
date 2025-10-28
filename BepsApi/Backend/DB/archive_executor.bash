#!/bin/bash

# 매달 1일에 한 번씩 실행해야 함 : cronjob 설정 필요
    # crontab -e
    # 0 0 1 * * /bin/bash ~/BepsApi/DB/content_viewing_history_sql_execute.bash >> ~/BepsApi/DB/backup/log/archive_automation.log 2>&1
# 1,4,7,10월에 sql 스크립트 실행
# 1월 1일에 2년 전 데이터 csv로 백업 및 삭제 -- 주석 처리

# PostgresSQL 데이터베이스 설정
DB_USER="postgres"
DB_NAME="beps"
DB_HOST="127.0.0.1"

# 파일 경로 설정
DATE=$(date +"%Y%m%d")
#DATE=$(date +"%Y")

#CSV 백업할 때 필요한 경로
#BACKUP_DIR="$HOME/service/BepsAip/Backend/DB/backup"
#BACKUP_PATH="$BACKUP_DIR/content_viewing_history_backup_${DATE}.csv" 
#mkdir -p "$BACKUP_DIR/log"

LOG_DIR="$HOME/service/BepsApi/Backend/DB/log"
LOG_PATH="$LOG_DIR/archive_automation.log"

echo "$LOG_PATH"

mkdir -p "$LOG_DIR"
chown "$(whoami)":"$(whoami)" "$LOG_DIR"
chmod u+w "$LOG_DIR"

CURRENT_MONTH=$(date +"%m")
CURRENT_DAY=$(date +"%d")

if [[ "$CURRENT_MONTH" == "01" || "$CURRENT_MONTH" == "04" || "$CURRENT_MONTH" == "07" || "$CURRENT_MONTH" == "10" ]]; then
    echo "$(date +"%Y-%m-%d %H:%M:%S"): Executing SQL script on $(date)" | tee -a "$LOG_PATH"
    # PostgreSQL 스크립트 실행(content_viewing_history_manager.sql) : 아카이브 이동, 파티션 생성, 1년 이전 데이터 삭제
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f content_viewing_history_manager.sql 2>&1 | tee -a "$LOG_PATH"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f login_history_manager.sql 2>&1 | tee -a "$LOG_PATH"
else
    echo "$(date +"%Y-%m-%d %H:%M:%S"): Not executing SQL script on $(date)" | tee -a "$LOG_PATH"
fi

# region 2년 전 파티션 정리: 데이터 쌓이면 성능 떨어질까봐 추가했는데, 아카이브 테이블 파티셔닝하면 안 해도 된다고 해서 주석 처리
# 매년 1월 1일에만 실행
# if [[ "$CURRENT_MONTH" == "01" && "$CURRENT_DAY" == "01" ]]; then
#     YEAR_TO_DELETE=$(date '+%Y' --date='2 years ago')
#     for MONTH in {01..12}; do
#         PARTITION_NAME="content_viewing_history_archive_${YEAR_TO_DELETE}_${MONTH}"
#         BACKUP_PATH="$BACKUP_DIR/${PARTITION_NAME}.csv"

#         echo "[$(date)] 백업 및 삭제 준비: $PARTITION_NAME" | tee -a "$LOG_PATH"

#         # 파티션 존재 여부 확인
#         EXISTS=$(PGPASSFILE=~/.pgpass psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c \
#             "SELECT to_regclass('public.$PARTITION_NAME');" | tr -d '[:space:]' | tr -d '\r')
        
#         echo "[$(date)] DEBUG: EXISTS=[$EXISTS], PARTITION_NAME=[public.$PARTITION_NAME]" | tee -a "$LOG_PATH"


#         if [[ "$EXISTS" != "$PARTITION_NAME" ]]; then
#             echo "[$(date)] 파티션 없음 → 건너뜀: $PARTITION_NAME" | tee -a "$LOG_PATH"
#             continue
#         fi

#         # 백업
#         PGPASSFILE=~/.pgpass psql -h $DB_HOST -U $DB_USER -d $DB_NAME <<EOF
# \copy (SELECT * FROM public.$PARTITION_NAME) TO '$BACKUP_PATH' WITH CSV HEADER;
# EOF

#         # 백업 확인 후 삭제
#         if [ -s "$BACKUP_PATH" ]; then
#             echo "[$(date)] 삭제 시작: $PARTITION_NAME" | tee -a "$LOG_PATH"
#             PGPASSFILE=~/.pgpass psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \
#                 "DROP TABLE IF EXISTS public.$PARTITION_NAME;"
#             echo "[$(date)] 삭제 완료: $PARTITION_NAME" | tee -a "$LOG_PATH"
#         else
#             echo "[$(date)] 백업 실패 또는 데이터 없음, 삭제 생략: $PARTITION_NAME" | tee -a "$LOG_PATH"
#         fi
#     done

#     echo "[$(date)] 2년 전 파티션 정리 완료" | tee -a "$LOG_PATH"
# fi
# endregion

# 로그 기록 (옵션)
echo "$(date +"%Y-%m-%d %H:%M:%S"): Backup completed on $(date)" | tee -a "$LOG_PATH"
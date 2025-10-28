from flask import request
import time
import threading
import json
import jwt
from flask_jwt_extended import decode_token
import logging
import log_config
from extensions import sockets

MAX_CONNECTIONS = 30    # 최대 동시 접속자 수
all_connections = {}    # 로그인 여부와 관계없이 모든 WebSocket 연결 저장장
active_users = {}       # 접속자 목록
CHECK_INTERVAL = 30      # 초 단위로 체크 간격
TIMEOUT = 60            # 초 단위로 타임아웃 시간

@sockets.route('/ws')
def websocket_hanlder(ws):
    """클라이언트 WebSocket 연결을 처리"""
    logging.info(f'New WebSocket connection from {request.remote_addr}')
    client_ip = request.remote_addr
    sid = f"{client_ip}:{time.time()}"
    
    all_connections[sid] = ws
    
    if len(active_users) >= MAX_CONNECTIONS:
        ws.send(json.dumps({'message': '최대 접속자 수를 초과했습니다.'}))
        ws.close()
        return
          
    try:
        broadcast_user_count()
       
        while not ws.closed:
            message = ws.receive()
            if message:
                data = json.loads(message)
                logging.info(f"Received message: {data}")
                
                if data.get("type") == "authenticate":
                    handle_authenticate(ws, sid, data)
                elif data.get("type") == "pong":
                    if sid in active_users:
                        active_users[sid]['last_active'] = time.time()
                elif data.get("type") == "disconnect":
                    if sid in active_users:
                        handle_disconnect(sid)
                    break
                
                ws.send(json.dumps({
                    'type':'update_user_count', 
                    'count':len(active_users),
                    'max_users':MAX_CONNECTIONS
                    }))
                
    except Exception as e:
        logging.error(f'Error in WebSocket connection: {e}')
    finally:
        all_connections.pop(sid, None)  
        if sid in active_users:
            handle_disconnect(sid)
        ws.close()
        logging.info(f'Connection from {sid} closed')

def handle_authenticate(ws, sid, data):
    """클라이언트의 인증 요청을 처리"""
    try:
        token = data.get('token')
        payload = decode_token(token)
        user_id = payload.get('sub')
                
        active_users[sid]['user_id'] = user_id
        ws.send(json.dumps({'type':'auth_success', 'user_id': user_id}))
        
        broadcast_user_count()
        
    except jwt.ExpiredSignatureError:
        ws.send(json.dumps({'type':'authentication_failed', 'message': '토큰이 만료되었습니다.'}))
        ws.close()
    except jwt.InvalidTokenError:
        ws.send(json.dumps({'type':'authentication_failed', 'message': '토큰이 유효하지 않습니다.'}))
        ws.close()
    except Exception as e:
        ws.send(json.dumps({'type':'authentication_failed', 'message': '알 수 없는 오류가 발생했습니다.'}))
        ws.close()

def broadcast_user_count():
    """현재 접속자 정보를 모든 클라이언트에게 전송"""
    user_count_data = json.dumps({
        'type':'update_user_count',
        'count':len(active_users),
        'max_users':MAX_CONNECTIONS
    })
    
    for sid, ws in list(all_connections.items()):
        try:            
            if ws and not ws.closed:
                ws.send(user_count_data)
        except Exception as e:
            logging.error(f'Error sending user count to {sid}: {e}')
        
def handle_disconnect(sid):
    """클라이언트 연결 종료 처리"""
    if sid in active_users:
        del active_users[sid]
        logging.info(f'Connection from {sid} closed')
        
        broadcast_user_count()

def check_inactive_clients():
    """비활성 사용자 주기적 제거"""
    while True:
        time.sleep(CHECK_INTERVAL)
        current_time = time.time()
        inactive_sids = [sid for sid, data in active_users.items() if current_time - data['last_active'] > TIMEOUT]
        
        for sid in inactive_sids:
            del active_users[sid]
            logging.info(f'Connection from {sid} closed due to inactivity')
            
        if inactive_sids:
            broadcast_user_count()

def check_inactive_connections():
    """비정상 종료된 WebSocket을 정리"""
    while True:
        time.sleep(60)  # ✅ 60초마다 체크
        inactive_sids = [sid for sid, ws in all_connections.items() if ws.closed]

        for sid in inactive_sids:
            logging.info(f"🗑️ 비정상 종료 감지: {sid} → 정리")
            all_connections.pop(sid, None)

        # ✅ 정리 후 전체 사용자에게 업데이트
        if inactive_sids:
            broadcast_user_count()
                       
# 비활성 사용자 제거 스레드 실행
threading.Thread(target=check_inactive_clients, daemon=True).start()
threading.Thread(target=check_inactive_connections, daemon=True).start()

## SocketIO 사용 구현 - C#의 
# from flask import Flask, render_template, request, current_app
# from flask_socketio import SocketIO, emit
# from extensions import socketio
# import time
# import threading
# from flask_jwt_extended import decode_token
# import jwt
# import logging
# import log_config

# MAX_CONNECTIONS = 30    # 최대 동시 접속자 수   
# active_users = {}       # 접속자 목록
# CHECK_INTERVAL = 60      # 초 단위로 체크 간격
# TIMEOUT = 5            # 초 단위로 타임아웃 시간

# @socketio.on('connect')
# def handle_connect():
#     """사용자가 접속하면 목록에 추가"""
#     logging.info(f'HHHHHHHHHHHH')
      
#     client_ip = request.remote_addr # 클라이언트 IP 주소
#     sid = request.sid # 클라이언트의 Socket ID
    
#     if len(active_users) >= MAX_CONNECTIONS:
#         socketio.emit('connection_dinied', {'message': '최대 접속자 수를 초과했습니다.'}, room=request.sid)
#         socketio.disconnect(request.sid)
#         return
    
#     logging.info(f'New connection from {client_ip} with SID {sid} and {len(active_users)} active users')
#     active_users[sid] = {'last_active':time.time(), 'user_id':None} # 현재 시간 저장
#     socketio.emit('update_user_count', len(active_users), broadcast=True)

# @socketio.on('authenticate')
# def handle_authenticate(data):
#     """클라이언트의 인증 요청을 처리"""
#     sid = request.sid
    
#     try:
#         token = data.get('token')     
    
#         payload = decode_token(token)
#         user_id = payload.get('sub')
        
#         if user_id not in active_users:
#             active_users[user_id] = {}
        
#         active_users[user_id][sid] = {'last_active': time.time()}
#         socketio.emit('auth_success', {'user_id': user_id}, room=sid)
        
#     except jwt.ExpiredSignatureError:
#         emit('authentication_failed', {'message': '토큰이 만료되었습니다.'}, room=sid)
#         socketio.disconnect(sid)
#     except jwt.InvalidTokenError:
#         emit('authentication_failed', {'message': '토큰이 유효하지 않습니다.'}, room=sid)
#         socketio.disconnect(sid)
#     except Exception as e:
#         emit('authentication_failed', {'message': '알 수 없는 오류가 발생했습니다.'}, room=sid)
#         socketio.disconnect(sid)
            
# @socketio.on('pong_response')
# def handle_pong_response():
#     """클라이언트의 PONG 응답을 처리"""
#     sid = request.sid
    
#     for user_id, sessions in active_users.items():
#         if sid in sessions:
#             sessions[sid]['last_active'] = time.time()
#             break
        
# @socketio.on('disconnect')
# def handle_disconnect():
#     """사용자가 접속을 해제하면 목록에서 제거"""
#     sid = request.sid
    
#     for user_id, sessions in list(active_users.items()):
#         if sid in sessions:
#             del sessions[sid]
#             if not sessions:
#                 del active_users[user_id]
#             break
        
#     socketio.emit('update_user_count', len(active_users), broadcast=True)

# def check_inactive_clients():
#     """비활성 사용자를 확인하고 제거"""
#     while True:
#         current_time = time.time()
#         inactive_users = []
        
#         for user_id, sessions in list(active_users.items()):
#             inactive_sids = [sid for sid, data in sessions.items() if current_time - data['last_active'] > TIMEOUT]
#             for sid in inactive_sids:
#                 del sessions[sid]
#             if not sessions:
#                 inactive_users.append(user_id)
                
#         for user_id in inactive_users:
#             del active_users[user_id]
        
#         socketio.emit('update_user_count', len(active_users), broadcast=True)
#         time.sleep(CHECK_INTERVAL)
        
        
# # 비활성 사용자 확인 스레드 시작
# threading.Thread(target=check_inactive_clients, daemon=True).start()



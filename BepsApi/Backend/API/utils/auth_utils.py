from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

#region 쿠키 또는 헤더에서 JWT를 검사하여 사용자 ID 반환
def get_current_user():
    try:
        verify_jwt_in_request()  # JWT 확인 (쿠키 or 헤더)
        return get_jwt_identity()  # 사용자 ID 반환
    except Exception:
        return None  # 인증 실패 시 None 반환
#endregion

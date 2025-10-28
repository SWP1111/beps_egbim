from flask import Blueprint

# 🔹 블루프린트 생성
def register_blueprints(app):
    from blueprints.user import api_user_bp
    from blueprints.leaning import api_leaning_bp
    from blueprints.contents_routes import api_contents_bp
    from blueprints.memo_routes import api_memo_bp
    from blueprints.memo_reply_routes import api_memo_reply_bp
    from blueprints.statistics_routes import api_statistics_bp
    from blueprints.push_routes import api_push_bp
    from blueprints.descope_api_routes import api_descope_bp
    
    app.register_blueprint(api_user_bp, url_prefix='/user')
    app.register_blueprint(api_leaning_bp, url_prefix='/leaning')
    app.register_blueprint(api_contents_bp, url_prefix='/contents')
    app.register_blueprint(api_memo_bp, url_prefix='/memo')
    app.register_blueprint(api_memo_reply_bp, url_prefix='/memo/reply')
    app.register_blueprint(api_statistics_bp, url_prefix='/statistics')
    app.register_blueprint(api_push_bp, url_prefix='/leaning/push')
    app.register_blueprint(api_descope_bp, url_prefix='/user/descope')

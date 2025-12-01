"""
Aplicação Flask principal
"""
from flask import Flask
from flask_cors import CORS
from app.config import Config

def create_app(config_class=Config):
    """Factory function para criar a aplicação Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Log inicial
    app.logger.info("🚀 Inicializando aplicacao Flask...")
    app.logger.info(f"   DATABASE_URL do Config: {bool(config_class.DATABASE_URL)}")
    if config_class.DATABASE_URL:
        app.logger.info(f"   DATABASE_URL valor: {config_class.DATABASE_URL[:50]}...")
    
    # Inicializa diretórios
    config_class.init_app(app)
    
    # Habilita CORS
    CORS(app)
    
    # Inicializa banco de dados
    from app.database import init_db
    app.logger.info("📦 Inicializando banco de dados...")
    db = init_db(app)
    if db.is_connected():
        app.logger.info("✅ Banco de dados conectado com sucesso")
    else:
        app.logger.warning("⚠️ Banco de dados nao configurado - usando modo arquivo")
        app.logger.warning(f"   DATABASE_URL configurada: {bool(app.config.get('DATABASE_URL'))}")
        if app.config.get('DATABASE_URL'):
            app.logger.warning(f"   DATABASE_URL valor: {app.config.get('DATABASE_URL')[:50]}...")
        else:
            app.logger.error("   DATABASE_URL nao encontrada no app.config!")
    
    # Garante que o banco está disponível globalmente
    @app.before_request
    def ensure_db_initialized():
        """Garante que o banco está inicializado antes de cada requisição"""
        from app.database import get_db
        db_instance = get_db()
        if not db_instance.is_connected():
            app.logger.error("❌ Banco de dados nao conectado! Verifique DATABASE_URL no .env")
    
    # Registra blueprints
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Inicializa cronjobs
    from app.scheduler import init_scheduler
    init_scheduler(app)
    
    return app

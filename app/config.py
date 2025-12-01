"""
Configurações da aplicação Flask
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

class Config:
    """Configurações base"""
    
    # Diretório base
    BASE_DIR = Path(__file__).parent.parent
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Clinicorp
    CLINICORP_BASE_URL = os.getenv("CLINICORP_BASE_URL", "https://sistema.clinicorp.com")
    CLINICORP_API_URL = os.getenv("CLINICORP_API_URL", "https://api.clinicorp.com")
    CLINICORP_USERNAME = os.getenv("CLINICORP_USERNAME", "william@essenciallis")
    CLINICORP_PASSWORD = os.getenv("CLINICORP_PASSWORD", "cJxc.LNwfT,/rH3")
    CLINICORP_CLINIC_ID = os.getenv("CLINICORP_CLINIC_ID", "6556997543657472")
    CLINICORP_AGENDA_ENDPOINT = os.getenv("CLINICORP_AGENDA_ENDPOINT", "/solution/api/appointment/list")
    
    # Supabase/PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DIRECT_URL = os.getenv("DIRECT_URL", "")
    
    # Scheduler
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    SCHEDULER_API_ENABLED = True
    SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "15"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = BASE_DIR / "logs" / "app.log"
    
    # Arquivos
    TOKEN_FILE = BASE_DIR / "data" / "token.json"
    AGENDA_DATA_FILE = BASE_DIR / "data" / "agenda_data.json"
    
    @staticmethod
    def init_app(app):
        """Inicializa configurações adicionais"""
        # Cria diretórios necessários
        (Config.BASE_DIR / "logs").mkdir(exist_ok=True)
        (Config.BASE_DIR / "data").mkdir(exist_ok=True)

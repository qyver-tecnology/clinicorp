"""
Arquivo de configuração do projeto
"""
import os
from pathlib import Path

# Diretório base do projeto
BASE_DIR = Path(__file__).parent

# Configurações de autenticação Clinicorp
CLINICORP_BASE_URL = "https://sistema.clinicorp.com"
CLINICORP_API_URL = "https://api.clinicorp.com"
CLINICORP_LOGIN_URL = f"{CLINICORP_BASE_URL}/login/"
CLINICORP_LOGIN_API_ENDPOINT = f"{CLINICORP_API_URL}/security/user/login"

# Credenciais (podem ser sobrescritas por variáveis de ambiente)
CLINICORP_USERNAME = os.getenv("CLINICORP_USERNAME", "william@essenciallis")
CLINICORP_PASSWORD = os.getenv("CLINICORP_PASSWORD", "cJxc.LNwfT,/rH3")

# Arquivo de token
TOKEN_FILE = BASE_DIR / "token.json"

# Endpoint de agenda (pode ser sobrescrito por variável de ambiente)
CLINICORP_AGENDA_ENDPOINT = os.getenv("CLINICORP_AGENDA_ENDPOINT", "/solution/api/appointment/list")

# Clinic ID (pode ser sobrescrito por variável de ambiente)
# Use o Clinic_BusinessId dos eventos da agenda
CLINICORP_CLINIC_ID = os.getenv("CLINICORP_CLINIC_ID", "6556997543657472")

# Configurações de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "clinicorp.log"


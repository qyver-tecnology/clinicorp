"""
Script para adicionar coluna total_profissionais à tabela sync_history
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import re

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_total_profissionais_column():
    """Adiciona coluna total_profissionais à tabela sync_history"""
    # Usa DIRECT_URL para migrações (sem pgbouncer)
    database_url = os.getenv('DIRECT_URL') or os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("DIRECT_URL ou DATABASE_URL nao configurada. Verifique o arquivo .env")
        return False
    
    # Remove parâmetro pgbouncer se existir (não é válido para psycopg2)
    if 'pgbouncer=true' in database_url or 'pgbouncer=' in database_url:
        database_url = re.sub(r'[?&]pgbouncer=[^&]*', '', database_url)
        logger.info("Removendo parametro pgbouncer da URL (usando conexao direta)")
    
    try:
        logger.info("Conectando ao banco de dados...")
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False
        )
        
        with engine.connect() as conn:
            # Verifica se a coluna já existe
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sync_history' 
                AND column_name = 'total_profissionais'
            """)
            
            result = conn.execute(check_query)
            column_exists = result.fetchone() is not None
            
            if column_exists:
                logger.info("✅ Coluna 'total_profissionais' ja existe na tabela sync_history")
                return True
            
            # Adiciona a coluna
            logger.info("Adicionando coluna 'total_profissionais' à tabela sync_history...")
            alter_query = text("""
                ALTER TABLE sync_history 
                ADD COLUMN total_profissionais INTEGER DEFAULT 0
            """)
            
            conn.execute(alter_query)
            conn.commit()
            
            logger.info("✅ Coluna 'total_profissionais' adicionada com sucesso!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar coluna: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    add_total_profissionais_column()


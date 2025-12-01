"""
Script para inicializar o banco de dados
Cria as tabelas necessárias
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

# Define modelos diretamente aqui para evitar importar Flask
class AgendaEvent(Base):
    """Modelo para eventos da agenda"""
    __tablename__ = 'agenda_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evento_id = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String(500))
    descricao = Column(Text)
    data = Column(DateTime, nullable=False, index=True)
    data_atomic = Column(Integer, index=True)
    hora_inicio = Column(String(10))
    hora_fim = Column(String(10))
    hora_inicio_numero = Column(Integer)
    profissional = Column(String(200))
    categoria = Column(String(200))
    paciente_id = Column(String(50))
    dentista_id = Column(String(50))
    tipo = Column(String(50))
    ocupado = Column(Boolean, default=False, index=True)
    deletado = Column(Boolean, default=False)
    dados_originais = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class Profissional(Base):
    """Modelo para profissionais/dentistas"""
    __tablename__ = 'profissionais'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profissional_id = Column(String(50), unique=True, nullable=False, index=True)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True, index=True)
    dados_originais = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class SyncHistory(Base):
    """Modelo para histórico de sincronizações"""
    __tablename__ = 'sync_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    total_eventos = Column(Integer, default=0)
    eventos_ocupados = Column(Integer, default=0)
    eventos_livres = Column(Integer, default=0)
    total_profissionais = Column(Integer, default=0)
    sucesso = Column(Boolean, default=True)
    erro = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

def init_database():
    """Inicializa o banco de dados criando as tabelas"""
    # Usa DIRECT_URL para migrações (sem pgbouncer)
    database_url = os.getenv('DIRECT_URL') or os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("DIRECT_URL ou DATABASE_URL nao configurada. Verifique o arquivo .env")
        return False
    
    # Remove parâmetro pgbouncer se existir (não é válido para psycopg2)
    if 'pgbouncer=true' in database_url:
        database_url = database_url.replace('?pgbouncer=true', '').replace('&pgbouncer=true', '')
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
        
        logger.info("Criando tabelas no banco de dados...")
        Base.metadata.create_all(engine)
        logger.info("✅ Tabelas criadas com sucesso!")
        logger.info("  - agenda_events")
        logger.info("  - profissionais")
        logger.info("  - sync_history")
        return True
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    init_database()

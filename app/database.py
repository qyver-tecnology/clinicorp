"""
Módulo de banco de dados Supabase/PostgreSQL
"""
import os
import re
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, JSON, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class AgendaEvent(Base):
    """Modelo para eventos da agenda"""
    __tablename__ = 'agenda_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evento_id = Column(String, unique=True, nullable=False, index=True)  # ID do evento no Clinicorp
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
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'evento_id': self.evento_id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'data': self.data.isoformat() if self.data else None,
            'data_atomic': self.data_atomic,
            'hora_inicio': self.hora_inicio,
            'hora_fim': self.hora_fim,
            'hora_inicio_numero': self.hora_inicio_numero,
            'profissional': self.profissional,
            'categoria': self.categoria,
            'paciente_id': self.paciente_id,
            'dentista_id': self.dentista_id,
            'tipo': self.tipo,
            'ocupado': self.ocupado,
            'deletado': self.deletado,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class Profissional(Base):
    """Modelo para profissionais/dentistas"""
    __tablename__ = 'profissionais'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profissional_id = Column(String(50), unique=True, nullable=False, index=True)  # ID do profissional no Clinicorp
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True, index=True)
    dados_originais = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'profissional_id': self.profissional_id,
            'nome': self.nome,
            'ativo': self.ativo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

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

class Database:
    """Gerenciador de banco de dados"""
    
    def __init__(self, database_url: str = None):
        """
        Inicializa conexão com banco de dados
        
        Args:
            database_url: URL de conexão do Supabase/PostgreSQL (já processada, sem pgbouncer)
        """
        self.database_url = database_url
        
        if not self.database_url:
            logger.warning("DATABASE_URL nao configurada. Usando modo arquivo apenas.")
            logger.warning(f"   Tentou usar: {database_url or 'os.getenv(DATABASE_URL)'}")
            self.engine = None
            self.Session = None
            return
        
        try:
            logger.info(f"Tentando conectar ao banco de dados...")
            logger.debug(f"   DATABASE_URL: {self.database_url[:50]}..." if len(self.database_url) > 50 else f"   DATABASE_URL: {self.database_url}")
            
            # Cria engine com pool de conexões
            self.engine = create_engine(
                self.database_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False
            )
            
            # Cria session factory
            self.Session = scoped_session(sessionmaker(bind=self.engine))
            
            # Testa a conexão
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Cria tabelas se não existirem
            Base.metadata.create_all(self.engine)
            
            logger.info("✅ Conexao com banco de dados estabelecida com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com banco de dados: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            self.engine = None
            self.Session = None
    
    @contextmanager
    def get_session(self):
        """Context manager para sessão do banco"""
        if not self.Session:
            raise Exception("Banco de dados nao configurado")
        
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Erro na sessao do banco: {e}")
            raise
        finally:
            session.close()
    
    def is_connected(self) -> bool:
        """Verifica se está conectado ao banco"""
        return self.engine is not None and self.Session is not None

# Instância global do banco de dados (será inicializada pelo Flask)
db = None

def init_db(app=None):
    """Inicializa o banco de dados com as configurações do Flask"""
    global db
    
    # SEMPRE prioriza DIRECT_URL quando disponível (sem pgbouncer)
    direct_url = None
    database_url = None
    
    if app:
        direct_url = app.config.get('DIRECT_URL') or os.getenv('DIRECT_URL')
        database_url = app.config.get('DATABASE_URL')
        logger.info(f"Inicializando banco de dados com app Flask.")
        logger.info(f"   DIRECT_URL configurada: {bool(direct_url)}")
        logger.info(f"   DATABASE_URL configurada: {bool(database_url)}")
    else:
        # Tenta importar do config Flask primeiro
        try:
            from app.config import Config
            direct_url = Config.DIRECT_URL or os.getenv('DIRECT_URL')
            database_url = Config.DATABASE_URL
            logger.info(f"Inicializando banco de dados sem app Flask.")
            logger.info(f"   DIRECT_URL do Config: {bool(direct_url)}")
            logger.info(f"   DATABASE_URL do Config: {bool(database_url)}")
        except ImportError:
            direct_url = os.getenv('DIRECT_URL')
            database_url = os.getenv('DATABASE_URL')
            logger.info(f"Inicializando banco de dados sem app Flask.")
            logger.info(f"   DIRECT_URL do env: {bool(direct_url)}")
            logger.info(f"   DATABASE_URL do env: {bool(database_url)}")
    
    # Usa DIRECT_URL se disponível, senão usa DATABASE_URL (removendo pgbouncer)
    final_url = None
    if direct_url:
        logger.info("✅ Usando DIRECT_URL (conexao direta sem pgbouncer)")
        final_url = direct_url
    elif database_url:
        # Remove parâmetros pgbouncer que não são suportados pelo psycopg2
        if 'pgbouncer=true' in database_url or 'pgbouncer=' in database_url:
            logger.warning("⚠️ Removendo parametros pgbouncer da DATABASE_URL")
            final_url = re.sub(r'[?&]pgbouncer=[^&]*', '', database_url)
            final_url = final_url.replace('?pgbouncer=true', '').replace('&pgbouncer=true', '')
        else:
            final_url = database_url
        logger.info("⚠️ Usando DATABASE_URL (pode ter limitacoes)")
    else:
        logger.warning("❌ Nenhuma URL de banco de dados encontrada!")
        final_url = None
    
    db = Database(final_url)
    return db

def get_db():
    """Retorna a instância atual do banco de dados"""
    global db
    if db is None:
        # Tenta inicializar se ainda não foi inicializado
        logger.warning("⚠️ Banco de dados nao inicializado. Tentando inicializar...")
        db = init_db()
        if db.is_connected():
            logger.info("✅ Banco de dados inicializado com sucesso via get_db()")
        else:
            logger.error("❌ Falha ao inicializar banco de dados. Verifique DATABASE_URL no .env")
            logger.error(f"   DATABASE_URL configurada: {bool(db.database_url if hasattr(db, 'database_url') else None)}")
    else:
        # Verifica se ainda está conectado
        if not db.is_connected():
            logger.warning("⚠️ Banco de dados foi desconectado. Tentando reconectar...")
            db = init_db()
    return db


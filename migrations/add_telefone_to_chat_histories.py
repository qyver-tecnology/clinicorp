"""
Migração para adicionar campos de telefone e contexto ao histórico de chat
- Adiciona coluna telefone para facilitar buscas
- Adiciona coluna contexto para armazenar informações do paciente
- Adiciona índices para melhorar performance
"""
import os
from dotenv import load_dotenv
import psycopg2

# Carregar variáveis de ambiente
load_dotenv()

def get_connection():
    """Obtém conexão com o banco"""
    database_url = os.getenv('DIRECT_URL') or os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL ou DIRECT_URL não configurada no .env")
        return None
    
    # Remover parâmetro pgbouncer se existir
    if '?pgbouncer' in database_url:
        database_url = database_url.split('?')[0]
    
    return psycopg2.connect(database_url)

def add_telefone_column(cursor):
    """Adiciona coluna de telefone à tabela n8n_chat_histories"""
    
    try:
        cursor.execute("""
        ALTER TABLE n8n_chat_histories 
        ADD COLUMN IF NOT EXISTS telefone VARCHAR(20);
        """)
        print("✅ Coluna 'telefone' adicionada!")
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("⚠️ Coluna 'telefone' já existe")
        else:
            raise

def add_contexto_column(cursor):
    """Adiciona coluna de contexto à tabela n8n_chat_histories"""
    
    try:
        cursor.execute("""
        ALTER TABLE n8n_chat_histories 
        ADD COLUMN IF NOT EXISTS contexto JSONB DEFAULT '{}';
        """)
        print("✅ Coluna 'contexto' adicionada!")
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("⚠️ Coluna 'contexto' já existe")
        else:
            raise

def add_nome_column(cursor):
    """Adiciona coluna de nome do paciente"""
    
    try:
        cursor.execute("""
        ALTER TABLE n8n_chat_histories 
        ADD COLUMN IF NOT EXISTS nome_paciente VARCHAR(255);
        """)
        print("✅ Coluna 'nome_paciente' adicionada!")
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("⚠️ Coluna 'nome_paciente' já existe")
        else:
            raise

def add_email_column(cursor):
    """Adiciona coluna de email do paciente"""
    
    try:
        cursor.execute("""
        ALTER TABLE n8n_chat_histories 
        ADD COLUMN IF NOT EXISTS email_paciente VARCHAR(255);
        """)
        print("✅ Coluna 'email_paciente' adicionada!")
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("⚠️ Coluna 'email_paciente' já existe")
        else:
            raise

def create_indexes(cursor):
    """Cria índices para melhorar performance"""
    
    # Índice para telefone
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chat_histories_telefone 
    ON n8n_chat_histories(telefone);
    """)
    print("✅ Índice 'telefone' criado!")
    
    # Índice para session_id + telefone
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chat_histories_session_telefone 
    ON n8n_chat_histories(session_id, telefone);
    """)
    print("✅ Índice 'session_id + telefone' criado!")
    
    # Índice para contexto
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chat_histories_contexto 
    ON n8n_chat_histories USING GIN(contexto);
    """)
    print("✅ Índice 'contexto' criado!")

def run_migrations():
    """Executa todas as migrações"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        print("\n🔄 Iniciando migrações...\n")
        
        add_telefone_column(cursor)
        add_contexto_column(cursor)
        add_nome_column(cursor)
        add_email_column(cursor)
        create_indexes(cursor)
        
        conn.commit()
        print("\n✅ Todas as migrações executadas com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_migrations()

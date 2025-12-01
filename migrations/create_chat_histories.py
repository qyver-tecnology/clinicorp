"""
Migração para criar tabelas do n8n
- n8n_chat_histories: histórico de conversas
- documents: contexto RAG
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

def create_chat_histories_table(cursor):
    """Cria a tabela n8n_chat_histories"""
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS n8n_chat_histories (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(255) NOT NULL,
        message JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chat_histories_session_id 
    ON n8n_chat_histories(session_id);
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chat_histories_created_at 
    ON n8n_chat_histories(created_at DESC);
    """)
    
    print("✅ Tabela n8n_chat_histories criada!")

def create_documents_table(cursor):
    """Cria a tabela documents para RAG"""
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        content TEXT NOT NULL,
        metadata JSONB DEFAULT '{}',
        embedding VECTOR(1536),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_documents_metadata 
    ON documents USING GIN(metadata);
    """)
    
    print("✅ Tabela documents criada!")

def run_migrations():
    """Executa todas as migrações"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        # Habilitar extensão vector se disponível
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except:
            print("⚠️ Extensão vector não disponível (opcional)")
        
        create_chat_histories_table(cursor)
        create_documents_table(cursor)
        
        conn.commit()
        print("\n✅ Todas as migrações executadas com sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_migrations()

"""
Migração para criar tabela de agendamentos locais

Esta tabela é usada por AgendaService.buscar_agendamentos_por_telefone
para permitir que a IA consulte os agendamentos futuros de um paciente
pelo telefone.
"""
import os
from dotenv import load_dotenv
import psycopg2

# Carregar variáveis de ambiente
load_dotenv()


def get_connection():
    """Obtém conexão com o banco (mesmo padrão de create_chat_histories.py)."""
    database_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL ou DIRECT_URL não configurada no .env")
        return None

    # Remover parâmetro pgbouncer se existir
    if "?pgbouncer" in database_url:
        database_url = database_url.split("?")[0]

    return psycopg2.connect(database_url)


def create_agendamentos_table(cursor):
    """Cria a tabela agendamentos se não existir."""

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agendamentos (
            id SERIAL PRIMARY KEY,
            data_agendamento DATE NOT NULL,
            hora_inicio VARCHAR(10) NOT NULL,
            hora_fim VARCHAR(10) NOT NULL,
            profissional_nome TEXT,
            procedimento TEXT,
            status VARCHAR(50) DEFAULT 'confirmado',
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Índice para buscas por telefone dentro de metadata
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agendamentos_metadata_telefone
        ON agendamentos USING GIN (metadata);
        """
    )

    # Índice para ordenar por data/hora
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agendamentos_data_hora
        ON agendamentos (data_agendamento, hora_inicio);
        """
    )

    print("✅ Tabela agendamentos criada/atualizada com sucesso!")


def run_migrations():
    """Executa a migração de criação da tabela agendamentos."""
    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        create_agendamentos_table(cursor)
        conn.commit()
        print("\n✅ Migração de agendamentos executada com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao executar migração de agendamentos: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migrations()

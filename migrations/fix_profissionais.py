"""
Script para corrigir nomes dos profissionais no banco de dados
Remove profissionais com nomes incorretos e permite que sejam recriados na próxima sincronização
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

def fix_profissionais():
    """Remove profissionais com nomes incorretos do banco"""
    # Usa DIRECT_URL para migrações (sem pgbouncer)
    database_url = os.getenv('DIRECT_URL') or os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("DIRECT_URL ou DATABASE_URL nao configurada. Verifique o arquivo .env")
        return False
    
    # Remove parâmetro pgbouncer se existir
    if 'pgbouncer=true' in database_url or 'pgbouncer=' in database_url:
        database_url = re.sub(r'[?&]pgbouncer=[^&]*', '', database_url)
        logger.info("Removendo parametro pgbouncer da URL")
    
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
            # Lista profissionais atuais
            select_query = text("SELECT id, profissional_id, nome FROM profissionais WHERE ativo = true")
            result = conn.execute(select_query)
            profissionais = result.fetchall()
            
            logger.info(f"Encontrados {len(profissionais)} profissionais ativos")
            
            # Identifica profissionais com nomes incorretos
            # Nomes que parecem ser títulos de eventos ou genéricos
            profissionais_incorretos = []
            for prof in profissionais:
                nome = prof[2] or ''
                profissional_id = prof[1]
                
                # Verifica se o nome parece ser incorreto
                nome_lower = nome.lower().strip()
                
                # Nomes que são claramente títulos de eventos
                if nome_lower in ['folga', 'niver bella <3']:
                    profissionais_incorretos.append((prof[0], profissional_id, nome))
                    logger.info(f"  - Profissional {profissional_id}: '{nome}' (parece ser título de evento)")
                # Nomes genéricos
                elif nome.startswith('Profissional '):
                    profissionais_incorretos.append((prof[0], profissional_id, nome))
                    logger.info(f"  - Profissional {profissional_id}: '{nome}' (nome genérico)")
            
            if not profissionais_incorretos:
                logger.info("✅ Nenhum profissional com nome incorreto encontrado!")
                return True
            
            logger.info(f"\nEncontrados {len(profissionais_incorretos)} profissionais com nomes incorretos")
            resposta = input("Deseja remover estes profissionais para que sejam recriados na próxima sincronização? (s/n): ")
            
            if resposta.lower() != 's':
                logger.info("Operação cancelada pelo usuário")
                return False
            
            # Remove profissionais incorretos
            for prof_id, profissional_id, nome in profissionais_incorretos:
                delete_query = text("DELETE FROM profissionais WHERE id = :id")
                conn.execute(delete_query, {"id": prof_id})
                logger.info(f"  ✅ Removido: {nome} (ID: {profissional_id})")
            
            conn.commit()
            logger.info(f"\n✅ {len(profissionais_incorretos)} profissionais removidos com sucesso!")
            logger.info("Execute uma sincronização manual para recriar os profissionais com nomes corretos:")
            logger.info("  curl -X POST http://localhost:5000/api/agenda/sync")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir profissionais: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    fix_profissionais()


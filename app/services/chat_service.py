"""
Serviço para gerenciar histórico de conversas com pacientes
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ChatService:
    """Serviço para gerenciar histórico de chats"""
    
    def __init__(self):
        """Inicializa o serviço de chat"""
        self.db = get_db()
    
    def buscar_historico_por_telefone(self, telefone: str, dias: int = 30) -> List[Dict]:
        """
        Busca o histórico de conversas de um paciente pelo telefone
        
        Args:
            telefone: Telefone do paciente
            dias: Número de dias para buscar histórico (padrão 30 dias)
            
        Returns:
            Lista de mensagens do histórico
        """
        try:
            if not self.db.is_connected():
                logger.warning("Banco de dados não conectado. Não foi possível buscar histórico.")
                return []
            
            with self.db.get_session() as session:
                # Busca o session_id associado ao telefone
                query = text("""
                    SELECT DISTINCT session_id 
                    FROM n8n_chat_histories 
                    WHERE message->>'telefone' = :telefone 
                    OR message->>'phone' = :telefone
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = session.execute(query, {'telefone': telefone}).fetchone()
                
                if not result:
                    logger.info(f"📞 Nenhum histórico encontrado para telefone: {telefone}")
                    return []
                
                session_id = result[0]
                logger.info(f"👤 Histórico encontrado para telefone {telefone} - Session ID: {session_id}")
                
                # Busca todas as mensagens da sessão nos últimos N dias
                data_limite = datetime.utcnow() - timedelta(days=dias)
                
                query = text("""
                    SELECT message, created_at 
                    FROM n8n_chat_histories 
                    WHERE session_id = :session_id 
                    AND created_at >= :data_limite
                    ORDER BY created_at ASC
                """)
                results = session.execute(query, {
                    'session_id': session_id,
                    'data_limite': data_limite
                }).fetchall()
                
                historico = []
                for row in results:
                    historico.append({
                        'message': row[0],
                        'created_at': row[1].isoformat() if row[1] else None
                    })
                
                logger.info(f"📋 Encontradas {len(historico)} mensagens no histórico")
                return historico
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar histórico de chat: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def buscar_resumo_conversas_anteriores(self, telefone: str, dias: int = 30) -> str:
        """
        Busca um resumo das conversas anteriores com o paciente
        
        Args:
            telefone: Telefone do paciente
            dias: Número de dias para buscar histórico
            
        Returns:
            String com resumo das conversas anteriores
        """
        try:
            historico = self.buscar_historico_por_telefone(telefone, dias)
            
            if not historico:
                return ""
            
            # Extrai informações relevantes do histórico
            resumo_parts = []
            ultima_conversa = None
            
            for msg in historico:
                if isinstance(msg.get('message'), dict):
                    msg_dict = msg['message']
                    if msg_dict.get('role') == 'user':
                        resumo_parts.append(f"- {msg_dict.get('content', '')}")
                    ultima_conversa = msg.get('created_at')
            
            if not resumo_parts:
                return ""
            
            resumo = f"""
📝 HISTÓRICO DE CONVERSAS ANTERIORES (últimos {dias} dias):
Última conversa: {ultima_conversa}

Tópicos discutidos:
{chr(10).join(resumo_parts[:10])}  # Limita a 10 últimas mensagens
"""
            logger.info(f"📊 Resumo gerado para telefone {telefone}")
            return resumo
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar resumo de conversas: {e}")
            return ""
    
    def verificar_paciente_conhecido(self, telefone: str) -> Dict:
        """
        Verifica se o paciente já conversou antes e retorna informações
        
        Args:
            telefone: Telefone do paciente
            
        Returns:
            Dicionário com informações do paciente
        """
        try:
            if not self.db.is_connected():
                logger.warning("Banco de dados não conectado.")
                return {'conhecido': False, 'telefone': telefone}
            
            with self.db.get_session() as session:
                # Busca informações do paciente no banco de chat histories
                query = text("""
                    SELECT DISTINCT 
                        telefone,
                        nome_paciente as nome,
                        email_paciente as email,
                        MAX(created_at) as ultima_conversa
                    FROM n8n_chat_histories 
                    WHERE telefone = :telefone 
                    AND nome_paciente IS NOT NULL
                    AND nome_paciente != ''
                    GROUP BY telefone, nome_paciente, email_paciente
                    LIMIT 1
                """)
                result = session.execute(query, {'telefone': telefone}).fetchone()
                
                if result:
                    tel, nome, email, ultima_conversa = result
                    logger.info(f"✅ Paciente conhecido: {nome} ({telefone})")
                    return {
                        'conhecido': True,
                        'telefone': telefone,
                        'nome': nome,
                        'email': email or '',
                        'ultima_conversa': ultima_conversa.isoformat() if ultima_conversa else None
                    }
                else:
                    logger.info(f"❌ Paciente desconhecido: {telefone}")
                    return {'conhecido': False, 'telefone': telefone}
                    
        except Exception as e:
            logger.error(f"❌ Erro ao verificar paciente: {e}")
            return {'conhecido': False, 'telefone': telefone, 'erro': str(e)}
    
    def obter_nome_paciente_por_telefone(self, telefone: str) -> Optional[str]:
        """
        Obtém o nome do paciente pelo telefone do histórico
        
        Args:
            telefone: Telefone do paciente
            
        Returns:
            Nome do paciente ou None
        """
        try:
            if not self.db.is_connected():
                logger.warning("Banco de dados não conectado.")
                return None
            
            with self.db.get_session() as session:
                query = text("""
                    SELECT nome_paciente
                    FROM n8n_chat_histories 
                    WHERE telefone = :telefone 
                    AND nome_paciente IS NOT NULL
                    AND nome_paciente != ''
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = session.execute(query, {'telefone': telefone}).fetchone()
                
                if result and result[0]:
                    nome = result[0]
                    logger.info(f"📝 Nome do paciente obtido do histórico: {nome} ({telefone})")
                    return nome
                
                logger.debug(f"Nenhum nome encontrado no histórico para: {telefone}")
                return None
                    
        except Exception as e:
            logger.error(f"❌ Erro ao obter nome do paciente: {e}")
            return None
    
    def salvar_mensagem_chat(self, session_id: str, mensagem: Dict, telefone: str = None, nome_paciente: str = None, email_paciente: str = None) -> bool:
        """
        Salva uma mensagem no histórico de chat
        
        Args:
            session_id: ID da sessão
            mensagem: Dicionário com dados da mensagem
            telefone: Telefone do paciente (opcional)
            nome_paciente: Nome do paciente (opcional)
            email_paciente: Email do paciente (opcional)
            
        Returns:
            True se salvo com sucesso
        """
        try:
            if not self.db.is_connected():
                logger.warning("Banco de dados não conectado. Mensagem não será salva.")
                return False
            
            with self.db.get_session() as session:
                query = text("""
                    INSERT INTO n8n_chat_histories (session_id, message, telefone, nome_paciente, email_paciente)
                    VALUES (:session_id, :message, :telefone, :nome_paciente, :email_paciente)
                """)
                session.execute(query, {
                    'session_id': session_id,
                    'message': str(mensagem),
                    'telefone': telefone,
                    'nome_paciente': nome_paciente,
                    'email_paciente': email_paciente
                })
                
                logger.debug(f"💾 Mensagem salva para sessão {session_id} - Telefone: {telefone}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar mensagem: {e}")
            return False
    
    def obter_contexto_paciente(self, telefone: str) -> str:
        """
        Obtém contexto completo do paciente para usar na IA
        
        Args:
            telefone: Telefone do paciente
            
        Returns:
            String com contexto formatado para a IA
        """
        try:
            info_paciente = self.verificar_paciente_conhecido(telefone)
            
            if not info_paciente.get('conhecido'):
                logger.info(f"📌 Novo paciente: {telefone}")
                return f"Este é um novo paciente. Telefone: {telefone}"
            
            contexto = f"""
🔍 CONTEXTO DO PACIENTE:
- Nome: {info_paciente.get('nome', 'Desconhecido')}
- Telefone: {telefone}
- Email: {info_paciente.get('email', 'Não informado')}
- Última conversa: {info_paciente.get('ultima_conversa', 'Desconhecida')}

{self.buscar_resumo_conversas_anteriores(telefone)}
"""
            logger.info(f"📋 Contexto gerado para paciente {telefone}")
            return contexto
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter contexto: {e}")
            return f"Telefone: {telefone}"

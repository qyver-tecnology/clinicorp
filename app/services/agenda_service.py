"""
Serviço de agenda - lógica de negócio
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pytz
from sqlalchemy import func
from app.database import get_db, AgendaEvent, SyncHistory, Profissional
from api.agenda_api import AgendaAPI

logger = logging.getLogger(__name__)

class AgendaService:
    """Serviço para gerenciar agenda"""
    
    def __init__(self):
        self.agenda_api = AgendaAPI()
        self.timezone_brasil = pytz.timezone('America/Sao_Paulo')
    
    def sincronizar_agenda(self) -> Dict:
        """
        Sincroniza profissionais e agenda de cada um, salvando no banco de dados
        
        Returns:
            Dicionário com resultado da sincronização
        """
        try:
            logger.info("🔄 Iniciando sincronizacao completa (profissionais + agendas)...")
            timestamp = datetime.now(self.timezone_brasil)
            
            db = get_db()
            if not db.is_connected():
                logger.warning("⚠️ Banco de dados nao conectado. Sincronizacao limitada.")
                return {
                    'timestamp': timestamp.isoformat(),
                    'erro': 'Banco de dados nao conectado',
                    'sucesso': False
                }
            
            # PASSO 1: Buscar e salvar profissionais
            logger.info("👥 Passo 1: Buscando profissionais...")
            profissionais = self.agenda_api.listar_profissionais()
            profissionais_salvos = self._salvar_profissionais_no_banco(profissionais, timestamp)
            logger.info(f"✅ Profissionais atualizados: {profissionais_salvos} profissionais salvos")
            
            # PASSO 2: Buscar agenda geral do mês completo (9h-18h)
            logger.info("📅 Passo 2: Buscando agenda geral do mes completo...")
            eventos_gerais = self.agenda_api.buscar_agenda_mes_completo(hora_inicio=9, hora_fim=18)
            
            # PASSO 3: Buscar agenda de cada profissional individualmente
            logger.info(f"📅 Passo 3: Processando eventos por profissional...")
            todos_eventos = list(eventos_gerais)  # Usa eventos gerais que já contêm todos os profissionais
            
            # Agrupa eventos por profissional para log
            eventos_por_profissional = {}
            for evento in todos_eventos:
                dentista_id = str(evento.get('dentista_id', ''))
                if dentista_id:
                    if dentista_id not in eventos_por_profissional:
                        eventos_por_profissional[dentista_id] = []
                    eventos_por_profissional[dentista_id].append(evento)
            
            logger.info(f"   Eventos encontrados por profissional:")
            for profissional in profissionais:
                profissional_id = profissional.get('id')
                profissional_nome = profissional.get('nome', 'Sem nome')
                eventos_prof = eventos_por_profissional.get(str(profissional_id), [])
                ocupados = len([e for e in eventos_prof if e.get('ocupado')])
                livres = len([e for e in eventos_prof if not e.get('ocupado')])
                logger.info(f"   - {profissional_nome}: {len(eventos_prof)} eventos ({ocupados} ocupados, {livres} livres)")
            
            # Separa eventos ocupados e livres
            eventos_ocupados = [e for e in todos_eventos if e.get('ocupado')]
            eventos_livres = [e for e in todos_eventos if not e.get('ocupado')]
            
            # Log dos eventos livres encontrados
            logger.info(f"📋 Eventos livres encontrados na sincronizacao: {len(eventos_livres)}")
            for idx, evento_livre in enumerate(eventos_livres[:5], 1):  # Mostra até 5 primeiros
                data_str = evento_livre.get('data', 'N/A')
                hora = evento_livre.get('hora_inicio', 'N/A')
                titulo = evento_livre.get('titulo', 'N/A')
                logger.info(f"   Livre {idx}: {data_str} {hora} - {titulo}")
            if len(eventos_livres) > 5:
                logger.info(f"   ... e mais {len(eventos_livres) - 5} eventos livres")
            
            # PASSO 4: Salva eventos no banco de dados
            logger.info("💾 Passo 4: Salvando eventos no banco de dados...")
            eventos_salvos = self._salvar_eventos_no_banco(todos_eventos, timestamp)
            
            # Registra histórico
            self._registrar_historico(
                timestamp=timestamp,
                total_eventos=len(todos_eventos),
                eventos_ocupados=len(eventos_ocupados),
                eventos_livres=len(eventos_livres),
                total_profissionais=len(profissionais),
                sucesso=True
            )
            
            resultado = {
                'timestamp': timestamp.isoformat(),
                'total_profissionais': len(profissionais),
                'profissionais_salvos': profissionais_salvos,
                'total_eventos': len(todos_eventos),
                'eventos_ocupados': len(eventos_ocupados),
                'eventos_livres': len(eventos_livres),
                'eventos_salvos': eventos_salvos,
                'sucesso': True
            }
            
            logger.info(f"✅ Sincronizacao concluida: {len(profissionais)} profissionais, {len(todos_eventos)} eventos ({len(eventos_ocupados)} ocupados, {len(eventos_livres)} livres)")
            
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar agenda: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Registra erro no histórico
            self._registrar_historico(
                timestamp=datetime.now(self.timezone_brasil),
                total_eventos=0,
                eventos_ocupados=0,
                eventos_livres=0,
                total_profissionais=0,
                sucesso=False,
                erro=str(e)
            )
            
            return {
                'timestamp': datetime.now(self.timezone_brasil).isoformat(),
                'erro': str(e),
                'sucesso': False
            }
    
    def _salvar_eventos_no_banco(self, eventos: List[Dict], timestamp: datetime) -> int:
        """Salva eventos no banco de dados"""
        db = get_db()
        if not db.is_connected():
            return 0
        
        eventos_salvos = 0
        
        try:
            with db.get_session() as session:
                for evento_data in eventos:
                    evento_id = str(evento_data.get('id'))
                    if not evento_id:
                        continue
                    
                    # Converte data se necessário
                    data_evento = None
                    if evento_data.get('data'):
                        try:
                            if isinstance(evento_data['data'], str):
                                data_evento = datetime.fromisoformat(evento_data['data'].replace('Z', '+00:00'))
                                if data_evento.tzinfo:
                                    data_evento = data_evento.astimezone(self.timezone_brasil).replace(tzinfo=None)
                            elif isinstance(evento_data['data'], datetime):
                                data_evento = evento_data['data']
                                if data_evento.tzinfo:
                                    data_evento = data_evento.astimezone(self.timezone_brasil).replace(tzinfo=None)
                        except Exception as e:
                            logger.debug(f"Erro ao converter data do evento {evento_id}: {e}")
                    
                    # Busca ou cria evento
                    evento = session.query(AgendaEvent).filter_by(evento_id=evento_id).first()
                    
                    if evento:
                        # Atualiza evento existente
                        evento.titulo = evento_data.get('titulo')
                        evento.descricao = evento_data.get('descricao')
                        evento.data = data_evento
                        evento.data_atomic = evento_data.get('data_atomic')
                        evento.hora_inicio = evento_data.get('hora_inicio')
                        evento.hora_fim = evento_data.get('hora_fim')
                        evento.hora_inicio_numero = evento_data.get('hora_inicio_numero')
                        evento.profissional = evento_data.get('profissional')
                        evento.categoria = evento_data.get('categoria')
                        evento.paciente_id = str(evento_data.get('paciente_id')) if evento_data.get('paciente_id') else None
                        evento.dentista_id = str(evento_data.get('dentista_id')) if evento_data.get('dentista_id') else None
                        evento.tipo = evento_data.get('tipo')
                        evento.ocupado = evento_data.get('ocupado', False)
                        evento.deletado = evento_data.get('deletado', False)
                        evento.dados_originais = evento_data.get('dados_originais')
                        evento.updated_at = timestamp
                    else:
                        # Cria novo evento
                        evento = AgendaEvent(
                            evento_id=evento_id,
                            titulo=evento_data.get('titulo'),
                            descricao=evento_data.get('descricao'),
                            data=data_evento,
                            data_atomic=evento_data.get('data_atomic'),
                            hora_inicio=evento_data.get('hora_inicio'),
                            hora_fim=evento_data.get('hora_fim'),
                            hora_inicio_numero=evento_data.get('hora_inicio_numero'),
                            profissional=evento_data.get('profissional'),
                            categoria=evento_data.get('categoria'),
                            paciente_id=str(evento_data.get('paciente_id')) if evento_data.get('paciente_id') else None,
                            dentista_id=str(evento_data.get('dentista_id')) if evento_data.get('dentista_id') else None,
                            tipo=evento_data.get('tipo'),
                            ocupado=evento_data.get('ocupado', False),
                            deletado=evento_data.get('deletado', False),
                            dados_originais=evento_data.get('dados_originais')
                        )
                        session.add(evento)
                    
                    eventos_salvos += 1
                
                # Log de quantos eventos livres foram salvos
                eventos_livres_salvos = session.query(AgendaEvent).filter_by(
                    ocupado=False, deletado=False
                ).count()
                logger.info(f"💾 Eventos salvos: {eventos_salvos} total, {eventos_livres_salvos} livres no banco")
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Erro ao salvar eventos no banco: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return eventos_salvos
    
    def _salvar_profissionais_no_banco(self, profissionais: List[Dict], timestamp: datetime) -> int:
        """Salva profissionais no banco de dados"""
        db = get_db()
        if not db.is_connected():
            return 0
        
        profissionais_salvos = 0
        
        try:
            with db.get_session() as session:
                for prof_data in profissionais:
                    profissional_id = str(prof_data.get('id'))
                    if not profissional_id:
                        continue
                    
                    nome = prof_data.get('nome', 'Sem nome')
                    dados_originais = prof_data.get('dados_originais', prof_data)
                    
                    # Busca ou cria profissional
                    profissional = session.query(Profissional).filter_by(profissional_id=profissional_id).first()
                    
                    if profissional:
                        # Atualiza profissional existente
                        profissional.nome = nome
                        profissional.ativo = True
                        profissional.dados_originais = dados_originais
                        profissional.updated_at = timestamp
                    else:
                        # Cria novo profissional
                        profissional = Profissional(
                            profissional_id=profissional_id,
                            nome=nome,
                            ativo=True,
                            dados_originais=dados_originais
                        )
                        session.add(profissional)
                    
                    profissionais_salvos += 1
                
                # Marca profissionais que não foram atualizados como inativos
                profissionais_ids_atualizados = {str(p.get('id')) for p in profissionais if p.get('id')}
                profissionais_antigos = session.query(Profissional).filter_by(ativo=True).all()
                for prof_antigo in profissionais_antigos:
                    if prof_antigo.profissional_id not in profissionais_ids_atualizados:
                        prof_antigo.ativo = False
                        logger.debug(f"Profissional {prof_antigo.nome} marcado como inativo")
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Erro ao salvar profissionais no banco: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return profissionais_salvos
    
    def _registrar_historico(self, timestamp: datetime, total_eventos: int, 
                            eventos_ocupados: int, eventos_livres: int, 
                            total_profissionais: int = 0,
                            sucesso: bool = True, erro: Optional[str] = None):
        """Registra histórico de sincronização"""
        db = get_db()
        if not db.is_connected():
            return
        
        try:
            with db.get_session() as session:
                historico = SyncHistory(
                    timestamp=timestamp,
                    data_inicio=datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0),
                    data_fim=(datetime.now(self.timezone_brasil) + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0),
                    total_eventos=total_eventos,
                    eventos_ocupados=eventos_ocupados,
                    eventos_livres=eventos_livres,
                    total_profissionais=total_profissionais,
                    sucesso=sucesso,
                    erro=erro
                )
                session.add(historico)
                session.commit()
        except Exception as e:
            logger.error(f"Erro ao registrar historico: {e}")
    
    def obter_eventos(self, ocupado: Optional[bool] = None, 
                     data_inicio: Optional[datetime] = None,
                     data_fim: Optional[datetime] = None,
                     limit: int = 100) -> List[Dict]:
        """
        Obtém eventos do banco de dados
        
        Args:
            ocupado: Filtrar por ocupado/livre (None = todos)
            data_inicio: Data de início do filtro
            data_fim: Data de fim do filtro
            limit: Limite de resultados
            
        Returns:
            Lista de eventos
        """
        db = get_db()
        if not db.is_connected():
            return []
        
        try:
            with db.get_session() as session:
                query = session.query(AgendaEvent).filter_by(deletado=False)
                
                if ocupado is not None:
                    query = query.filter_by(ocupado=ocupado)
                
                if data_inicio:
                    query = query.filter(AgendaEvent.data >= data_inicio)
                
                if data_fim:
                    query = query.filter(AgendaEvent.data <= data_fim)
                
                eventos = query.order_by(AgendaEvent.data).limit(limit).all()
                
                return [evento.to_dict() for evento in eventos]
                
        except Exception as e:
            logger.error(f"Erro ao obter eventos: {e}")
            return []
    
    def obter_estatisticas(self) -> Dict:
        """Obtém estatísticas da agenda"""
        db = get_db()
        logger.info(f"🔌 Status do banco de dados (estatisticas): conectado={db.is_connected()}")
        if not db.is_connected():
            logger.error("❌ Banco de dados nao conectado. Retornando estatisticas vazias.")
            logger.error(f"   DATABASE_URL configurada: {bool(db.database_url if hasattr(db, 'database_url') else None)}")
            logger.error(f"   Engine existe: {db.engine is not None if hasattr(db, 'engine') else 'N/A'}")
            logger.error(f"   Session existe: {db.Session is not None if hasattr(db, 'Session') else 'N/A'}")
            return {}
        
        try:
            with db.get_session() as session:
                # Estatísticas gerais
                total = session.query(AgendaEvent).filter_by(deletado=False).count()
                ocupados = session.query(AgendaEvent).filter_by(ocupado=True, deletado=False).count()
                livres = session.query(AgendaEvent).filter_by(ocupado=False, deletado=False).count()
                
                # Estatísticas por profissional
                profissionais_ativos = session.query(Profissional).filter_by(ativo=True).count()
                
                # Eventos por profissional
                eventos_por_profissional = {}
                eventos_com_profissional = session.query(AgendaEvent).filter(
                    AgendaEvent.deletado == False,
                    AgendaEvent.dentista_id.isnot(None)
                ).all()
                
                for evento in eventos_com_profissional:
                    dentista_id = evento.dentista_id
                    if dentista_id:
                        if dentista_id not in eventos_por_profissional:
                            eventos_por_profissional[dentista_id] = {'ocupados': 0, 'livres': 0}
                        if evento.ocupado:
                            eventos_por_profissional[dentista_id]['ocupados'] += 1
                        else:
                            eventos_por_profissional[dentista_id]['livres'] += 1
                
                # Última sincronização
                ultima_sync = session.query(SyncHistory).order_by(SyncHistory.timestamp.desc()).first()
                
                # Próximos eventos (próximos 7 dias)
                hoje = datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0)
                proximos_7_dias = hoje + timedelta(days=7)
                
                eventos_proximos = session.query(AgendaEvent).filter(
                    AgendaEvent.deletado == False,
                    AgendaEvent.data >= hoje,
                    AgendaEvent.data <= proximos_7_dias
                ).count()
                
                eventos_proximos_ocupados = session.query(AgendaEvent).filter(
                    AgendaEvent.deletado == False,
                    AgendaEvent.ocupado == True,
                    AgendaEvent.data >= hoje,
                    AgendaEvent.data <= proximos_7_dias
                ).count()
                
                return {
                    'total_eventos': total,
                    'eventos_ocupados': ocupados,
                    'eventos_livres': livres,
                    'taxa_ocupacao': round((ocupados / total * 100) if total > 0 else 0, 2),
                    'total_profissionais_ativos': profissionais_ativos,
                    'eventos_por_profissional': eventos_por_profissional,
                    'proximos_7_dias': {
                        'total_eventos': eventos_proximos,
                        'eventos_ocupados': eventos_proximos_ocupados,
                        'eventos_disponiveis': eventos_proximos - eventos_proximos_ocupados
                    },
                    'ultima_sincronizacao': {
                        'timestamp': ultima_sync.timestamp.isoformat() if ultima_sync else None,
                        'sucesso': ultima_sync.sucesso if ultima_sync else None,
                        'total_eventos': ultima_sync.total_eventos if ultima_sync else None,
                        'total_profissionais': ultima_sync.total_profissionais if ultima_sync else None,
                        'erro': ultima_sync.erro if ultima_sync and ultima_sync.erro else None
                    }
                }
        except Exception as e:
            logger.error(f"Erro ao obter estatisticas: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {}
    
    def obter_agendas_disponiveis(self, data: datetime, hora_inicio: int = 9, hora_fim: int = 18, profissional_id: Optional[str] = None) -> List[Dict]:
        """
        Obtém agendas disponíveis (livres) para um dia específico dentro da janela de horário.
        Gera slots de 30 minutos e retorna os que não têm eventos ocupados.
        
        Args:
            data: Data para buscar (datetime) - apenas a data será usada, hora será ignorada
            hora_inicio: Hora de início (padrão: 9)
            hora_fim: Hora de fim (padrão: 18)
            
        Returns:
            Lista de slots disponíveis de 30 minutos ordenados por horário
        """
        db = get_db()
        logger.info(f"🔌 Status do banco de dados: conectado={db.is_connected()}")
        if not db.is_connected():
            logger.error("❌ Banco de dados nao conectado. Retornando lista vazia.")
            return []
        
        try:
            # Normaliza a data para o início do dia (ignora hora)
            data_normalizada = data.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Verifica se é hoje para filtrar horários passados
            agora = datetime.now(self.timezone_brasil)
            hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            eh_hoje = data_normalizada.date() == hoje.date()
            hora_atual_sistema = agora.hour
            minuto_atual_sistema = agora.minute
            
            # Calcula o próximo slot de 30 minutos a partir de agora
            if eh_hoje:
                # Arredonda para o próximo slot de 30 minutos
                proximo_slot_minuto = ((minuto_atual_sistema // 30) + 1) * 30
                proximo_slot_hora = hora_atual_sistema
                if proximo_slot_minuto >= 60:
                    proximo_slot_minuto = 0
                    proximo_slot_hora += 1
            else:
                proximo_slot_hora = hora_inicio
                proximo_slot_minuto = 0
            
            logger.info(f"🔍 Buscando slots disponiveis - Data: {data.strftime('%Y-%m-%d')}, Horario: {hora_inicio}h-{hora_fim}h")
            if eh_hoje:
                logger.info(f"⏰ É hoje - filtrando horarios passados. Hora atual: {hora_atual_sistema}:{minuto_atual_sistema:02d}, Proximo slot: {proximo_slot_hora}:{proximo_slot_minuto:02d}")
            
            with db.get_session() as session:
                # Busca TODOS os eventos ocupados do dia (não deletados)
                inicio_dia = data_normalizada
                fim_dia = data_normalizada.replace(hour=23, minute=59, second=59)
                
                # Busca eventos ocupados, filtrando por profissional se fornecido
                query_ocupados = session.query(AgendaEvent).filter(
                    AgendaEvent.deletado == False,
                    AgendaEvent.ocupado == True,
                    AgendaEvent.data >= inicio_dia,
                    AgendaEvent.data <= fim_dia
                )
                
                if profissional_id:
                    query_ocupados = query_ocupados.filter(AgendaEvent.dentista_id == str(profissional_id))
                    logger.info(f"🔍 Filtrando por profissional ID: {profissional_id}")
                    # Log para debug: mostra alguns dentista_ids dos eventos para verificar correspondência
                    eventos_debug = session.query(AgendaEvent.dentista_id).filter(
                        AgendaEvent.deletado == False,
                        AgendaEvent.ocupado == True,
                        AgendaEvent.data >= inicio_dia,
                        AgendaEvent.data <= fim_dia
                    ).distinct().limit(5).all()
                    logger.debug(f"   IDs de dentistas encontrados nos eventos: {[str(e[0]) for e in eventos_debug if e[0]]}")
                
                eventos_ocupados = query_ocupados.all()
                
                logger.info(f"📊 Eventos ocupados encontrados no dia: {len(eventos_ocupados)}")
                if len(eventos_ocupados) == 0 and profissional_id:
                    logger.warning(f"⚠️ Nenhum evento ocupado encontrado para profissional {profissional_id} em {data.strftime('%Y-%m-%d')}")
                
                # Cria conjunto de slots ocupados (hora, minuto) de 30 em 30 minutos
                slots_ocupados = set()
                for evento in eventos_ocupados:
                    evento_data = evento.data
                    if evento_data:
                        if evento_data.tzinfo:
                            evento_data = evento_data.replace(tzinfo=None)
                        
                        # Verifica se é do mesmo dia
                        if evento_data.date() != data_normalizada.date():
                            continue
                        
                        # Extrai hora e minuto de início e fim do evento
                        hora_inicio_evento = evento_data.hour
                        minuto_inicio_evento = evento_data.minute
                        
                        # Tenta obter hora de fim do evento
                        hora_fim_evento = hora_inicio_evento
                        minuto_fim_evento = minuto_inicio_evento + 30  # Padrão: 30 minutos
                        
                        if evento.hora_fim:
                            try:
                                partes_fim = str(evento.hora_fim).split(':')
                                if len(partes_fim) >= 2:
                                    hora_fim_evento = int(partes_fim[0])
                                    minuto_fim_evento = int(partes_fim[1])
                            except:
                                pass
                        
                        # Adiciona todos os slots de 30 minutos ocupados por este evento
                        hora_atual = hora_inicio_evento
                        minuto_atual = (minuto_inicio_evento // 30) * 30  # Arredonda para 0 ou 30
                        
                        while hora_atual < hora_fim_evento or (hora_atual == hora_fim_evento and minuto_atual < minuto_fim_evento):
                            if hora_atual >= hora_inicio and hora_atual < hora_fim:
                                slots_ocupados.add((hora_atual, minuto_atual))
                            
                            # Avança 30 minutos
                            minuto_atual += 30
                            if minuto_atual >= 60:
                                minuto_atual = 0
                                hora_atual += 1
                
                logger.info(f"⏰ Slots ocupados identificados: {len(slots_ocupados)}")
                
                # Gera todos os slots de 30 minutos possíveis entre hora_inicio e hora_fim
                # IMPORTANTE: O slot não pode ultrapassar hora_fim (ex: último slot é 17:30-18:00, não 18:00-18:30)
                slots_disponiveis = []
                hora_slot = hora_inicio
                minuto_slot = 0
                
                while hora_slot < hora_fim:
                    # Se for hoje, verifica se o horário já passou
                    if eh_hoje:
                        # Verifica se o slot já passou (deve ser >= próximo slot)
                        slot_passou = False
                        if hora_slot < proximo_slot_hora:
                            slot_passou = True
                        elif hora_slot == proximo_slot_hora:
                            # Mesma hora, verifica minutos
                            if minuto_slot < proximo_slot_minuto:
                                slot_passou = True
                        
                        if slot_passou:
                            # Slot já passou, avança
                            minuto_slot += 30
                            if minuto_slot >= 60:
                                minuto_slot = 0
                                hora_slot += 1
                            continue
                    
                    # Verifica se o slot não ultrapassa hora_fim
                    hora_fim_slot = hora_slot
                    minuto_fim_slot = minuto_slot + 30
                    if minuto_fim_slot >= 60:
                        minuto_fim_slot = 0
                        hora_fim_slot += 1
                    
                    # Se o fim do slot ultrapassar hora_fim, para aqui
                    if hora_fim_slot > hora_fim or (hora_fim_slot == hora_fim and minuto_fim_slot > 0):
                        break
                    
                    # Verifica se este slot não está ocupado
                    if (hora_slot, minuto_slot) not in slots_ocupados:
                        # Formata hora início
                        hora_inicio_str = f"{hora_slot}:{minuto_slot:02d}"
                        
                        # Formata hora fim
                        hora_fim_str = f"{hora_fim_slot}:{minuto_fim_slot:02d}"
                        
                        # Retorna apenas os horários disponíveis
                        slots_disponiveis.append({
                            'hora_inicio': hora_inicio_str,
                            'hora_fim': hora_fim_str
                        })
                    
                    # Avança 30 minutos
                    minuto_slot += 30
                    if minuto_slot >= 60:
                        minuto_slot = 0
                        hora_slot += 1
                
                logger.info(f"✅ Resultado final: {len(slots_disponiveis)} slots disponiveis de 30min para {data.strftime('%Y-%m-%d')} entre {hora_inicio}h e {hora_fim}h")
                
                return slots_disponiveis
                
        except Exception as e:
            logger.error(f"Erro ao obter agendas disponiveis: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def listar_profissionais_com_agendas(
        self,
        data: Optional[datetime] = None,
        hora_inicio: int = 9,
        hora_fim: int = 18,
        usar_cache: bool = True,
        dias_futuros: int = 3
    ) -> List[Dict]:
        """
        Lista profissionais com suas agendas disponíveis para múltiplos dias
        
        Args:
            data: Data inicial para buscar agendas (usa hoje se None)
            hora_inicio: Hora de início (padrão: 9)
            hora_fim: Hora de fim (padrão: 18)
            usar_cache: Se True, busca profissionais do banco primeiro
            dias_futuros: Número de dias futuros para buscar (padrão: 3)
        
        Returns:
            Lista de profissionais com suas agendas disponíveis por dia
        """
        try:
            if data is None:
                data = datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Busca profissionais
            profissionais = self.listar_profissionais(usar_cache=usar_cache)
            
            # Para cada profissional, busca suas agendas disponíveis para cada dia
            profissionais_com_agendas = []
            for profissional in profissionais:
                # IMPORTANTE: Usa profissional_id (ID da API Clinicorp) não id (ID do banco local)
                # Quando vem do banco, tem 'profissional_id' (ID da API) e 'id' (ID do banco)
                # Quando vem da API, tem 'id' (ID da API)
                profissional_id_api = profissional.get('profissional_id') or profissional.get('id')
                profissional_nome = profissional.get('nome', '')
                
                if not profissional_id_api:
                    logger.warning(f"Profissional sem ID válido: {profissional}")
                    continue
                
                logger.debug(f"Buscando agendas para profissional {profissional_nome} (ID API: {profissional_id_api})")
                
                # Busca agendas para cada dia usando o ID da API Clinicorp
                agendas_por_dia = []
                for dia_offset in range(dias_futuros):
                    data_atual = data + timedelta(days=dia_offset)
                    
                    # Busca agendas disponíveis deste profissional para este dia
                    # Usa profissional_id_api (ID da API Clinicorp) para filtrar eventos
                    agendas = self.obter_agendas_disponiveis(
                        data=data_atual,
                        hora_inicio=hora_inicio,
                        hora_fim=hora_fim,
                        profissional_id=str(profissional_id_api)
                    )
                    
                    # Adiciona mesmo se não houver agendas (para mostrar que o profissional existe)
                    agendas_por_dia.append({
                        'data': data_atual.strftime('%Y-%m-%d'),
                        'total_disponiveis': len(agendas),
                        'agendas': agendas
                    })
                
                # Adiciona profissional sempre (mesmo sem agendas disponíveis)
                profissionais_com_agendas.append({
                    'id': str(profissional_id_api),  # Retorna ID da API Clinicorp
                    'nome': profissional_nome,
                    'total_dias_com_disponibilidade': len([d for d in agendas_por_dia if d['total_disponiveis'] > 0]),
                    'agendas_por_dia': agendas_por_dia
                })
            
            logger.info(f"📋 Retornando {len(profissionais_com_agendas)} profissionais com suas agendas para {dias_futuros} dias")
            return profissionais_com_agendas
            
        except Exception as e:
            logger.error(f"Erro ao listar profissionais com agendas: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def listar_profissionais(self, usar_cache: bool = True, forcar_atualizacao: bool = False) -> List[Dict]:
        """
        Lista profissionais disponíveis na clínica
        
        Args:
            usar_cache: Se True, busca do banco primeiro. Se False ou banco vazio, busca da API
            forcar_atualizacao: Se True, sempre busca da API e atualiza o banco
        
        Returns:
            Lista de profissionais com id e nome
        """
        db = get_db()
        
        # Se forçar atualização, sempre busca da API
        if forcar_atualizacao:
            logger.info("🔄 Forçando atualização de profissionais da API...")
            try:
                profissionais = self.agenda_api.listar_profissionais()
                
                # Salva no banco se conectado
                if db.is_connected() and profissionais:
                    timestamp = datetime.now(self.timezone_brasil)
                    self._salvar_profissionais_no_banco(profissionais, timestamp)
                
                return profissionais
            except Exception as e:
                logger.error(f"Erro ao listar profissionais: {e}")
                return []
        
        # Tenta buscar do banco primeiro se usar_cache
        if usar_cache and db.is_connected():
            try:
                with db.get_session() as session:
                    profissionais_db = session.query(Profissional).filter_by(ativo=True).all()
                    if profissionais_db:
                        # Verifica se há profissionais com nomes incorretos (genéricos ou títulos)
                        profissionais_com_nomes_ruins = [
                            p for p in profissionais_db 
                            if p.nome.startswith('Profissional ') or 
                               p.nome.lower() in ['folga', 'niver bella <3'] or
                               len(p.nome.strip()) < 3
                        ]
                        
                        if profissionais_com_nomes_ruins:
                            logger.warning(f"⚠️ Encontrados {len(profissionais_com_nomes_ruins)} profissionais com nomes incorretos. Buscando atualização da API...")
                            # Busca da API para atualizar
                            profissionais_api = self.agenda_api.listar_profissionais()
                            if profissionais_api:
                                timestamp = datetime.now(self.timezone_brasil)
                                self._salvar_profissionais_no_banco(profissionais_api, timestamp)
                                # Busca novamente do banco atualizado
                                profissionais_db = session.query(Profissional).filter_by(ativo=True).all()
                        
                        logger.info(f"📋 Retornando {len(profissionais_db)} profissionais do banco de dados")
                        return [prof.to_dict() for prof in profissionais_db]
            except Exception as e:
                logger.warning(f"Erro ao buscar profissionais do banco: {e}")
        
        # Se não encontrou no banco, busca da API
        try:
            logger.info("Buscando profissionais da API...")
            profissionais = self.agenda_api.listar_profissionais()
            
            # Salva no banco se conectado
            if db.is_connected() and profissionais:
                timestamp = datetime.now(self.timezone_brasil)
                self._salvar_profissionais_no_banco(profissionais, timestamp)
            
            return profissionais
        except Exception as e:
            logger.error(f"Erro ao listar profissionais: {e}")
            return []
    
    def criar_agendamento(
        self,
        paciente_id: str,
        profissional_id: str,
        data: datetime,
        hora_inicio: str,
        hora_fim: str,
        observacoes: str = "",
        procedimentos: List[str] = None,
        telefone: str = "",
        email: str = ""
    ) -> Dict:
        """
        Cria um novo agendamento no Clinicorp
        
        Args:
            paciente_id: ID do paciente
            profissional_id: ID do profissional/dentista
            data: Data do agendamento (datetime)
            hora_inicio: Hora de início (formato "HH:MM")
            hora_fim: Hora de fim (formato "HH:MM")
            observacoes: Observações do agendamento
            procedimentos: Lista de procedimentos
            telefone: Telefone do paciente
            email: Email do paciente
            
        Returns:
            Dicionário com resultado do agendamento
        """
        try:
            return self.agenda_api.criar_agendamento(
                paciente_id=paciente_id,
                profissional_id=profissional_id,
                data=data,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                observacoes=observacoes,
                procedimentos=procedimentos,
                telefone=telefone,
                email=email
            )
        except Exception as e:
            logger.error(f"Erro ao criar agendamento: {e}")
            return {
                'sucesso': False,
                'erro': str(e)
            }


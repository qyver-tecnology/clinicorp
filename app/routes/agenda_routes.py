"""
Rotas da API de agenda
"""
from flask import jsonify, request
from datetime import datetime
from app.routes import api_bp
from app.services.agenda_service import AgendaService
import pytz
import logging

logger = logging.getLogger(__name__)

agenda_service = AgendaService()
timezone_brasil = pytz.timezone('America/Sao_Paulo')


def _parse_hora_param(value: str, default: int) -> int:
    """Converte parâmetros de hora que podem vir como '10' ou '10:00'."""
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        try:
            return int(str(value).split(':')[0])
        except Exception:
            return default

@api_bp.route('/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    return jsonify({
        'status': 'ok',
        'service': 'clinicorp-agenda-sync'
    })

@api_bp.route('/agenda/sync', methods=['POST'])
def sync_agenda():
    """Força uma sincronização manual da agenda"""
    try:
        resultado = agenda_service.sincronizar_agenda()
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/agenda/eventos', methods=['GET'])
def get_eventos():
    """Obtém eventos da agenda"""
    try:
        # Parâmetros de filtro
        ocupado = request.args.get('ocupado')
        if ocupado is not None:
            ocupado = ocupado.lower() == 'true'
        
        data_inicio = request.args.get('data_inicio')
        if data_inicio:
            data_inicio = datetime.fromisoformat(data_inicio)
        
        data_fim = request.args.get('data_fim')
        if data_fim:
            data_fim = datetime.fromisoformat(data_fim)
        
        limit = int(request.args.get('limit', 100))
        
        eventos = agenda_service.obter_eventos(
            ocupado=ocupado,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limit=limit
        )
        
        return jsonify({
            'total': len(eventos),
            'eventos': eventos
        }), 200
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/agenda/estatisticas', methods=['GET'])
def get_estatisticas():
    """Obtém estatísticas da agenda"""
    try:
        stats = agenda_service.obter_estatisticas()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/agenda/disponiveis', methods=['GET'])
def get_agendas_disponiveis():
    """
    Busca agendas disponíveis (livres) dentro da janela de 9h-18h para um dia específico
    
    Query params:
        data: Data no formato YYYY-MM-DD (obrigatório)
        hora_inicio: Hora de início (padrão: 9)
        hora_fim: Hora de fim (padrão: 18)
        profissional_id: ID do profissional para filtrar (opcional)
    """
    try:
        data_str = request.args.get('data')
        if not data_str:
            return jsonify({'erro': 'Parametro "data" e obrigatorio (formato: YYYY-MM-DD)'}), 400
        
        try:
            data = datetime.strptime(data_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'erro': 'Formato de data invalido. Use YYYY-MM-DD'}), 400
        
        hora_inicio = _parse_hora_param(request.args.get('hora_inicio'), 9)
        hora_fim = _parse_hora_param(request.args.get('hora_fim'), 18)
        profissional_id = request.args.get('profissional_id')
        
        # Busca agendas disponíveis
        agendas = agenda_service.obter_agendas_disponiveis(
            data=data,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            profissional_id=profissional_id
        )
        
        return jsonify({
            'data': data_str,
            'hora_inicio': hora_inicio,
            'hora_fim': hora_fim,
            'profissional_id': profissional_id,
            'total_disponiveis': len(agendas),
            'agendas': agendas
        }), 200
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/agenda/profissionais', methods=['GET'])
def get_profissionais():
    """
    Lista profissionais disponíveis na clínica
    
    Query params:
        usar_cache: Se true, busca do banco primeiro (padrão: true)
        forcar_atualizacao: Se true, sempre busca da API e atualiza o banco (padrão: false)
        com_agendas: Se true, retorna profissionais com suas agendas disponíveis (padrão: false)
        data: Data inicial para buscar agendas quando com_agendas=true (formato YYYY-MM-DD, padrão: hoje)
        dias_futuros: Número de dias futuros para buscar agendas (padrão: 3)
        hora_inicio: Hora de início para agendas (padrão: 9)
        hora_fim: Hora de fim para agendas (padrão: 18)
    """
    try:
        usar_cache = request.args.get('usar_cache', 'true').lower() == 'true'
        forcar_atualizacao = request.args.get('forcar_atualizacao', 'false').lower() == 'true'
        com_agendas = request.args.get('com_agendas', 'false').lower() == 'true'
        
        if com_agendas:
            # Retorna profissionais com suas agendas
            data_str = request.args.get('data')
            if data_str:
                try:
                    data = datetime.strptime(data_str, '%Y-%m-%d')
                except ValueError:
                    return jsonify({'erro': 'Formato de data invalido. Use YYYY-MM-DD'}), 400
            else:
                data = datetime.now(timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0)
            
            hora_inicio = _parse_hora_param(request.args.get('hora_inicio'), 9)
            hora_fim = _parse_hora_param(request.args.get('hora_fim'), 18)
            dias_futuros = int(request.args.get('dias_futuros', 3))
            
            profissionais_com_agendas = agenda_service.listar_profissionais_com_agendas(
                data=data,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                usar_cache=usar_cache and not forcar_atualizacao,
                dias_futuros=dias_futuros
            )
            
            return jsonify({
                'data_inicio': data.strftime('%Y-%m-%d'),
                'dias_futuros': dias_futuros,
                'hora_inicio': hora_inicio,
                'hora_fim': hora_fim,
                'total': len(profissionais_com_agendas),
                'profissionais': profissionais_com_agendas
            }), 200
        else:
            # Retorna apenas lista de profissionais
            profissionais = agenda_service.listar_profissionais(
                usar_cache=usar_cache and not forcar_atualizacao,
                forcar_atualizacao=forcar_atualizacao
            )
            
            # Formata para retornar apenas id e nome
            profissionais_formatados = [
                {
                    'id': p.get('id') or p.get('profissional_id'),
                    'nome': p.get('nome', '')
                }
                for p in profissionais
            ]
            
            return jsonify({
                'total': len(profissionais_formatados),
                'profissionais': profissionais_formatados
            }), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/agenda/criar', methods=['POST'])
def criar_agendamento():
    """
    Cria um novo agendamento no Clinicorp
    
    Se paciente_id não for fornecido, o sistema buscará o nome do paciente
    pelo telefone e criará um novo paciente automaticamente no Clinicorp.
    
    Body JSON:
        paciente_id: ID do paciente (opcional - se não fornecido, cria novo paciente)
        profissional_id: ID do profissional (obrigatório)
        data: Data no formato YYYY-MM-DD (obrigatório)
        hora_inicio: Hora de início no formato HH:MM (obrigatório)
        hora_fim: Hora de fim no formato HH:MM (obrigatório)
        observacoes: Observações (opcional)
        procedimentos: Lista de procedimentos (opcional)
        telefone: Telefone do paciente (obrigatório se paciente_id não for fornecido)
        email: Email do paciente (opcional)
        nome_paciente: Nome do paciente (opcional - busca do banco se não fornecido)
    """
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Body JSON e obrigatorio'}), 400
        
        # Valida campos obrigatórios
        paciente_id = dados.get('paciente_id')
        telefone = dados.get('telefone', '').strip()
        profissional_id = dados.get('profissional_id')
        data_str = dados.get('data')
        hora_inicio = dados.get('hora_inicio')
        hora_fim = dados.get('hora_fim')
        nome_paciente = dados.get('nome_paciente', '').strip()
        
        if not profissional_id:
            return jsonify({'erro': 'Campo "profissional_id" e obrigatorio'}), 400
        if not data_str:
            return jsonify({'erro': 'Campo "data" e obrigatorio (formato: YYYY-MM-DD)'}), 400
        if not hora_inicio:
            return jsonify({'erro': 'Campo "hora_inicio" e obrigatorio (formato: HH:MM)'}), 400
        if not hora_fim:
            return jsonify({'erro': 'Campo "hora_fim" e obrigatorio (formato: HH:MM)'}), 400
        
        # Se não tem paciente_id, precisa de telefone para buscar/criar paciente
        if not paciente_id:
            if not telefone:
                return jsonify({
                    'erro': 'Campo "telefone" e obrigatorio quando paciente_id nao e fornecido',
                    'detalhes': 'Para criar um novo paciente, informe o telefone.'
                }), 400
            
            # Se não tem nome_paciente no request, busca do banco pelo telefone
            if not nome_paciente:
                nome_paciente = _buscar_nome_paciente_por_telefone(telefone)
            
            if not nome_paciente:
                return jsonify({
                    'erro': 'Nome do paciente nao encontrado',
                    'detalhes': 'O nome do paciente deve ser coletado antes de criar o agendamento. Use a ferramenta Salvar_nome_paciente primeiro.',
                    'telefone_informado': telefone
                }), 400
            
            # PASSO 1: Buscar ou criar paciente no Clinicorp (e salvar no banco local)
            logger.info(f"🔍 Buscando/criando paciente no Clinicorp: {nome_paciente} ({telefone})")
            paciente = agenda_service.buscar_ou_criar_paciente(
                nome=nome_paciente,
                telefone=telefone,
                email=dados.get('email', '')
            )
            
            if not paciente or not paciente.get('id'):
                return jsonify({
                    'erro': 'Falha ao criar paciente no Clinicorp',
                    'detalhes': 'Nao foi possivel criar o paciente no sistema. Tente novamente.',
                    'nome': nome_paciente,
                    'telefone': telefone
                }), 400
            
            # Usa o ID do paciente do Clinicorp
            paciente_id = str(paciente['id'])
            logger.info(f"✅ Paciente pronto para agendamento: {paciente.get('nome')} (ID: {paciente_id})")
        
        # PASSO 2: Criar agendamento (agora sempre com paciente_id válido)
        logger.info(f"📅 Criando agendamento para paciente ID: {paciente_id}")
        
        # Converte data
        try:
            data = datetime.strptime(data_str, '%Y-%m-%d')
            # Adiciona hora e minuto da hora_inicio
            hora_parts = hora_inicio.split(':')
            if len(hora_parts) >= 2:
                data = data.replace(hour=int(hora_parts[0]), minute=int(hora_parts[1]))
            # Localiza no timezone de Brasília
            data = timezone_brasil.localize(data)
        except ValueError as e:
            return jsonify({'erro': f'Formato de data invalido: {e}'}), 400
        
        # Cria agendamento
        resultado = agenda_service.criar_agendamento(
            paciente_id=str(paciente_id) if paciente_id else None,
            profissional_id=str(profissional_id),
            data=data,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            observacoes=dados.get('observacoes', ''),
            procedimentos=dados.get('procedimentos', []),
            telefone=telefone,
            email=dados.get('email', ''),
            nome_paciente=nome_paciente
        )
        
        if resultado.get('sucesso'):
            return jsonify(resultado), 201
        else:
            return jsonify(resultado), 400
        
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {e}")
        return jsonify({'erro': str(e)}), 500


def _extrair_nome_completo(mensagem: str) -> str:
    """
    Extrai o nome completo de uma mensagem como "meu nome é Gustavo Prezzoti"
    
    Args:
        mensagem: Mensagem do cliente
        
    Returns:
        Nome completo extraído ou string vazia
    """
    import re
    
    # Padrões comuns para extração de nome
    padroes = [
        r'(?:me\s+chamo|meu\s+nome\s+[ée]|sou\s+(?:o|a)?)\s*[\s:]+([A-Za-zÀ-ÖØ-öø-ÿ\s]+)',  # "me chamo João Silva", "meu nome é Maria Santos"
        r'(?:nome|nome\s+completo)\s*[\s:]+([A-Za-zÀ-ÖØ-öø-ÿ\s]+)',  # "nome: Pedro Souza", "nome completo: Ana Lima"
        r'([A-Za-zÀ-ÖØ-öø-ÿ]{2,}\s+[A-Za-zÀ-ÖØ-öø-ÿ]{2,}(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ]{2,})*)' # "João Silva", "Maria Santos Lima"
    ]
    
    for padrao in padroes:
        match = re.search(padrao, mensagem, re.IGNORECASE)
        if match:
            nome_extraido = match.group(1).strip()
            # Remove pontuação no final
            nome_extraido = re.sub(r'[.,!?;:]$', '', nome_extraido)
            return nome_extraido
    
    return ""

def _buscar_nome_paciente_por_telefone(telefone: str) -> str:
    """
    Busca o nome do paciente no banco de dados pelo telefone
    
    Args:
        telefone: Telefone do paciente
        
    Returns:
        Nome do paciente ou string vazia se não encontrado
    """
    try:
        from app.database import get_db
        db = get_db()
        
        if not db.is_connected():
            logger.warning("Banco de dados nao conectado. Nao foi possivel buscar nome do paciente.")
            return ""
        
        with db.get_session() as session:
            from sqlalchemy import text
            
            query = text("""
                SELECT content, metadata 
                FROM documents 
                WHERE metadata->>'telefone' = :telefone 
                AND metadata->>'tipo' = 'paciente_info'
                LIMIT 1
            """)
            result = session.execute(query, {'telefone': telefone}).fetchone()
            
            if result:
                # content contém o nome, ou busca do metadata
                nome = result[0] or (result[1].get('nome', '') if result[1] else '')
                if nome:
                    logger.info(f"Nome do paciente encontrado para telefone {telefone}: {nome}")
                    return nome
            
            logger.warning(f"Nome do paciente nao encontrado para telefone: {telefone}")
            return ""
            
    except Exception as e:
        logger.error(f"Erro ao buscar nome do paciente: {e}")
        return ""

@api_bp.route('/paciente/buscar-clinicorp', methods=['GET'])
def buscar_paciente_clinicorp():
    """
    Busca paciente na API do Clinicorp pelo telefone
    
    Query params:
        telefone: Telefone do paciente (obrigatório)
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        
        if not telefone:
            return jsonify({'erro': 'Parametro "telefone" e obrigatorio'}), 400
        
        # Busca na API do Clinicorp
        paciente = agenda_service.agenda_api.buscar_paciente_por_telefone(telefone)
        
        if paciente:
            return jsonify({
                'encontrado': True,
                'paciente': paciente
            }), 200
        else:
            return jsonify({
                'encontrado': False,
                'telefone': telefone,
                'mensagem': 'Paciente nao encontrado no Clinicorp'
            }), 200
            
    except Exception as e:
        logger.error(f"Erro ao buscar paciente no Clinicorp: {e}")
        return jsonify({'erro': str(e)}), 500


@api_bp.route('/paciente/criar', methods=['POST'])
def criar_paciente():
    """
    Cria um novo paciente no Clinicorp e salva no banco local.
    Se o paciente já existir (pelo telefone), retorna os dados dele.
    
    Body JSON:
        telefone: Telefone do paciente (obrigatório)
        nome: Nome completo do paciente (obrigatório)
        email: Email do paciente (opcional)
    
    Returns:
        Dados do paciente (existente ou recém-criado)
    """
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Body JSON e obrigatorio'}), 400
        
        telefone = dados.get('telefone', '').strip()
        nome = dados.get('nome', '').strip()
        email = dados.get('email', '').strip()
        
        if not telefone:
            return jsonify({'erro': 'Campo "telefone" e obrigatorio'}), 400
        if not nome:
            return jsonify({'erro': 'Campo "nome" e obrigatorio'}), 400
        
        logger.info(f"🔍 Buscando/criando paciente: {nome} ({telefone})")
        
        # Busca ou cria paciente no Clinicorp (e salva no banco local)
        paciente = agenda_service.buscar_ou_criar_paciente(
            nome=nome,
            telefone=telefone,
            email=email
        )
        
        if paciente and paciente.get('id'):
            return jsonify({
                'sucesso': True,
                'paciente': paciente,
                'mensagem': 'Paciente pronto para agendamento'
            }), 200
        else:
            return jsonify({
                'sucesso': False,
                'erro': 'Falha ao criar paciente no Clinicorp',
                'nome': nome,
                'telefone': telefone
            }), 400
            
    except Exception as e:
        logger.error(f"Erro ao criar paciente: {e}")
        return jsonify({'erro': str(e)}), 500


@api_bp.route('/paciente/salvar-nome', methods=['POST'])
def salvar_nome_paciente():
    """
    Salva ou atualiza o nome do paciente associado ao telefone
    
    Body JSON:
        telefone: Telefone do paciente (obrigatório)
        nome: Nome completo do paciente (obrigatório)
        mensagem: Mensagem original (opcional - para extrair nome completo)
    """
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Body JSON e obrigatorio'}), 400
        
        telefone = dados.get('telefone', '').strip()
        nome = dados.get('nome', '').strip()
        mensagem = dados.get('mensagem', '').strip()
        
        if not telefone:
            return jsonify({'erro': 'Campo "telefone" e obrigatorio'}), 400
        if not nome:
            return jsonify({'erro': 'Campo "nome" e obrigatorio'}), 400
        
        if mensagem and len(nome.split()) == 1:
            nome_extraido = _extrair_nome_completo(mensagem)
            if nome_extraido and len(nome_extraido.split()) > 1:
                logger.info(f"Nome completo extraído da mensagem: '{nome_extraido}' (original: '{nome}')")
                nome = nome_extraido
        
        from app.database import get_db
        db = get_db()
        
        if not db.is_connected():
            logger.warning("Banco de dados nao conectado. Nome nao sera salvo.")
            return jsonify({
                'sucesso': False,
                'erro': 'Banco de dados nao conectado',
                'nome': nome,
                'telefone': telefone
            }), 200
        
        try:
            with db.get_session() as session:
                from sqlalchemy import text
                
                # Busca documento existente para este telefone
                query = text("""
                    SELECT id, content, metadata 
                    FROM documents 
                    WHERE metadata->>'telefone' = :telefone 
                    AND metadata->>'tipo' = 'paciente_info'
                    LIMIT 1
                """)
                result = session.execute(query, {'telefone': telefone}).fetchone()
                
                if result:
                    # Atualiza documento existente
                    doc_id = result[0]
                    update_query = text("""
                        UPDATE documents 
                        SET content = :nome,
                            metadata = jsonb_set(
                                COALESCE(metadata, '{}'::jsonb),
                                '{nome}',
                                to_jsonb(:nome::text)
                            ),
                            created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                        WHERE id = :doc_id
                    """)
                    session.execute(update_query, {'nome': nome, 'doc_id': doc_id})
                    logger.info(f"✅ Nome atualizado para telefone {telefone}: {nome}")
                else:
                    # Cria novo documento
                    insert_query = text("""
                        INSERT INTO documents (content, metadata)
                        VALUES (
                            :nome,
                            jsonb_build_object(
                                'telefone', :telefone,
                                'nome', :nome,
                                'tipo', 'paciente_info'
                            )
                        )
                    """)
                    session.execute(insert_query, {'nome': nome, 'telefone': telefone})
                    logger.info(f"✅ Nome salvo para telefone {telefone}: {nome}")
                
                session.commit()
        
        except Exception as e:
            logger.error(f"Erro ao salvar nome no banco: {e}")
            return jsonify({
                'sucesso': False,
                'erro': f'Erro ao salvar no banco: {str(e)}',
                'nome': nome,
                'telefone': telefone
            }), 500
        
        return jsonify({
            'sucesso': True,
            'nome': nome,
            'telefone': telefone,
            'mensagem': 'Nome salvo com sucesso'
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao salvar nome do paciente: {e}")
        return jsonify({'erro': str(e)}), 500

@api_bp.route('/paciente/buscar-nome', methods=['GET'])
def buscar_nome_paciente():
    """
    Busca o nome do paciente pelo telefone
    
    Query params:
        telefone: Telefone do paciente (obrigatório)
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        
        if not telefone:
            return jsonify({'erro': 'Parametro "telefone" e obrigatorio'}), 400
        
        from app.database import get_db
        db = get_db()
        
        if not db.is_connected():
            return jsonify({
                'nome': None,
                'telefone': telefone,
                'encontrado': False
            }), 200
        
        try:
            with db.get_session() as session:
                from sqlalchemy import text
                
                query = text("""
                    SELECT content, metadata 
                    FROM documents 
                    WHERE metadata->>'telefone' = :telefone 
                    AND metadata->>'tipo' = 'paciente_info'
                    LIMIT 1
                """)
                result = session.execute(query, {'telefone': telefone}).fetchone()
                
                if result:
                    nome = result[0] or result[1].get('nome', '') if result[1] else ''
                    return jsonify({
                        'nome': nome,
                        'telefone': telefone,
                        'encontrado': True
                    }), 200
                else:
                    return jsonify({
                        'nome': None,
                        'telefone': telefone,
                        'encontrado': False
                    }), 200
        
        except Exception as e:
            logger.error(f"Erro ao buscar nome no banco: {e}")
            return jsonify({
                'nome': None,
                'telefone': telefone,
                'encontrado': False,
                'erro': str(e)
            }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar nome do paciente: {e}")
        return jsonify({'erro': str(e)}), 500


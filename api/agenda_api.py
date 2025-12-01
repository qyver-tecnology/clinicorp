"""
Módulo para buscar agenda do Clinicorp
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz
from clinicorp_client import ClinicorpClient

# Tenta importar do novo config primeiro
try:
    from app.config import Config
    CLINICORP_AGENDA_ENDPOINT = Config.CLINICORP_AGENDA_ENDPOINT
    CLINICORP_CLINIC_ID = Config.CLINICORP_CLINIC_ID
except ImportError:
    # Fallback para config antigo
    from config import CLINICORP_AGENDA_ENDPOINT, CLINICORP_CLINIC_ID

logger = logging.getLogger(__name__)


class AgendaAPI:
    """Classe para buscar e gerenciar agenda do Clinicorp"""
    
    def __init__(self, client: Optional[ClinicorpClient] = None):
        """
        Inicializa a API de agenda
        
        Args:
            client: Cliente Clinicorp (cria novo se None)
        """
        self.client = client or ClinicorpClient()
        self.timezone_brasil = pytz.timezone('America/Sao_Paulo')
    
    def buscar_agenda(
        self, 
        data_inicio: Optional[datetime] = None,
        data_fim: Optional[datetime] = None,
        hora_inicio: int = 9,
        hora_fim: int = 18
    ) -> List[Dict]:
        """
        Busca agenda entre as datas especificadas, filtrando horários entre hora_inicio e hora_fim
        
        Args:
            data_inicio: Data de início (usa hoje se None)
            data_fim: Data de fim (usa 1 mês a partir de hoje se None)
            hora_inicio: Hora inicial do filtro (padrão 9h)
            hora_fim: Hora final do filtro (padrão 18h)
            
        Returns:
            Lista de eventos da agenda
        """
        # Define datas padrão se não fornecidas
        if data_inicio is None:
            data_inicio = datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Garante que está no timezone de Brasília
            if data_inicio.tzinfo is None:
                data_inicio = self.timezone_brasil.localize(data_inicio)
        
        if data_fim is None:
            data_fim = data_inicio + timedelta(days=30)
        else:
            if data_fim.tzinfo is None:
                data_fim = self.timezone_brasil.localize(data_fim)
        
        logger.info(f"Buscando agenda de {data_inicio.date()} até {data_fim.date()} (horário {hora_inicio}h-{hora_fim}h)")
        
        # Endpoint correto da API de agenda do Clinicorp
        endpoint = '/solution/api/appointment/list'
        
        # Obtém clinic_id do token ou usa configurado
        clinic_id = self._obter_clinic_id()
        
        # Formata datas no formato esperado pela API (YYYY-MM-DD)
        params = {
            'from': data_inicio.strftime('%Y-%m-%d'),
            'to': data_fim.strftime('%Y-%m-%d'),
            'clinic_id': clinic_id,
            'canceled': '',
            '__caller': 'AppointmentBook.getAppointments',
            '_AccessPath': '*.Calendar.Use',
            'without_status': 'X',
        }
        
        try:
            logger.debug(f"Buscando agenda em {endpoint} com params: {params}")
            response = self.client.get(endpoint, use_api_url=True, params=params)
            
            if response.status_code == 200:
                try:
                    # Verifica Content-Type
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'json' not in content_type:
                        logger.warning(f"Resposta nao e JSON (Content-Type: {content_type})")
                        logger.debug(f"Resposta: {response.text[:500]}")
                        return []
                    
                    data = response.json()
                    logger.info(f"✅ Agenda obtida com sucesso!")
                    
                    # Processa e filtra os dados
                    eventos = self._processar_resposta_agenda(data, hora_inicio, hora_fim)
                    return eventos
                except ValueError as e:
                    logger.error(f"Erro ao decodificar resposta JSON: {e}")
                    logger.debug(f"Status: {response.status_code}")
                    logger.debug(f"Headers: {dict(response.headers)}")
                    try:
                        resposta_texto = response.text[:1000].encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                        logger.debug(f"Resposta (primeiros 1000 chars): {resposta_texto}")
                    except:
                        logger.debug("Nao foi possivel ler resposta")
                    return []
            else:
                logger.error(f"Erro ao buscar agenda: Status {response.status_code}")
                logger.debug(f"Resposta: {response.text[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"Erro ao buscar agenda: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _obter_clinic_id(self) -> str:
        """
        Obtém o clinic_id da configuração, token JWT ou API
        """
        # Primeiro, tenta usar o configurado
        if CLINICORP_CLINIC_ID:
            return str(CLINICORP_CLINIC_ID)
        
        # Tenta obter do token JWT
        try:
            token = self.client.token_manager.load_token()
            if token and token != "SESSION_ACTIVE":
                import base64
                import json as json_lib
                parts = token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = base64.urlsafe_b64decode(payload)
                    jwt_data = json_lib.loads(decoded)
                    
                    # Procura clinic_id ou NamespaceId no token
                    # O Clinic_BusinessId pode estar em diferentes campos
                    clinic_id = (
                        jwt_data.get('Clinic_BusinessId') or
                        jwt_data.get('clinic_id') or
                        jwt_data.get('ClinicId') or
                        jwt_data.get('NamespaceId') or
                        jwt_data.get('namespaceId')
                    )
                    if clinic_id:
                        logger.info(f"Clinic ID obtido do token: {clinic_id}")
                        return str(clinic_id)
        except Exception as e:
            logger.debug(f"Erro ao extrair clinic_id do token: {e}")
        
        # Se não encontrou no token, tenta buscar da API de usuário
        try:
            response = self.client.get('/security/user/me', use_api_url=True)
            if response.status_code == 200:
                user_data = response.json()
                # Procura em diferentes lugares da resposta
                clinic_id = (
                    user_data.get('clinic_id') or
                    user_data.get('ClinicId') or
                    user_data.get('user', {}).get('clinic_id') or
                    user_data.get('user', {}).get('ClinicId') or
                    user_data.get('user', {}).get('NamespaceId')
                )
                if clinic_id:
                    logger.info(f"Clinic ID obtido da API: {clinic_id}")
                    return str(clinic_id)
        except Exception as e:
            logger.debug(f"Erro ao buscar clinic_id da API: {e}")
        
        # Se ainda não encontrou, usa o padrão do exemplo
        logger.warning("Clinic ID nao encontrado, usando padrao do exemplo. Configure CLINICORP_CLINIC_ID se necessario.")
        return "6556997543657472"  # ID padrão do exemplo
    
    def _obter_user_id(self) -> int:
        """
        Obtém o ID do usuário atual do token JWT
        """
        try:
            token = self.client.token_manager.load_token()
            if token and token != "SESSION_ACTIVE":
                import base64
                import json as json_lib
                parts = token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = base64.urlsafe_b64decode(payload)
                    jwt_data = json_lib.loads(decoded)
                    
                    # Procura user_id no token
                    user_id = (
                        jwt_data.get('id') or
                        jwt_data.get('UserId') or
                        jwt_data.get('userId') or
                        jwt_data.get('CreateUserId')
                    )
                    if user_id:
                        return int(user_id)
        except Exception as e:
            logger.debug(f"Erro ao extrair user_id do token: {e}")
        
        # Se não encontrou, usa padrão do exemplo
        logger.warning("User ID nao encontrado no token, usando padrao")
        return 4942786269347840
    
    def _processar_resposta_agenda(
        self, 
        data: Dict, 
        hora_inicio: int, 
        hora_fim: int
    ) -> List[Dict]:
        """
        Processa a resposta da API e filtra eventos entre hora_inicio e hora_fim
        
        Args:
            data: Dados da resposta da API
            hora_inicio: Hora inicial do filtro
            hora_fim: Hora final do filtro
            
        Returns:
            Lista de eventos processados
        """
        eventos = []
        
        # A API do Clinicorp retorna os dados em 'list'
        dados_agenda = (
            data.get('list') or  # Formato correto da API Clinicorp
            data.get('data') or
            data.get('appointments') or
            data.get('events') or
            (data if isinstance(data, list) else [])
        )
        
        if not isinstance(dados_agenda, list):
            dados_agenda = [dados_agenda] if dados_agenda else []
        
        for evento in dados_agenda:
            if not isinstance(evento, dict):
                continue
            
            # Extrai informações do evento (formato real da API Clinicorp)
            # A API usa: AtomicDate (YYYYMMDD), fromTime ("HH:MM"), toTime ("HH:MM")
            atomic_date = evento.get('AtomicDate') or evento.get('atomicDate')
            from_time = evento.get('fromTime') or evento.get('FromTime')
            to_time = evento.get('toTime') or evento.get('ToTime')
            
            # Converte AtomicDate + fromTime para datetime
            hora_evento = None
            data_evento = None
            
            if atomic_date and from_time:
                try:
                    # AtomicDate vem como número: 20251125
                    atomic_str = str(atomic_date)
                    if len(atomic_str) == 8:
                        ano = int(atomic_str[:4])
                        mes = int(atomic_str[4:6])
                        dia = int(atomic_str[6:8])
                        
                        # fromTime vem como "12:00" ou "12:00:00"
                        hora_str = str(from_time).split(':')
                        hora = int(hora_str[0]) if hora_str else 0
                        minuto = int(hora_str[1]) if len(hora_str) > 1 else 0
                        
                        # Cria datetime no timezone de Brasília
                        data_evento = self.timezone_brasil.localize(
                            datetime(ano, mes, dia, hora, minuto)
                        )
                        hora_evento = hora
                        
                        # Filtra por horário (9h-18h)
                        # Inclui eventos que começam dentro do intervalo
                        # Ex: 9h-18h inclui eventos de 9:00 até 17:59
                        if hora_evento < hora_inicio or hora_evento >= hora_fim:
                            continue
                except Exception as e:
                    logger.debug(f"Erro ao processar data/hora do evento: {e}")
                    # Se não conseguir processar, tenta continuar
            
            # Determina se está ocupado
            # Eventos ocupados têm Patient_PersonId (são agendamentos reais)
            # Eventos livres são blocos de tempo sem paciente
            tem_paciente = evento.get('Patient_PersonId') is not None
            tipo = evento.get('Type') or ''
            deletado = evento.get('Deleted') == 'X'
            
            ocupado = tem_paciente and not deletado
            
            # Extrai informações do evento
            titulo = (
                evento.get('PatientName') or
                evento.get('Name') or
                evento.get('title') or
                evento.get('Title') or
                'Sem título'
            )
            
            descricao = (
                evento.get('Notes') or
                evento.get('notes') or
                evento.get('Procedures') or
                evento.get('CategoryDescription') or
                evento.get('description') or
                ''
            )
            
            # Informações adicionais
            profissional = (
                evento.get('DentistName') or
                evento.get('Name') or
                ''
            )
            
            categoria = evento.get('CategoryDescription') or ''
            
            evento_processado = {
                'id': evento.get('id'),
                'titulo': titulo,
                'descricao': descricao,
                'data': data_evento.isoformat() if data_evento else None,
                'data_atomic': atomic_date,
                'hora_inicio': from_time,
                'hora_fim': to_time,
                'hora_inicio_numero': hora_evento,
                'profissional': profissional,
                'categoria': categoria,
                'paciente_id': evento.get('Patient_PersonId'),
                'dentista_id': evento.get('Dentist_PersonId'),
                'tipo': tipo,
                'ocupado': ocupado,
                'deletado': deletado,
                'dados_originais': evento,  # Mantém dados originais para referência
            }
            
            eventos.append(evento_processado)
        
        logger.info(f"Processados {len(eventos)} eventos da agenda")
        return eventos
    
    def _extrair_hora(self, hora_str: str) -> Optional[int]:
        """Extrai a hora de uma string de hora"""
        try:
            if isinstance(hora_str, (int, float)):
                return int(hora_str)
            
            # Tenta diferentes formatos: "09:00", "9:00:00", etc
            partes = str(hora_str).split(':')
            if partes:
                return int(partes[0])
        except:
            pass
        return None
    
    def buscar_agenda_mes_completo(self, hora_inicio: int = 9, hora_fim: int = 18, profissional_id: Optional[str] = None) -> List[Dict]:
        """
        Busca agenda de 1 mês completo a partir de hoje
        
        Args:
            hora_inicio: Hora inicial (padrão 9h)
            hora_fim: Hora final (padrão 18h)
            profissional_id: ID do profissional para filtrar (opcional)
            
        Returns:
            Lista de eventos da agenda
        """
        hoje = datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0)
        um_mes_depois = hoje + timedelta(days=30)
        
        eventos = self.buscar_agenda(
            data_inicio=hoje,
            data_fim=um_mes_depois,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim
        )
        
        # Se foi especificado profissional_id, filtra eventos desse profissional
        if profissional_id:
            eventos = [e for e in eventos if str(e.get('dentista_id')) == str(profissional_id)]
        
        return eventos
    
    def buscar_agenda_por_profissional(
        self,
        profissional_id: str,
        data_inicio: Optional[datetime] = None,
        data_fim: Optional[datetime] = None,
        hora_inicio: int = 9,
        hora_fim: int = 18
    ) -> List[Dict]:
        """
        Busca agenda específica de um profissional
        
        Args:
            profissional_id: ID do profissional
            data_inicio: Data de início (usa hoje se None)
            data_fim: Data de fim (usa 1 mês a partir de hoje se None)
            hora_inicio: Hora inicial (padrão 9h)
            hora_fim: Hora final (padrão 18h)
            
        Returns:
            Lista de eventos da agenda do profissional
        """
        return self.buscar_agenda_mes_completo(
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            profissional_id=profissional_id
        )
    
    def listar_profissionais(self) -> List[Dict]:
        """
        Lista profissionais disponíveis na clínica usando o endpoint oficial da API
        
        Usa o endpoint /solution/api/core/person/list_by_type?type=DENTIST
        que retorna profissionais com nomes corretos e horários ocupados
        
        Returns:
            Lista de profissionais com id, nome e horários ocupados
        """
        try:
            logger.info(f"Buscando profissionais do endpoint oficial da API...")
            
            endpoint = '/solution/api/core/person/list_by_type'
            params = {
                'type': 'DENTIST',
                'professionalToBeDefined': 'X'
            }
            
            response = self.client.get(endpoint, use_api_url=True, params=params)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    profissionais_list = data.get('list') or []
                    
                    if not isinstance(profissionais_list, list):
                        profissionais_list = [profissionais_list] if profissionais_list else []
                    
                    profissionais = []
                    for prof_data in profissionais_list:
                        if not isinstance(prof_data, dict):
                            continue
                        
                        # Verifica se está ativo
                        if prof_data.get('Active') != 'X':
                            continue
                        
                        profissional_id = str(prof_data.get('id', ''))
                        nome = prof_data.get('Name', '').strip()
                        
                        if not profissional_id or not nome:
                            continue
                        
                        # Extrai horários ocupados (DentistBusyScheduleSlots)
                        horarios_ocupados = prof_data.get('DentistBusyScheduleSlots', [])
                        
                        profissional = {
                            'id': profissional_id,
                            'nome': nome,
                            'email': prof_data.get('Email', ''),
                            'telefone': prof_data.get('MobilePhone', ''),
                            'cor': prof_data.get('Color', ''),
                            'horarios_ocupados': horarios_ocupados,
                            'dados_originais': prof_data
                        }
                        
                        profissionais.append(profissional)
                    
                    logger.info(f"✅ Encontrados {len(profissionais)} profissionais ativos na API")
                    
                    if len(profissionais) > 0:
                        for prof in profissionais[:5]:  # Mostra até 5 primeiros
                            logger.debug(f"   - {prof['nome']} (ID: {prof['id']})")
                        if len(profissionais) > 5:
                            logger.debug(f"   ... e mais {len(profissionais) - 5} profissionais")
                    
                    return profissionais
                    
                except Exception as e:
                    logger.error(f"Erro ao processar resposta de profissionais: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    return []
            else:
                logger.error(f"Erro ao buscar profissionais: Status {response.status_code}")
                logger.debug(f"Resposta: {response.text[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"Erro ao listar profissionais: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def buscar_paciente_por_telefone(self, telefone: str) -> Optional[Dict]:
        """
        Busca paciente na API do Clinicorp pelo telefone
        
        Args:
            telefone: Telefone do paciente (com ou sem formatação)
            
        Returns:
            Dados do paciente se encontrado, None caso contrário
        """
        try:
            # Limpa o telefone (remove formatação)
            telefone_limpo = ''.join(filter(str.isdigit, telefone))
            
            if not telefone_limpo:
                logger.warning("Telefone vazio para busca de paciente")
                return None
            
            endpoint = '/solution/api/patient/search'
            params = {
                'name': telefone_limpo,  # Busca pelo telefone como "name"
                'onlyPatient': 'true'
            }
            
            logger.info(f"Buscando paciente pelo telefone: {telefone_limpo}")
            
            response = self.client.get(endpoint, use_api_url=True, params=params)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    pacientes = data.get('list') or data.get('data') or []
                    
                    if not isinstance(pacientes, list):
                        pacientes = [pacientes] if pacientes else []
                    
                    # Procura paciente com telefone correspondente
                    for paciente in pacientes:
                        if not isinstance(paciente, dict):
                            continue
                        
                        # Verifica se o telefone bate
                        mobile_phone = ''.join(filter(str.isdigit, str(paciente.get('MobilePhone', ''))))
                        phone = ''.join(filter(str.isdigit, str(paciente.get('Phone', ''))))
                        
                        if telefone_limpo in mobile_phone or telefone_limpo in phone or \
                           mobile_phone in telefone_limpo or phone in telefone_limpo:
                            logger.info(f"✅ Paciente encontrado: {paciente.get('Name')} (ID: {paciente.get('id')})")
                            return {
                                'id': paciente.get('id'),
                                'nome': paciente.get('Name', ''),
                                'telefone': paciente.get('MobilePhone', ''),
                                'email': paciente.get('Email', ''),
                                'dados_originais': paciente
                            }
                    
                    # Se não encontrou por telefone, tenta buscar diretamente pelo telefone formatado
                    # Alguns sistemas guardam com formatação
                    logger.debug(f"Paciente não encontrado na primeira busca, tentando busca alternativa...")
                    
                except Exception as e:
                    logger.error(f"Erro ao processar resposta de busca de paciente: {e}")
            else:
                logger.warning(f"Busca de paciente retornou status {response.status_code}")
            
            logger.info(f"Paciente não encontrado para telefone: {telefone}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar paciente por telefone: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def criar_paciente(self, nome: str, telefone: str, email: str = "") -> Optional[Dict]:
        """
        Cria um novo paciente na API do Clinicorp
        
        Args:
            nome: Nome completo do paciente
            telefone: Telefone do paciente
            email: Email do paciente (opcional)
            
        Returns:
            Dados do paciente criado ou None se falhar
        """
        try:
            if not nome or not telefone:
                logger.error("Nome e telefone são obrigatórios para criar paciente")
                return None
            
            # Limpa o telefone
            telefone_limpo = ''.join(filter(str.isdigit, telefone))
            
            clinic_id = self._obter_clinic_id()
            endpoint = '/solution/api/patient/create'
            
            # Dados do paciente para criação
            paciente_data = {
                "Name": nome.strip(),
                "MobilePhone": telefone_limpo,
                "Email": email.strip() if email else "",
                "Clinic_BusinessId": int(clinic_id),
                "Type": "PATIENT",
                "Active": "X",
                "_AccessPath": "*.Patient.Create"
            }
            
            logger.info(f"📝 Criando paciente no Clinicorp: {nome} (telefone: {telefone_limpo})")
            logger.debug(f"Payload: {paciente_data}")
            
            response = self.client.post(
                endpoint,
                use_api_url=True,
                json=paciente_data,
                headers={
                    'Content-Type': 'application/json;charset=UTF-8'
                }
            )
            
            if response.status_code == 200:
                try:
                    resultado = response.json()
                    
                    # Tenta extrair o ID de diferentes estruturas de resposta
                    paciente_id = None
                    
                    # Estrutura 1: resultado.id (resposta simples)
                    if resultado.get('id'):
                        paciente_id = resultado.get('id')
                    # Estrutura 2: resultado.patient.Patient.id (resposta Clinicorp)
                    elif resultado.get('patient', {}).get('Patient', {}).get('id'):
                        paciente_id = resultado['patient']['Patient']['id']
                    # Estrutura 3: resultado.Patient.id
                    elif resultado.get('Patient', {}).get('id'):
                        paciente_id = resultado['Patient']['id']
                    
                    if paciente_id:
                        logger.info(f"✅ Paciente criado com sucesso no Clinicorp: {nome} (ID: {paciente_id})")
                        return {
                            'id': paciente_id,
                            'nome': nome,
                            'telefone': telefone_limpo,
                            'email': email,
                            'dados_originais': resultado
                        }
                    else:
                        logger.error(f"Resposta da API não contém ID do paciente: {resultado}")
                        return None
                        
                except Exception as e:
                    logger.error(f"Erro ao processar resposta de criação de paciente: {e}")
                    return None
            else:
                logger.error(f"Erro ao criar paciente: Status {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao criar paciente: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def buscar_ou_criar_paciente(self, nome: str, telefone: str, email: str = "") -> Optional[Dict]:
        """
        Busca paciente pelo telefone. Se não existir, cria um novo.
        
        Args:
            nome: Nome completo do paciente
            telefone: Telefone do paciente
            email: Email do paciente (opcional)
            
        Returns:
            Dados do paciente (existente ou recém-criado) ou None se falhar
        """
        # Primeiro, busca paciente existente
        logger.info(f"🔍 Buscando paciente no Clinicorp pelo telefone: {telefone}")
        paciente = self.buscar_paciente_por_telefone(telefone)
        
        if paciente and paciente.get('id'):
            logger.info(f"✅ Paciente já existe no Clinicorp: {paciente.get('nome')} (ID: {paciente.get('id')})")
            return paciente
        
        # Não existe, cria novo
        logger.info(f"📝 Paciente não encontrado, criando novo: {nome}")
        paciente_criado = self.criar_paciente(nome=nome, telefone=telefone, email=email)
        
        if paciente_criado:
            return paciente_criado
        
        logger.error(f"❌ Falha ao criar paciente: {nome} ({telefone})")
        return None

    def buscar_paciente_por_nome(self, nome: str) -> List[Dict]:
        """
        Busca pacientes na API do Clinicorp pelo nome
        
        Args:
            nome: Nome do paciente (parcial ou completo)
            
        Returns:
            Lista de pacientes encontrados
        """
        try:
            if not nome or len(nome.strip()) < 2:
                logger.warning("Nome muito curto para busca de paciente")
                return []
            
            endpoint = '/solution/api/patient/search'
            params = {
                'name': nome.strip(),
                'onlyPatient': 'true'
            }
            
            logger.info(f"Buscando paciente pelo nome: {nome}")
            
            response = self.client.get(endpoint, use_api_url=True, params=params)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    pacientes_raw = data.get('list') or data.get('data') or []
                    
                    if not isinstance(pacientes_raw, list):
                        pacientes_raw = [pacientes_raw] if pacientes_raw else []
                    
                    pacientes = []
                    for paciente in pacientes_raw:
                        if not isinstance(paciente, dict):
                            continue
                        
                        pacientes.append({
                            'id': paciente.get('id'),
                            'nome': paciente.get('Name', ''),
                            'telefone': paciente.get('MobilePhone', ''),
                            'email': paciente.get('Email', ''),
                            'dados_originais': paciente
                        })
                    
                    logger.info(f"✅ Encontrados {len(pacientes)} pacientes para busca '{nome}'")
                    return pacientes
                    
                except Exception as e:
                    logger.error(f"Erro ao processar resposta de busca de paciente: {e}")
            else:
                logger.warning(f"Busca de paciente retornou status {response.status_code}")
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao buscar paciente por nome: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
        email: str = "",
        nome_paciente: str = ""
    ) -> Dict:
        """
        Cria um novo agendamento no Clinicorp.
        
        IMPORTANTE: O paciente deve existir no Clinicorp antes de criar o agendamento.
        Use buscar_ou_criar_paciente() primeiro para garantir que o paciente existe.
        
        Args:
            paciente_id: ID do paciente no Clinicorp (OBRIGATÓRIO)
            profissional_id: ID do profissional/dentista
            data: Data do agendamento (datetime)
            hora_inicio: Hora de início (formato "HH:MM")
            hora_fim: Hora de fim (formato "HH:MM")
            observacoes: Observações do agendamento
            procedimentos: Lista de procedimentos
            telefone: Telefone do paciente (para referência)
            email: Email do paciente (para referência)
            nome_paciente: Nome do paciente (para referência)
            
        Returns:
            Dicionário com resultado do agendamento
        """
        try:
            # Valida que paciente_id foi fornecido
            if not paciente_id or paciente_id == "" or paciente_id == "None":
                return {
                    'sucesso': False,
                    'erro': 'paciente_id é obrigatório. Crie o paciente primeiro usando buscar_ou_criar_paciente().'
                }
            
            clinic_id = self._obter_clinic_id()
            endpoint = '/solution/api/appointment/create'
            
            # Converte data para formato esperado (ISO com timezone UTC)
            data_iso = data.astimezone(pytz.UTC).isoformat()
            
            # Calcula AtomicDate (YYYYMMDD)
            atomic_date = int(data.strftime('%Y%m%d'))
            
            # Prepara dados do agendamento (sempre com paciente existente)
            agendamento_data = {
                "Patient_PersonId": int(paciente_id),
                "Dentist_PersonId": int(profissional_id),
                "date": data_iso,
                "referenceMonth": "",
                "fromTime": hora_inicio,
                "toTime": hora_fim,
                "Notes": observacoes,
                "Procedures": ", ".join(procedimentos) if procedimentos else "",
                "wasEdited": "",
                "SelectedProceduresList": procedimentos or [],
                "SubAppointments": [{
                    "ScheduleToType": "PROFESSIONAL",
                    "fromTime": hora_inicio,
                    "toTime": hora_fim,
                    "ScheduleToId": int(profissional_id),
                    "Name": "",
                    "Color": "",
                    "Dentist_PersonId": int(profissional_id)
                }],
                "ScheduleToType": "PROFESSIONAL",
                "ScheduleToId": int(profissional_id),
                "AtomicDate": atomic_date,
                "Clinic_BusinessId": int(clinic_id),
                "AddInfo": {"AddInfo1": "Confirmation,"},
                "AlertInfo": {
                    "ConfirmSchedule": "1D",
                    "AlertSchedule": "0H",
                    "ConfirmWhats": "",
                    "ConfirmSms": "X",
                    "AlertWhats": "",
                    "AlertSms": "",
                    "AlertCliniMe": "",
                    "ConfirmCliniMe": ""
                },
                "Email": email,
                "MobilePhone": telefone,
                "CreateUserId": self._obter_user_id(),
                "ToTestDate": data_iso,
                "ProceduresDuration": 0,
                "CreatedBy": "WEB",
                "_AccessPath": "*.Calendar.Appointment.Create"
            }
            
            logger.info(f"📅 Criando agendamento para paciente {paciente_id} com profissional {profissional_id} em {data.strftime('%Y-%m-%d')} {hora_inicio}-{hora_fim}")
            logger.debug(f"Payload do agendamento: {agendamento_data}")
            
            response = self.client.post(
                endpoint,
                use_api_url=True,
                json=agendamento_data,
                headers={
                    'Content-Type': 'application/json;charset=UTF-8'
                }
            )
            
            if response.status_code == 200:
                try:
                    resultado = response.json()
                    logger.info(f"✅ Agendamento criado com sucesso para paciente {paciente_id}")
                    
                    return {
                        'sucesso': True,
                        'dados': resultado,
                        'paciente_id': paciente_id
                    }
                except:
                    logger.info("✅ Agendamento criado com sucesso (resposta não JSON)")
                    return {
                        'sucesso': True,
                        'dados': response.text,
                        'paciente_id': paciente_id
                    }
            else:
                logger.error(f"Erro ao criar agendamento: {response.status_code} - {response.text}")
                return {
                    'sucesso': False,
                    'erro': f"Status {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Erro ao criar agendamento: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'sucesso': False,
                'erro': str(e)
            }

    def deletar_agendamento(self, agendamento_id: str) -> Dict:
        """Deleta (cancela) um agendamento no Clinicorp pelo ID.

        Args:
            agendamento_id: ID do agendamento no Clinicorp (campo id retornado na criação).

        Returns:
            Dicionário com resultado da deleção.
        """
        try:
            if not agendamento_id:
                return {
                    'sucesso': False,
                    'erro': 'agendamento_id é obrigatório'
                }

            endpoint = '/solution/api/appointment/delete'

            params = {
                'id': agendamento_id,
                '_AccessPath': '*.Appointment.Delete',
                '__caller': 'InfoPanel.render.onClick_delete_appointment'
            }

            logger.info(f"🗑️ Deletando agendamento no Clinicorp: ID {agendamento_id}")

            response = self.client.get(
                endpoint,
                use_api_url=True,
                params=params
            )

            if response.status_code == 200:
                try:
                    dados = response.json()
                except Exception:
                    dados = response.text

                logger.info(f"✅ Agendamento {agendamento_id} deletado com sucesso no Clinicorp")
                return {
                    'sucesso': True,
                    'dados': dados,
                    'id': agendamento_id
                }
            else:
                logger.error(f"Erro ao deletar agendamento {agendamento_id}: {response.status_code} - {response.text}")
                return {
                    'sucesso': False,
                    'erro': f'Status {response.status_code}: {response.text}'
                }

        except Exception as e:
            logger.error(f"Erro ao deletar agendamento {agendamento_id}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'sucesso': False,
                'erro': str(e)
            }


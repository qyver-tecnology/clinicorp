"""
Sistema de sincronização de agenda
"""
import logging
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import pytz
from api.agenda_api import AgendaAPI

logger = logging.getLogger(__name__)


class AgendaSync:
    """Gerencia sincronização periódica da agenda"""
    
    def __init__(self, intervalo_segundos: int = 15, salvar_em: str = "agenda_data.json"):
        """
        Inicializa o sincronizador de agenda
        
        Args:
            intervalo_segundos: Intervalo entre sincronizações (padrão 15 segundos)
            salvar_em: Arquivo para salvar os dados da agenda
        """
        self.intervalo_segundos = intervalo_segundos
        self.arquivo_dados = Path(salvar_em)
        self.agenda_api = AgendaAPI()
        self.timezone_brasil = pytz.timezone('America/Sao_Paulo')
        self.rodando = False
        
    def sincronizar(self) -> Dict:
        """
        Executa uma sincronização da agenda
        
        Returns:
            Dicionário com dados da sincronização
        """
        try:
            logger.info("Iniciando sincronização da agenda...")
            timestamp = datetime.now(self.timezone_brasil)
            
            # Busca agenda do mês completo (9h-18h)
            eventos = self.agenda_api.buscar_agenda_mes_completo(hora_inicio=9, hora_fim=18)
            
            # Separa eventos ocupados e livres
            eventos_ocupados = [e for e in eventos if e.get('ocupado')]
            eventos_livres = [e for e in eventos if not e.get('ocupado')]
            
            dados_sincronizacao = {
                'timestamp': timestamp.isoformat(),
                'data_inicio': datetime.now(self.timezone_brasil).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                'data_fim': (datetime.now(self.timezone_brasil) + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                'total_eventos': len(eventos),
                'eventos_ocupados': len(eventos_ocupados),
                'eventos_livres': len(eventos_livres),
                'eventos': eventos,
                'eventos_ocupados_detalhes': eventos_ocupados,
                'eventos_livres_detalhes': eventos_livres,
            }
            
            # Salva dados
            self._salvar_dados(dados_sincronizacao)
            
            logger.info(f"✅ Sincronização concluída: {len(eventos)} eventos ({len(eventos_ocupados)} ocupados, {len(eventos_livres)} livres)")
            
            return dados_sincronizacao
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar agenda: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'timestamp': datetime.now(self.timezone_brasil).isoformat(),
                'erro': str(e),
                'eventos': [],
            }
    
    def _salvar_dados(self, dados: Dict):
        """
        Salva dados da agenda no arquivo
        Mantém apenas a última agenda completa e um histórico resumido (sem duplicar eventos)
        """
        try:
            # Carrega dados existentes
            dados_existentes = self._carregar_dados()
            
            # Cria histórico resumido (sem os eventos completos para economizar espaço)
            historico_resumido = {
                'timestamp': dados['timestamp'],
                'data_inicio': dados['data_inicio'],
                'data_fim': dados['data_fim'],
                'total_eventos': dados['total_eventos'],
                'eventos_ocupados': dados['eventos_ocupados'],
                'eventos_livres': dados['eventos_livres'],
            }
            
            # Adiciona ao histórico resumido
            if 'historico' not in dados_existentes:
                dados_existentes['historico'] = []
            
            dados_existentes['historico'].append(historico_resumido)
            
            # Mantém apenas últimas 1000 sincronizações no histórico (apenas resumo, não eventos completos)
            if len(dados_existentes['historico']) > 1000:
                dados_existentes['historico'] = dados_existentes['historico'][-1000:]
            
            # Atualiza última sincronização completa (substitui a anterior, não adiciona)
            dados_existentes['ultima_sincronizacao'] = dados['timestamp']
            dados_existentes['ultima_agenda'] = dados['eventos']
            dados_existentes['ultima_agenda_ocupados'] = dados['eventos_ocupados_detalhes']
            dados_existentes['ultima_agenda_livres'] = dados['eventos_livres_detalhes']
            dados_existentes['ultima_agenda_stats'] = {
                'total_eventos': dados['total_eventos'],
                'eventos_ocupados': dados['eventos_ocupados'],
                'eventos_livres': dados['eventos_livres'],
                'data_inicio': dados['data_inicio'],
                'data_fim': dados['data_fim'],
            }
            
            # Salva arquivo
            with open(self.arquivo_dados, 'w', encoding='utf-8') as f:
                json.dump(dados_existentes, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Dados salvos em {self.arquivo_dados} (sem duplicacao)")
            
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")
    
    def _carregar_dados(self) -> Dict:
        """Carrega dados existentes do arquivo"""
        try:
            if self.arquivo_dados.exists():
                with open(self.arquivo_dados, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Erro ao carregar dados: {e}")
        
        return {}
    
    def iniciar_sincronizacao_continua(self):
        """
        Inicia sincronização contínua a cada intervalo_segundos segundos
        """
        self.rodando = True
        logger.info(f"Iniciando sincronização contínua (a cada {self.intervalo_segundos} segundos)")
        
        try:
            while self.rodando:
                self.sincronizar()
                
                # Aguarda intervalo antes da próxima sincronização
                if self.rodando:
                    logger.debug(f"Aguardando {self.intervalo_segundos} segundos até próxima sincronização...")
                    time.sleep(self.intervalo_segundos)
                    
        except KeyboardInterrupt:
            logger.info("Sincronização interrompida pelo usuário")
            self.rodando = False
        except Exception as e:
            logger.error(f"Erro na sincronização contínua: {e}")
            self.rodando = False
    
    def parar(self):
        """Para a sincronização contínua"""
        logger.info("Parando sincronização...")
        self.rodando = False
    
    def obter_ultima_agenda(self) -> List[Dict]:
        """Retorna a última agenda sincronizada"""
        dados = self._carregar_dados()
        return dados.get('ultima_agenda', [])


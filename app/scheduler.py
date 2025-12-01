"""
Configuração do scheduler (cronjobs)
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from app.config import Config
from app.services.agenda_service import AgendaService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
agenda_service = AgendaService()

def job_sincronizar_agenda():
    """Job para sincronizar agenda periodicamente"""
    try:
        logger.info("Executando job de sincronizacao da agenda...")
        resultado = agenda_service.sincronizar_agenda()
        logger.info(f"Job concluido: {resultado.get('total_eventos', 0)} eventos")
    except Exception as e:
        logger.error(f"Erro no job de sincronizacao: {e}")

def init_scheduler(app):
    """Inicializa o scheduler com os jobs configurados"""
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler desativado via configuração (SCHEDULER_ENABLED=false)")
        return

    if not scheduler.running:
        # Adiciona job de sincronização
        scheduler.add_job(
            func=job_sincronizar_agenda,
            trigger=IntervalTrigger(seconds=Config.SYNC_INTERVAL_SECONDS),
            id='sync_agenda',
            name='Sincronizar agenda Clinicorp',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"Scheduler iniciado - sincronizacao a cada {Config.SYNC_INTERVAL_SECONDS} segundos")
        
        # Executa primeira sincronização imediatamente
        logger.info("Executando primeira sincronizacao...")
        job_sincronizar_agenda()


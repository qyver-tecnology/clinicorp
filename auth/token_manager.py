"""
Módulo para gerenciar tokens de autenticação (salvar, carregar, renovar)
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenManager:
    """Gerencia tokens de autenticação com persistência em arquivo"""
    
    def __init__(self, token_file: str = "token.json"):
        """
        Args:
            token_file: Caminho do arquivo para salvar o token
        """
        self.token_file = Path(token_file)
        self.token_data: Optional[Dict] = None
    
    def save_token(self, token: str, expires_in: Optional[int] = None):
        """
        Salva o token no arquivo
        
        Args:
            token: Token Bearer
            expires_in: Tempo de expiração em segundos (opcional)
        """
        try:
            expires_at = None
            if expires_in:
                expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            
            token_data = {
                'token': token,
                'created_at': datetime.now().isoformat(),
                'expires_at': expires_at,
                'expires_in': expires_in
            }
            
            # Cria o diretório se não existir
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2, ensure_ascii=False)
            
            self.token_data = token_data
            logger.info(f"Token salvo em: {self.token_file}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar token: {e}")
            raise
    
    def load_token(self) -> Optional[str]:
        """
        Carrega o token do arquivo
        
        Returns:
            Token se válido, None caso contrário
        """
        try:
            if not self.token_file.exists():
                logger.info("Arquivo de token não encontrado")
                return None
            
            with open(self.token_file, 'r', encoding='utf-8') as f:
                self.token_data = json.load(f)
            
            token = self.token_data.get('token')
            
            if not token:
                logger.warning("Token não encontrado no arquivo")
                return None
            
            # Verifica se o token expirou
            if self.is_token_expired():
                logger.warning("Token expirado")
                return None
            
            logger.info("Token carregado com sucesso")
            return token
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar arquivo de token: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar token: {e}")
            return None
    
    def is_token_expired(self) -> bool:
        """
        Verifica se o token expirou
        
        Returns:
            True se expirado, False caso contrário
        """
        if not self.token_data:
            return True
        
        expires_at = self.token_data.get('expires_at')
        if not expires_at:
            # Se não tem data de expiração, assume que não expirou
            return False
        
        try:
            expires_datetime = datetime.fromisoformat(expires_at)
            is_expired = datetime.now() >= expires_datetime
            if is_expired:
                logger.info(f"Token expirou em: {expires_at}")
            return is_expired
        except Exception as e:
            logger.error(f"Erro ao verificar expiração do token: {e}")
            return False
    
    def delete_token(self):
        """
        Remove o arquivo de token
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Token removido")
            self.token_data = None
        except Exception as e:
            logger.error(f"Erro ao remover token: {e}")
    
    def get_token_info(self) -> Optional[Dict]:
        """
        Retorna informações sobre o token atual
        """
        return self.token_data.copy() if self.token_data else None
    
    def token_exists(self) -> bool:
        """
        Verifica se o arquivo de token existe
        """
        return self.token_file.exists()


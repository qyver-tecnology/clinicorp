"""
Cliente principal para interagir com o sistema Clinicorp
Gerencia autenticação automática e renovação de tokens
"""
import logging
from typing import Optional
from auth.clinicorp_auth import ClinicorpAuth
from auth.token_manager import TokenManager
try:
    # Tenta importar do novo config primeiro
    from app.config import Config
    CLINICORP_BASE_URL = Config.CLINICORP_BASE_URL
    CLINICORP_API_URL = Config.CLINICORP_API_URL
    CLINICORP_USERNAME = Config.CLINICORP_USERNAME
    CLINICORP_PASSWORD = Config.CLINICORP_PASSWORD
    TOKEN_FILE = Config.TOKEN_FILE
except ImportError:
    # Fallback para config antigo
    from config import (
        CLINICORP_BASE_URL,
        CLINICORP_API_URL,
        CLINICORP_USERNAME,
        CLINICORP_PASSWORD,
        TOKEN_FILE
    )

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clinicorp.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ClinicorpClient:
    """
    Cliente principal para interagir com o sistema Clinicorp
    Gerencia autenticação automática e renovação de tokens
    """
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Inicializa o cliente Clinicorp
        
        Args:
            username: Nome de usuário (usa config padrão se None)
            password: Senha (usa config padrão se None)
        """
        self.username = username or CLINICORP_USERNAME
        self.password = password or CLINICORP_PASSWORD
        self.auth = ClinicorpAuth(CLINICORP_BASE_URL, CLINICORP_API_URL)
        self.token_manager = TokenManager(str(TOKEN_FILE))
        self._ensure_authenticated()
    
    def _ensure_authenticated(self):
        """
        Garante que está autenticado, renovando o token se necessário
        """
        # Tenta carregar token salvo
        token = self.token_manager.load_token()
        
        if token and not self.token_manager.is_token_expired():
            logger.info("Usando token existente")
            self.auth.set_token(token)
            
            # Verifica se o token ainda é válido fazendo uma requisição de teste
            if self.auth.is_logged_in():
                logger.info("Token válido confirmado")
                return
            else:
                logger.warning("Token inválido, fazendo novo login")
                self.token_manager.delete_token()
        
        # Se não tem token válido, faz login
        logger.info("Realizando login...")
        token = self.auth.login(self.username, self.password)
        
        if not token:
            raise Exception("Falha ao realizar login no sistema Clinicorp")
        
        # Salva o token
        if token != "SESSION_ACTIVE":
            # Se recebeu um token real, salva
            # Tenta extrair expiração do JWT se for um token JWT
            expires_in = None
            if isinstance(token, str) and token.count('.') == 2:
                try:
                    import base64
                    import json as json_lib
                    import time
                    parts = token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.urlsafe_b64decode(payload)
                        jwt_data = json_lib.loads(decoded)
                        if 'exp' in jwt_data:
                            exp_timestamp = jwt_data['exp']
                            current_timestamp = int(time.time())
                            expires_in = max(0, exp_timestamp - current_timestamp)
                            logger.info(f"Token JWT expira em {expires_in} segundos ({expires_in/3600:.1f} horas)")
                except Exception as e:
                    logger.debug(f"Erro ao extrair expiração do JWT: {e}")
            
            # Se não conseguiu extrair, usa padrão de 24h
            if expires_in is None or expires_in <= 0:
                expires_in = 86400  # 24 horas padrão
                logger.info("Usando expiração padrão de 24 horas")
            
            self.token_manager.save_token(token, expires_in=expires_in)
            self.auth.set_token(token)
        else:
            # Se é apenas sessão ativa (baseada em cookies), salva como indicador
            # A sessão HTTP já tem os cookies necessários
            logger.info("Usando autenticação baseada em cookies de sessão")
            self.token_manager.save_token("SESSION_ACTIVE")
            # Não precisa setar token Bearer, os cookies já estão na sessão
        
        # Verifica se realmente está autenticado
        if not self.auth.is_logged_in():
            logger.warning("Login realizado mas verificação de autenticação falhou")
            # Tenta mais uma vez
            if not self.auth.is_logged_in():
                raise Exception("Não foi possível confirmar autenticação após login")
        
        logger.info("Autenticação realizada com sucesso")
    
    def refresh_token(self):
        """
        Força a renovação do token
        """
        logger.info("Renovando token...")
        self.token_manager.delete_token()
        self._ensure_authenticated()
    
    def get_session(self):
        """
        Retorna a sessão HTTP autenticada
        """
        # Verifica se precisa renovar antes de retornar
        if not self.auth.is_logged_in():
            logger.warning("Sessão expirada, renovando...")
            self.refresh_token()
        
        return self.auth.get_session()
    
    def make_request(self, method: str, endpoint: str, use_api_url: bool = False, **kwargs):
        """
        Faz uma requisição HTTP autenticada
        
        Args:
            method: Método HTTP (GET, POST, etc)
            endpoint: Endpoint da API (relativo à base URL ou API URL)
            use_api_url: Se True, usa CLINICORP_API_URL ao invés de CLINICORP_BASE_URL
            **kwargs: Argumentos adicionais para requests
            
        Returns:
            Resposta da requisição
        """
        session = self.get_session()
        
        # Escolhe a URL base dependendo do tipo de endpoint
        if use_api_url or endpoint.startswith('/api/') or endpoint.startswith('api/'):
            base_url = CLINICORP_API_URL
        else:
            base_url = CLINICORP_BASE_URL
        
        # Remove barra inicial duplicada se necessário
        if endpoint.startswith('/') and base_url.endswith('/'):
            endpoint = endpoint[1:]
        elif not endpoint.startswith('/') and not base_url.endswith('/'):
            endpoint = '/' + endpoint
        
        url = f"{base_url}{endpoint}"
        
        try:
            response = session.request(method, url, **kwargs)
            
            # Descomprime Brotli se necessário (requests não faz automaticamente)
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            if 'br' in content_encoding and response.content:
                try:
                    import brotli
                    # Verifica se está comprimido (não começa com caracteres JSON)
                    if response.content[:1] not in [b'{', b'[']:
                        logger.debug("Descomprimindo resposta Brotli...")
                        decompressed = brotli.decompress(response.content)
                        response._content = decompressed
                        response.encoding = 'utf-8'
                except ImportError:
                    logger.warning("Biblioteca brotli nao instalada. Instale com: pip install brotli")
                except Exception as e:
                    logger.debug(f"Erro ao descomprimir Brotli: {e}")
            
            # Se recebeu 401 ou redirecionou para login, renova token
            # Verifica se a resposta é texto antes de procurar por login
            try:
                response_text = response.text if hasattr(response, 'text') else ''
            except:
                response_text = ''
            
            if response.status_code == 401 or 'login__login_screen' in response_text:
                logger.warning("Token expirado durante requisição, renovando...")
                self.refresh_token()
                # Tenta novamente
                session = self.get_session()
                response = session.request(method, url, **kwargs)
                # Descomprime novamente se necessário
                content_encoding = response.headers.get('Content-Encoding', '').lower()
                if 'br' in content_encoding and response.content:
                    try:
                        import brotli
                        if response.content[:1] not in [b'{', b'[']:
                            decompressed = brotli.decompress(response.content)
                            response._content = decompressed
                            response.encoding = 'utf-8'
                    except:
                        pass
            
            return response
        except Exception as e:
            logger.error(f"Erro na requisição: {e}")
            raise
    
    def get(self, endpoint: str, **kwargs):
        """Faz uma requisição GET"""
        return self.make_request('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs):
        """Faz uma requisição POST"""
        return self.make_request('POST', endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs):
        """Faz uma requisição PUT"""
        return self.make_request('PUT', endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs):
        """Faz uma requisição DELETE"""
        return self.make_request('DELETE', endpoint, **kwargs)


if __name__ == "__main__":
    # Exemplo de uso
    try:
        client = ClinicorpClient()
        print("Cliente Clinicorp inicializado com sucesso!")
        print(f"Token salvo em: {TOKEN_FILE}")
        
        # Exemplo: fazer uma requisição
        # response = client.get("/api/some-endpoint")
        # print(response.json())
        
    except Exception as e:
        logger.error(f"Erro ao inicializar cliente: {e}")
        raise


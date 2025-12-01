"""
Módulo de autenticação para o sistema Clinicorp
"""
import requests
from typing import Optional, Dict
import logging
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class ClinicorpAuth:
    """Classe para gerenciar autenticação no sistema Clinicorp"""
    
    def __init__(self, base_url: str = "https://sistema.clinicorp.com", api_url: str = "https://api.clinicorp.com"):
        self.base_url = base_url
        self.api_url = api_url
        self.login_url = f"{base_url}/login/"
        self.login_api_endpoint = f"{api_url}/security/user/login"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Origin': base_url,
            'Referer': f'{base_url}/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })
    
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Realiza login no sistema Clinicorp e retorna o token de autenticação
        
        Args:
            username: Nome de usuário
            password: Senha
            
        Returns:
            Token Bearer se login for bem-sucedido, None caso contrário
        """
        try:
            # Primeiro, acessa a página de login para obter cookies e sessão
            logger.info(f"Acessando página de login: {self.login_url}")
            response = self.session.get(self.login_url)
            response.raise_for_status()
            
            # Calcula timezone offset (em minutos)
            # O offset no exemplo é 180 (provavelmente UTC-3 = -180 minutos ou UTC+3 = +180 minutos)
            # Vamos calcular baseado no timezone do sistema
            import time
            import datetime
            # Calcula a diferença entre hora local e UTC
            # Se estamos em UTC-3, o offset deve ser -180
            # Se estamos em UTC+3, o offset deve ser +180
            now_local = datetime.datetime.now()
            now_utc = datetime.datetime.utcnow()
            # A diferença mostra quantas horas estamos à frente ou atrás do UTC
            offset_timedelta = now_local - now_utc
            tzoffset = int(offset_timedelta.total_seconds() / 60)
            
            # Prepara dados de login no formato correto
            login_data = {
                "username": username,
                "password": password,
                "authMethod": "USER_PASSWORD",
                "loginType": "DEFAULT",
                "tzoffset": tzoffset,
                "clientId": "74c455eb-a75e-40f4-94f9-791a2f739b81"  # Client ID padrão
            }
            
            logger.info(f"Fazendo login em: {self.login_api_endpoint}")
            logger.debug(f"Dados de login: {{'username': '{username}', 'password': '***', 'authMethod': 'USER_PASSWORD', 'loginType': 'DEFAULT', 'tzoffset': {tzoffset}, 'clientId': '...'}}")
            
            # Faz requisição de login
            response = self.session.post(
                self.login_api_endpoint,
                json=login_data,
                headers={
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                },
                timeout=30
            )
            
            logger.debug(f"Status: {response.status_code}")
            logger.debug(f"Headers de resposta: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.debug(f"Resposta JSON completa: {data}")
                    
                    # Tenta extrair o token de diferentes formatos de resposta
                    # O token está em data['user']['token'] conforme a resposta da API
                    token = (
                        data.get('user', {}).get('token') or  # Formato correto da API Clinicorp
                        data.get('token') or
                        data.get('access_token') or
                        data.get('accessToken') or
                        data.get('bearer_token') or
                        data.get('authToken') or
                        data.get('data', {}).get('token') or
                        data.get('data', {}).get('access_token') or
                        data.get('result', {}).get('token') or
                        (data.get('user', {}).get('accessToken') if isinstance(data.get('user'), dict) else None)
                    )
                    
                    if token:
                        logger.info("✅ Login realizado com sucesso!")
                        logger.debug(f"Token obtido: {token[:50]}..." if len(str(token)) > 50 else f"Token obtido: {token}")
                        return token
                    else:
                        # Se não tem token mas a resposta foi 200, pode ser que use cookies
                        logger.warning("Login retornou 200 mas não encontrou token. Verificando cookies...")
                        token = self._extract_token_from_session()
                        if token:
                            return token
                        # Se ainda assim não tem token, mas login foi bem-sucedido, usa sessão
                        if 'error' not in str(data).lower() and 'fail' not in str(data).lower():
                            logger.info("Login aparentemente bem-sucedido, usando sessão baseada em cookies")
                            return "SESSION_ACTIVE"
                        else:
                            logger.error(f"Login falhou: {data}")
                            return None
                            
                except ValueError as e:
                    logger.error(f"Erro ao decodificar resposta JSON: {e}")
                    logger.debug(f"Resposta texto: {response.text[:500]}")
                    return None
            else:
                logger.error(f"Login falhou com status {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"Erro: {error_data}")
                except:
                    logger.error(f"Resposta: {response.text[:500]}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao realizar login: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _extract_api_endpoints(self, html_content: str) -> list:
        """
        Extrai endpoints de API do HTML/JavaScript da página
        """
        endpoints = []
        try:
            # Procura por padrões comuns em JavaScript
            import re
            
            # Padrões comuns: '/api/auth/login', '/api/login', etc.
            patterns = [
                r'["\']([^"\']*\/api[^"\']*\/login[^"\']*)["\']',
                r'["\']([^"\']*\/api[^"\']*\/auth[^"\']*\/login[^"\']*)["\']',
                r'["\']([^"\']*\/api[^"\']*\/signin[^"\']*)["\']',
                r'url:\s*["\']([^"\']*\/api[^"\']*)["\']',
                r'endpoint:\s*["\']([^"\']*\/api[^"\']*)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if match.startswith('http'):
                        endpoints.append(match)
                    elif match.startswith('/'):
                        endpoints.append(f"{self.base_url}{match}")
                    else:
                        endpoints.append(f"{self.base_url}/{match}")
            
            # Remove duplicatas
            return list(set(endpoints))
        except Exception as e:
            logger.debug(f"Erro ao extrair endpoints: {e}")
            return []
    
    def _login_via_form(self, username: str, password: str, html_content: str = None) -> Optional[str]:
        """
        Tenta fazer login via formulário HTML (fallback)
        Usa JavaScript/API que o formulário pode chamar internamente
        """
        try:
            # Se não recebeu HTML, busca novamente
            if not html_content:
                logger.info("Buscando página de login novamente...")
                response = self.session.get(self.login_url)
                html_content = response.text
            
            # Analisa o formulário HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Tenta encontrar o endpoint correto analisando o formulário
            form = soup.find('form')
            form_action = None
            if form and form.get('action'):
                form_action = form.get('action')
                if form_action.startswith('/'):
                    form_action = f"{self.base_url}{form_action}"
                elif not form_action.startswith('http'):
                    form_action = f"{self.base_url}/{form_action}"
            
            # Procura por scripts JavaScript que possam ter endpoints
            scripts = soup.find_all('script')
            js_endpoints = []
            for script in scripts:
                if script.string:
                    js_endpoints.extend(self._extract_api_endpoints(script.string))
            
            # Tenta endpoints encontrados
            api_endpoints = list(set(js_endpoints))
            if form_action:
                api_endpoints.insert(0, form_action)
            
            # Adiciona endpoints comuns
            api_endpoints.extend([
                f"{self.base_url}/api/auth/signin",
                f"{self.base_url}/api/auth/login",
                f"{self.base_url}/api/login",
                f"{self.base_url}/api/v1/auth/login",
                f"{self.base_url}/api/v1/login",
            ])
            
            # Dados no formato que o formulário pode esperar
            login_payloads = [
                {"username": username, "password": password},
                {"email": username, "password": password},
                {"user": username, "password": password},
                {"login": username, "password": password},
                {"usuario": username, "senha": password},
            ]
            
            for endpoint in api_endpoints:
                for payload in login_payloads:
                    try:
                        logger.info(f"Tentando: {endpoint} com payload: {list(payload.keys())}")
                        response = self.session.post(
                            endpoint,
                            json=payload,
                            headers={
                                'Content-Type': 'application/json',
                                'Referer': self.login_url,
                                'Origin': self.base_url,
                            },
                            timeout=30,
                            allow_redirects=False
                        )
                        
                        logger.debug(f"Status: {response.status_code}")
                        if response.status_code not in [404, 405]:
                            logger.debug(f"Resposta (primeiros 500 chars): {response.text[:500]}")
                        
                        # Se recebeu resposta válida
                        if response.status_code in [200, 201]:
                            try:
                                data = response.json()
                                logger.debug(f"Resposta JSON: {data}")
                                token = (
                                    data.get('token') or
                                    data.get('access_token') or
                                    data.get('accessToken') or
                                    data.get('bearer_token') or
                                    data.get('authToken') or
                                    data.get('data', {}).get('token') or
                                    data.get('data', {}).get('access_token')
                                )
                                if token:
                                    logger.info("Token encontrado via API do formulário")
                                    return token
                            except:
                                pass
                        
                        # Verifica se redirecionou (sucesso)
                        if response.status_code in [301, 302, 303, 307, 308]:
                            location = response.headers.get('Location', '')
                            logger.debug(f"Redirecionamento para: {location}")
                            if 'login' not in location.lower():
                                logger.info("Login bem-sucedido (redirecionamento detectado)")
                                token = self._extract_token_from_session()
                                return token or "SESSION_ACTIVE"
                    except Exception as e:
                        logger.debug(f"Erro ao tentar {endpoint}: {e}")
                        continue
            
            # Última tentativa: simular submit do formulário HTML
            logger.info("Tentando submit direto do formulário HTML...")
            
            # Tenta diferentes formatos de dados do formulário
            form_data_variants = [
                {'username': username, 'password': password},
                {'email': username, 'password': password},
                {'user': username, 'password': password},
                {'login': username, 'password': password},
            ]
            
            for form_data in form_data_variants:
                try:
                    response = self.session.post(
                        self.login_url,
                        data=form_data,
                        headers={
                            'Referer': self.login_url,
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        allow_redirects=True,
                        timeout=30
                    )
                    
                    logger.debug(f"Status após submit: {response.status_code}")
                    logger.debug(f"URL após submit: {response.url}")
                    
                    # Verifica se o login foi bem-sucedido
                    soup = BeautifulSoup(response.text, 'html.parser')
                    login_screen = soup.find('div', {'id': 'login__login_screen'})
                    
                    if not login_screen and response.url != self.login_url:
                        # Login parece ter funcionado
                        logger.info("Login aparentemente bem-sucedido (não está mais na página de login)")
                        token = self._extract_token_from_session()
                        if token:
                            logger.info("Token encontrado após submit do formulário")
                            return token
                        else:
                            logger.warning("Login bem-sucedido, mas token não encontrado - usando sessão")
                            return "SESSION_ACTIVE"
                except Exception as e:
                    logger.debug(f"Erro ao tentar submit com {form_data}: {e}")
                    continue
            
            logger.error("Login falhou - todas as tentativas falharam")
            return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao fazer login via formulário: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado no login via formulário: {e}")
            return None
    
    def _extract_token_from_session(self) -> Optional[str]:
        """
        Extrai o token Bearer da sessão atual (cookies, headers, etc)
        """
        # Verifica cookies (procura por vários padrões comuns)
        for cookie in self.session.cookies:
            cookie_name_lower = cookie.name.lower()
            if any(keyword in cookie_name_lower for keyword in ['token', 'auth', 'session', 'jwt', 'bearer']):
                value = cookie.value
                # Se o cookie contém um token Bearer, extrai apenas o token
                if 'Bearer ' in value:
                    return value.replace('Bearer ', '').strip()
                return value
        
        # Verifica se há Authorization header
        if 'Authorization' in self.session.headers:
            auth_header = self.session.headers['Authorization']
            if auth_header.startswith('Bearer '):
                return auth_header.replace('Bearer ', '').strip()
        
        # Tenta extrair de cookies de sessão (alguns sistemas usam sessionId como token)
        session_cookies = ['sessionId', 'session_id', 'session', 'sid']
        for cookie_name in session_cookies:
            if cookie_name in self.session.cookies:
                return self.session.cookies[cookie_name]
        
        return None
    
    def is_logged_in(self) -> bool:
        """
        Verifica se ainda está autenticado fazendo uma requisição de teste
        """
        try:
            # Tenta acessar uma página protegida
            test_urls = [
                f"{self.base_url}/dashboard",
                f"{self.base_url}/home",
                f"{self.base_url}/api/user",
                f"{self.base_url}/api/v1/user",
                f"{self.base_url}/api/me",
            ]
            
            for url in test_urls:
                try:
                    response = self.session.get(url, timeout=10, allow_redirects=False)
                    
                    # Verifica status code
                    if response.status_code == 401:
                        continue
                    
                    # Verifica se redirecionou para login
                    if response.status_code in [301, 302, 303, 307, 308]:
                        location = response.headers.get('Location', '')
                        if 'login' in location.lower():
                            continue
                    
                    # Verifica conteúdo HTML
                    if 'login__login_screen' in response.text:
                        continue
                    
                    # Se passou todas as verificações, está autenticado
                    return True
                except Exception as e:
                    logger.debug(f"Erro ao testar URL {url}: {e}")
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar login: {e}")
            return False
    
    def get_session_token(self) -> Optional[str]:
        """
        Retorna o token atual da sessão
        """
        return self._extract_token_from_session()
    
    def set_token(self, token: str):
        """
        Define o token Bearer na sessão
        """
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
    
    def get_session(self) -> requests.Session:
        """
        Retorna a sessão HTTP atual
        """
        return self.session


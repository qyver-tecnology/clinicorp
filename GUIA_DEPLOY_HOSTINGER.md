# 🚀 Guia de Deploy - Hostinger (Sem Domínio)

Este guia explica como fazer o deploy da API Flask na Hostinger usando o IP do servidor (sem domínio).

## 📋 Pré-requisitos

- Conta na Hostinger com acesso SSH
- Python 3.8+ instalado no servidor
- Acesso ao painel de controle da Hostinger
- Arquivo `.env` configurado

## 🔧 Passo 1: Preparar o Ambiente Local

### 1.1. Remover arquivos desnecessários

Certifique-se de que os seguintes arquivos foram removidos:
- ✅ `teste.json` (já removido)
- ✅ Arquivos `__pycache__/` (serão ignorados pelo .gitignore)

### 1.2. Verificar arquivos essenciais

Certifique-se de ter:
- ✅ `requirements.txt`
- ✅ `.env` (com todas as variáveis configuradas)
- ✅ `start.py` ou `run.py`
- ✅ Todos os arquivos do projeto

## 📦 Passo 2: Fazer Upload dos Arquivos

### 2.1. Via File Manager (Hostinger)

1. Acesse o **File Manager** no painel da Hostinger
2. Navegue até a pasta `public_html` ou crie uma pasta `api` dentro dela
3. Faça upload de todos os arquivos do projeto (exceto `venv/`)

### 2.2. Via FTP/SFTP

```bash
# Exemplo usando sftp
sftp usuario@seu-ip-hostinger
cd public_html/api
put -r * .
```

### 2.3. Via Git (Recomendado)

Se você tem um repositório Git:

```bash
# No servidor Hostinger via SSH
cd ~/public_html
git clone https://seu-repositorio.git api
cd api
```

## 🐍 Passo 3: Configurar Python no Servidor

### 3.1. Conectar via SSH

```bash
ssh usuario@seu-ip-hostinger
```

### 3.2. Verificar versão do Python

```bash
python3 --version
# ou
python --version
```

### 3.3. Criar ambiente virtual

```bash
cd ~/public_html/api  # ou onde você colocou os arquivos
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows (se estiver usando Windows no servidor)
```

### 3.4. Instalar dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## ⚙️ Passo 4: Configurar Variáveis de Ambiente

### 4.1. Criar arquivo .env no servidor

```bash
cd ~/public_html/api
nano .env
```

### 4.2. Copiar conteúdo do .env local

Cole todas as variáveis do seu `.env` local:

```env
# Flask
SECRET_KEY=clinicorp-agenda-sync-secret-key-2025
FLASK_DEBUG=False
PORT=5000

# Clinicorp
CLINICORP_USERNAME=william@essenciallis
CLINICORP_PASSWORD=cJxc.LNwfT,/rH3
CLINICORP_CLINIC_ID=6556997543657472

# Supabase/PostgreSQL
DATABASE_URL=postgresql://postgres.wtfheobvaamelqifttjj:zJt3HcddV2gXDslb@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true
DIRECT_URL=postgresql://postgres.wtfheobvaamelqifttjj:zJt3HcddV2gXDslb@aws-1-sa-east-1.pooler.supabase.com:5432/postgres

# Scheduler
SYNC_INTERVAL_SECONDS=15

# Logging
LOG_LEVEL=INFO
```

Salve com `Ctrl+O`, `Enter`, `Ctrl+X`

## 🔄 Passo 5: Configurar o Servidor para Rodar em Background

### 5.1. Usando screen (Recomendado)

```bash
# Instalar screen (se não tiver)
sudo apt-get install screen  # Ubuntu/Debian
# ou
sudo yum install screen  # CentOS/RHEL

# Criar uma sessão screen
screen -S flask-api

# Ativar ambiente virtual
cd ~/public_html/api
source venv/bin/activate

# Rodar a aplicação
python start.py
# ou
python run.py

# Detach da sessão: Ctrl+A, depois D
```

### 5.2. Usando nohup (Alternativa)

```bash
cd ~/public_html/api
source venv/bin/activate
nohup python start.py > app.log 2>&1 &
```

### 5.3. Usando systemd (Produção - Requer acesso root)

Crie o arquivo `/etc/systemd/system/flask-api.service`:

```ini
[Unit]
Description=Flask API - Clinicorp Agenda Sync
After=network.target

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/home/seu-usuario/public_html/api
Environment="PATH=/home/seu-usuario/public_html/api/venv/bin"
ExecStart=/home/seu-usuario/public_html/api/venv/bin/python start.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Ativar o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flask-api
sudo systemctl start flask-api
sudo systemctl status flask-api
```

## 🌐 Passo 6: Configurar Firewall e Portas

### 6.1. Verificar porta disponível

A Hostinger geralmente permite portas acima de 1024. Use a porta 5000 ou outra disponível.

### 6.2. Configurar firewall (se necessário)

```bash
# Ubuntu/Debian
sudo ufw allow 5000/tcp
sudo ufw reload

# Verificar status
sudo ufw status
```

### 6.3. Obter IP do servidor

No painel da Hostinger, você encontrará o IP do servidor. Anote esse IP.

## 🔗 Passo 7: Configurar n8n Workflow

### 7.1. Obter URL da API

Sua API estará disponível em:
```
http://SEU-IP-HOSTINGER:5000/api
```

**Exemplo:**
```
http://123.45.67.89:5000/api
```

### 7.2. Atualizar URLs no workflow n8n

No arquivo `workflow_n8n_completo.json`, substitua todas as ocorrências de:

**ANTES:**
```json
"url": "https://7811d9b534ad.ngrok-free.app/api/..."
```

**DEPOIS:**
```json
"url": "http://SEU-IP-HOSTINGER:5000/api/..."
```

### 7.3. URLs específicas para atualizar

Procure e substitua estas URLs:

1. **Salvar_nome_paciente:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/paciente/salvar-nome"
   ```

2. **Buscar_profissionais_disponiveis:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/agenda/profissionais"
   ```

3. **Buscar_agendas_disponiveis:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/agenda/disponiveis"
   ```

4. **Criar_agendamento_local:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/agenda/criar"
   ```

5. **Sincronizar_agenda:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/agenda/sync"
   ```

6. **Buscar_eventos_agenda:**
   ```json
   "url": "http://SEU-IP-HOSTINGER:5000/api/agenda/eventos"
   ```

### 7.4. Remover headers ngrok

Remova os headers relacionados ao ngrok:

**REMOVER:**
```json
{
  "name": "ngrok-skip-browser-warning",
  "value": "true"
}
```

## ✅ Passo 8: Testar a API

### 8.1. Teste de Health Check

```bash
curl http://SEU-IP-HOSTINGER:5000/api/health
```

**Resposta esperada:**
```json
{
  "status": "ok",
  "service": "clinicorp-agenda-sync"
}
```

### 8.2. Teste de Endpoints

```bash
# Listar profissionais
curl http://SEU-IP-HOSTINGER:5000/api/agenda/profissionais

# Buscar agendas disponíveis
curl "http://SEU-IP-HOSTINGER:5000/api/agenda/disponiveis?data=2025-12-01"

# Salvar nome do paciente
curl -X POST http://SEU-IP-HOSTINGER:5000/api/paciente/salvar-nome \
  -H "Content-Type: application/json" \
  -d '{"telefone": "554999599263", "nome": "Gustavo"}'
```

## 🔍 Passo 9: Verificar Logs

### 9.1. Logs da aplicação

```bash
# Se usou nohup
tail -f ~/public_html/api/app.log

# Se usou screen
screen -r flask-api

# Se usou systemd
sudo journalctl -u flask-api -f
```

### 9.2. Verificar erros

```bash
# Ver últimos erros
tail -n 100 ~/public_html/api/logs/app.log
```

## 🛠️ Passo 10: Manutenção

### 10.1. Reiniciar a aplicação

**Com screen:**
```bash
screen -r flask-api
# Ctrl+C para parar
python start.py
# Ctrl+A, D para detach
```

**Com systemd:**
```bash
sudo systemctl restart flask-api
```

**Com nohup:**
```bash
# Encontrar processo
ps aux | grep python

# Matar processo
kill PID_DO_PROCESSO

# Reiniciar
cd ~/public_html/api
source venv/bin/activate
nohup python start.py > app.log 2>&1 &
```

### 10.2. Atualizar código

```bash
cd ~/public_html/api
source venv/bin/activate

# Se usar Git
git pull origin main

# Instalar novas dependências (se houver)
pip install -r requirements.txt

# Reiniciar aplicação
```

## ⚠️ Problemas Comuns

### Porta 5000 não acessível

**Solução:** Use outra porta (ex: 8000, 8080) e atualize no `.env`:
```env
PORT=8000
```

### Erro de permissão

**Solução:**
```bash
chmod +x start.py
chmod -R 755 ~/public_html/api
```

### Banco de dados não conecta

**Solução:** Verifique se o IP do servidor Hostinger está na whitelist do Supabase.

### Aplicação para após desconectar SSH

**Solução:** Use `screen`, `nohup` ou `systemd` conforme descrito acima.

## 📝 Checklist Final

- [ ] Arquivos enviados para o servidor
- [ ] Ambiente virtual criado e dependências instaladas
- [ ] Arquivo `.env` configurado no servidor
- [ ] Aplicação rodando em background
- [ ] Porta configurada e acessível
- [ ] URLs atualizadas no workflow n8n
- [ ] Headers ngrok removidos
- [ ] Health check funcionando
- [ ] Endpoints testados
- [ ] Logs verificados

## 🎯 URLs Finais para n8n

Substitua `SEU-IP-HOSTINGER` pelo IP real do seu servidor:

```
http://SEU-IP-HOSTINGER:5000/api/health
http://SEU-IP-HOSTINGER:5000/api/agenda/profissionais
http://SEU-IP-HOSTINGER:5000/api/agenda/disponiveis
http://SEU-IP-HOSTINGER:5000/api/agenda/criar
http://SEU-IP-HOSTINGER:5000/api/agenda/sync
http://SEU-IP-HOSTINGER:5000/api/agenda/eventos
http://SEU-IP-HOSTINGER:5000/api/paciente/salvar-nome
http://SEU-IP-HOSTINGER:5000/api/paciente/buscar-nome
```

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs da aplicação
2. Verifique se a porta está aberta
3. Verifique se o Python está rodando
4. Verifique as variáveis de ambiente
5. Entre em contato com o suporte da Hostinger se necessário

---

**Última atualização:** 29/11/2025


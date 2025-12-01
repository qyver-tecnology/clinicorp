# Instruções para Atualizar Workflow do N8N

## Objetivo
Integrar o histórico de chat com o workflow do n8n para que a IA verifique conversas anteriores pelo telefone do paciente.

## Passos para Atualizar o Workflow

### 1. Adicionar Nó HTTP - Verificar Paciente
**Tipo:** HTTP Request

**Configuração:**
- **URL:** `http://localhost:5000/api/chat/verificar-paciente?telefone={{$json.telefone}}`
- **Método:** GET
- **Headers:**
  - `Content-Type: application/json`

**Descrição:** Verifica se o paciente já conversou antes

**Saída esperada:**
```json
{
  "conhecido": true,
  "telefone": "11999999999",
  "nome": "João Silva",
  "email": "joao@email.com",
  "ultima_conversa": "2025-12-01T14:30:00"
}
```

---

### 2. Adicionar Nó HTTP - Obter Contexto
**Tipo:** HTTP Request

**Configuração:**
- **URL:** `http://localhost:5000/api/chat/contexto?telefone={{$json.telefone}}`
- **Método:** GET
- **Headers:**
  - `Content-Type: application/json`

**Descrição:** Obtém o contexto completo do paciente

**Saída esperada:**
```json
{
  "telefone": "11999999999",
  "contexto": "🔍 CONTEXTO DO PACIENTE:\n- Nome: João Silva\n..."
}
```

---

### 3. Adicionar Nó IF - Verificar se Paciente é Conhecido
**Tipo:** IF

**Configuração:**
- **Condição:** `{{$json.body.conhecido === true}}`
- **Ramo TRUE:** Usar contexto do paciente conhecido
- **Ramo FALSE:** Tratar como novo paciente

---

### 4. Atualizar Prompt da IA

**Se paciente é conhecido:**
```
Você está conversando com um paciente que já conversou conosco antes.

{{$json.contexto}}

Use as informações anteriores para personalizar a conversa e fornecer um atendimento melhor.
```

**Se paciente é novo:**
```
Você está conversando com um novo paciente. Seja educado e colete informações básicas como nome e email.

Telefone: {{$json.telefone}}
```

---

### 5. Adicionar Nó HTTP - Salvar Mensagem (Opcional)
**Tipo:** HTTP Request

**Configuração:**
- **URL:** `http://localhost:5000/api/chat/salvar-mensagem`
- **Método:** POST
- **Headers:**
  - `Content-Type: application/json`
- **Body:**
```json
{
  "session_id": "{{$json.sessionId}}",
  "mensagem": {{$json.message}},
  "telefone": "{{$json.telefone}}",
  "nome_paciente": "{{$json.nome}}",
  "email_paciente": "{{$json.email}}"
}
```

---

## Fluxo Recomendado

```
[Entrada de Mensagem]
        ↓
[Extrair Telefone]
        ↓
[HTTP - Verificar Paciente] ← Chama /api/chat/verificar-paciente
        ↓
[IF - Paciente Conhecido?]
    ↙           ↘
[SIM]           [NÃO]
  ↓               ↓
[HTTP - Obter  [Tratar como
 Contexto]      novo paciente]
  ↓               ↓
  └─────┬─────┘
        ↓
[Preparar Prompt com Contexto]
        ↓
[Chamar IA (Claude/GPT)]
        ↓
[Responder ao Paciente]
        ↓
[HTTP - Salvar Mensagem] (opcional)
```

---

## Variáveis Esperadas

- `$json.telefone` - Telefone do paciente
- `$json.sessionId` - ID da sessão
- `$json.message` - Mensagem do usuário
- `$json.nome` - Nome do paciente (se disponível)
- `$json.email` - Email do paciente (se disponível)

---

## Exemplo de Workflow Completo

1. **Trigger:** Webhook recebe mensagem
2. **Extract:** Extrai telefone da mensagem
3. **Verify:** Chama `/api/chat/verificar-paciente`
4. **Condition:** Verifica se `conhecido === true`
5. **Context:** Se conhecido, chama `/api/chat/contexto`
6. **AI:** Prepara prompt com contexto e chama IA
7. **Response:** Envia resposta ao paciente
8. **Save:** Salva mensagem no histórico (opcional)

---

## Logs para Monitorar

Verifique o arquivo `logs/app.log` para:
- `🔍 Verificação de paciente` - Quando verifica se paciente é conhecido
- `📋 Histórico obtido` - Quando busca histórico
- `📌 Contexto gerado` - Quando gera contexto para IA
- `💾 Mensagem salva` - Quando salva mensagem no banco

---

## Testes

### Teste 1: Novo Paciente
```bash
curl "http://localhost:5000/api/chat/verificar-paciente?telefone=11987654321"
# Resposta esperada: {"conhecido": false, "telefone": "11987654321"}
```

### Teste 2: Paciente Conhecido
```bash
curl "http://localhost:5000/api/chat/verificar-paciente?telefone=11999999999"
# Resposta esperada: {"conhecido": true, "nome": "João Silva", ...}
```

### Teste 3: Obter Contexto
```bash
curl "http://localhost:5000/api/chat/contexto?telefone=11999999999"
# Resposta esperada: {"telefone": "11999999999", "contexto": "🔍 CONTEXTO..."}
```

---

## Troubleshooting

### Erro: "Banco de dados não conectado"
- Verifique se DATABASE_URL ou DIRECT_URL está configurada no .env
- Execute a migração: `python migrations/add_telefone_to_chat_histories.py`

### Erro: "Parâmetro telefone é obrigatório"
- Certifique-se de que o telefone está sendo extraído corretamente da mensagem
- Verifique se está sendo passado como query parameter

### Histórico não aparece
- Verifique se as mensagens estão sendo salvas com o telefone correto
- Consulte os logs para ver se há erros ao salvar

---

## Próximos Passos

1. ✅ Criar migração do banco de dados
2. ✅ Implementar endpoints de chat
3. ⏳ Atualizar workflow do n8n
4. ⏳ Testar integração completa
5. ⏳ Monitorar logs em produção

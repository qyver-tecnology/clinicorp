#!/usr/bin/env python3
"""
Script para atualizar URLs do workflow n8n para o servidor Hostinger
"""
import json
import sys
import re

def atualizar_urls_workflow(arquivo_workflow, ip_hostinger, porta=5000):
    """
    Atualiza todas as URLs do workflow n8n para apontar para o servidor Hostinger
    
    Args:
        arquivo_workflow: Caminho do arquivo workflow_n8n_completo.json
        ip_hostinger: IP do servidor Hostinger (ex: "123.45.67.89")
        porta: Porta do servidor (padrão: 5000)
    """
    base_url = f"http://{ip_hostinger}:{porta}"
    
    # Ler arquivo
    try:
        with open(arquivo_workflow, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {arquivo_workflow}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao ler JSON: {e}")
        sys.exit(1)
    
    # URLs antigas (ngrok)
    urls_antigas = [
        "https://7811d9b534ad.ngrok-free.app",
        "https://.*\\.ngrok-free\\.app",
        "https://.*\\.ngrok\\.io",
    ]
    
    # URLs novas
    urls_novas = {
        "/api/agenda/profissionais": f"{base_url}/api/agenda/profissionais",
        "/api/agenda/disponiveis": f"{base_url}/api/agenda/disponiveis",
        "/api/agenda/criar": f"{base_url}/api/agenda/criar",
        "/api/agenda/sync": f"{base_url}/api/agenda/sync",
        "/api/agenda/eventos": f"{base_url}/api/agenda/eventos",
        "/api/paciente/salvar-nome": f"{base_url}/api/paciente/salvar-nome",
        "/api/paciente/buscar-nome": f"{base_url}/api/paciente/buscar-nome",
    }
    
    # Contador de alterações
    alteracoes = 0
    
    # Função para atualizar URLs em um objeto
    def atualizar_urls_em_objeto(obj):
        nonlocal alteracoes
        
        if isinstance(obj, dict):
            # Verificar campo 'url'
            if 'url' in obj:
                url_antiga = obj['url']
                
                # Verificar se é uma URL do ngrok
                for pattern in urls_antigas:
                    if re.search(pattern, url_antiga):
                        # Extrair o path da URL
                        for path, nova_url in urls_novas.items():
                            if path in url_antiga:
                                obj['url'] = nova_url
                                print(f"✅ Atualizado: {url_antiga} → {nova_url}")
                                alteracoes += 1
                                break
                        else:
                            # Se não encontrou path específico, substituir base URL
                            nova_url = re.sub(pattern, base_url, url_antiga)
                            if nova_url != url_antiga:
                                obj['url'] = nova_url
                                print(f"✅ Atualizado: {url_antiga} → {nova_url}")
                                alteracoes += 1
                        break
            
            # Remover header ngrok-skip-browser-warning
            if 'parametersHeaders' in obj and 'values' in obj['parametersHeaders']:
                headers = obj['parametersHeaders']['values']
                headers_removidos = [
                    h for h in headers 
                    if h.get('name') == 'ngrok-skip-browser-warning'
                ]
                if headers_removidos:
                    obj['parametersHeaders']['values'] = [
                        h for h in headers 
                        if h.get('name') != 'ngrok-skip-browser-warning'
                    ]
                    alteracoes += len(headers_removidos)
                    print(f"✅ Removido header ngrok-skip-browser-warning")
            
            # Recursivamente atualizar todos os valores
            for key, value in obj.items():
                atualizar_urls_em_objeto(value)
        
        elif isinstance(obj, list):
            for item in obj:
                atualizar_urls_em_objeto(item)
    
    # Atualizar workflow
    print(f"🔄 Atualizando URLs para: {base_url}")
    print("-" * 60)
    atualizar_urls_em_objeto(workflow)
    
    # Salvar arquivo
    arquivo_backup = arquivo_workflow.replace('.json', '_backup.json')
    try:
        # Fazer backup
        with open(arquivo_backup, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        print(f"💾 Backup salvo em: {arquivo_backup}")
    except Exception as e:
        print(f"⚠️  Aviso: Não foi possível criar backup: {e}")
    
    # Salvar arquivo atualizado
    try:
        with open(arquivo_workflow, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        print(f"💾 Arquivo atualizado: {arquivo_workflow}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        sys.exit(1)
    
    print("-" * 60)
    print(f"✅ Concluído! {alteracoes} alteração(ões) realizada(s)")
    print(f"\n📝 Próximos passos:")
    print(f"   1. Importe o workflow atualizado no n8n")
    print(f"   2. Teste os endpoints para garantir que estão funcionando")
    print(f"   3. Verifique se todas as URLs foram atualizadas corretamente")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python atualizar_urls_workflow.py <arquivo_workflow> <ip_hostinger> [porta]")
        print("\nExemplo:")
        print("  python atualizar_urls_workflow.py workflow_n8n_completo.json 123.45.67.89")
        print("  python atualizar_urls_workflow.py workflow_n8n_completo.json 123.45.67.89 8000")
        sys.exit(1)
    
    arquivo = sys.argv[1]
    ip = sys.argv[2]
    porta = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    
    atualizar_urls_workflow(arquivo, ip, porta)


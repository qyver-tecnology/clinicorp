"""
Script para iniciar a aplicação Flask
"""
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

from run import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("=" * 70)
    print("CLINICORP AGENDA SYNC - API Flask")
    print("=" * 70)
    print(f"\nServidor iniciando em: http://localhost:{port}")
    print(f"Debug: {debug}")
    print(f"\nEndpoints disponiveis:")
    print(f"  - GET  /api/health")
    print(f"  - POST /api/agenda/sync")
    print(f"  - GET  /api/agenda/eventos")
    print(f"  - GET  /api/agenda/estatisticas")
    print("\nPressione Ctrl+C para parar\n")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )


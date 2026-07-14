import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
from datetime import datetime, timezone
import os

# 1. Configurar uma sessão resiliente (tenta novamente se a API falhar)
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[ 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))
headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}

def executar_etl():
    print("Buscando lista de deputados do RJ...")
    url_deps = "https://dadosabertos.camara.leg.br/api/v2/deputados?siglaUf=RJ&itens=100&ordem=ASC&ordenarPor=nome"
    response = session.get(url_deps, headers=headers, timeout=30)
    deputados = response.json()['dados']
    
    ano_atual = datetime.now().year
    mes_atual = datetime.now().month

    # 2. Buscar despesas para cada deputado
    for dep in deputados:
        print(f"Buscando despesas de: {dep['nome']}")
        url_despesas = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{dep['id']}/despesas?ano={ano_atual}&mes={mes_atual}&itens=100"
        
        try:
            resp_desp = session.get(url_despesas, headers=headers, timeout=30)
            despesas_dados = resp_desp.json().get('dados', [])
            
            # Somar os valores do mês
            total_gasto = sum(despesa['valorDocumento'] for despesa in despesas_dados)
            dep['gastoMes'] = round(total_gasto, 2)
        except Exception as e:
            print(f"Erro ao buscar despesa para {dep['nome']}: {e}")
            dep['gastoMes'] = 0.0
            
        # Pausa de meio segundo para não sobrecarregar a API da Câmara
        time.sleep(0.5)

    # 3. Preparar e salvar o arquivo final
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dados_finais = {
        "atualizadoEm": agora,
        "dados": deputados
    }

    os.makedirs("data", exist_ok=True)
    with open("data/deputados.json", "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
        
    print("ETL concluído com sucesso!")

if __name__ == "__main__":
    executar_etl()

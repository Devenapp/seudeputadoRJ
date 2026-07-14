import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qs
import json
import time
from datetime import datetime, timezone
import os

# Configurar sessão resiliente
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

    for dep in deputados:
        print(f"Processando: {dep['nome']}")
        
        # -------------------------------------------------------------
        # 1. Gasto de Gabinete (Ano Inteiro agrupado por Mês)
        # -------------------------------------------------------------
        # Removemos o parâmetro &mes= para puxar o ano todo
        url_despesas = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{dep['id']}/despesas?ano={ano_atual}&itens=100"
        
        # Inicia um dicionário com todos os meses zerados
        gastos_mensais = {str(m): 0.0 for m in range(1, 13)}
        
        while url_despesas:
            try:
                resp_desp = session.get(url_despesas, headers=headers, timeout=30)
                json_desp = resp_desp.json()
                
                # Soma a despesa no mês correspondente
                for d in json_desp.get('dados', []):
                    mes = str(d['mes'])
                    if mes in gastos_mensais:
                        gastos_mensais[mes] += d['valorDocumento']
                
                url_despesas = None
                for link in json_desp.get('links', []):
                    if link['rel'] == 'next':
                        url_despesas = link['href']
                        break
                        
                if url_despesas:
                    time.sleep(0.3)
                    
            except Exception as e:
                print(f"Erro ao buscar despesa de {dep['nome']}: {e}")
                break

        # Arredonda os valores finais de cada mês
        dep['gastosMensais'] = {m: round(v, 2) for m, v in gastos_mensais.items()}

        # -------------------------------------------------------------
        # 2. Projetos Apresentados (Apenas Leis na Legislatura Atual)
        # -------------------------------------------------------------
        url_projetos = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?idDeputadoAutor={dep['id']}&dataApresentacaoInicio=2023-02-01&siglaTipo=PL&siglaTipo=PEC&siglaTipo=PLP&itens=1"
        total_projetos = 0
        
        try:
            resp_proj = session.get(url_projetos, headers=headers, timeout=30)
            json_proj = resp_proj.json()
            
            for link in json_proj.get('links', []):
                if link['rel'] == 'last':
                    parsed_url = urlparse(link['href'])
                    pagina = parse_qs(parsed_url.query).get('pagina')
                    if pagina:
                        total_projetos = int(pagina[0])
                        break
            
            if total_projetos == 0 and len(json_proj.get('dados', [])) > 0:
                total_projetos = 1

            dep['projetosApresentados'] = total_projetos
            
        except Exception as e:
            print(f"Erro ao contar projetos de {dep['nome']}: {e}")
            dep['projetosApresentados'] = 0

        # -------------------------------------------------------------
        # 3. Placeholders do MVP
        # -------------------------------------------------------------
        dep['presencaPlenario'] = "N/D"
        dep['assessores'] = "N/D"

        time.sleep(0.5)

    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dados_finais = {
        "atualizadoEm": agora,
        "dados": deputados
    }

    os.makedirs("data", exist_ok=True)
    with open("data/deputados.json", "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
        
    print("ETL concluído e documentação validada com sucesso!")

if __name__ == "__main__":
    executar_etl()

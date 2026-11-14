import os
import re
import json
import time
import random
import urllib.parse
from playwright.sync_api import sync_playwright
from robo_licitacoes_sjc_7_2 import classificar_objeto, faxinar_base_json

ARQUIVO_JSON_LICITACOES = "licitacoes.json"

ORGAOS_ALVO = {
    "45395704000149": {"nome": "FUNDACAO CULTURAL CASSIANO RICARDO", "cidade": "SAO JOSE DOS CAMPOS"},
    "46526471000140": {"nome": "PREFEITURA MUNICIPAL DE SAO JOSE DOS CAMPOS", "cidade": "SAO JOSE DOS CAMPOS"},
    "45393576000108": {"nome": "PREFEITURA MUNICIPAL DE JACAREI", "cidade": "JACAREI"},
    "50437516000176": {"nome": "JACAREI CAMARA MUNICIPAL", "cidade": "JACAREI"},
    "45194248000170": {"nome": "PREFEITURA MUNICIPAL DE CACAPAVA", "cidade": "CACAPAVA"},
    "50453703000143": {"nome": "FUNDACAO DE SAUDE E ASSISTENCIA DE CACAPAVA", "cidade": "CACAPAVA"}
}

def extrair_pncp_id(href: str) -> str:
    match = re.search(r'pncp_id=([^&]+)', href)
    if match:
        return urllib.parse.unquote(match.group(1))
    return str(hash(href))

def executar_varredura_licita_pub():
    print("==================================================================")
    print("🚀 MONITOR REGIONAL LICITA.PUB (FILTRO BLINDADO SST & MECÂNICA)")
    print("==================================================================")

    historico = []
    if os.path.exists(ARQUIVO_JSON_LICITACOES):
        try:
            with open(ARQUIVO_JSON_LICITACOES, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except Exception as e:
            print(f"⚠️ Aviso ao ler base local: {e}")
            historico = []

    mapa_ids = {item.get("id"): item for item in historico}
    novos_adicionados = 0

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=chrome_path if os.path.exists(chrome_path) else None
        )
        page = browser.new_page()

        for cnpj, info in ORGAOS_ALVO.items():
            url_orgao = f"https://licita.pub/orgao/{cnpj}"
            nome_orgao = info["nome"]
            cidade_orgao = info["cidade"]

            print(f"\n🔍 Varrendo Licita.pub: {nome_orgao} ({cidade_orgao})...")

            try:
                page.goto(url_orgao, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(random.randint(1000, 2000))

                itens_licitacao = page.locator("div.lic-item").all()

                for item in itens_licitacao:
                    link_el = item.locator("a").first
                    if not link_el.is_visible():
                        continue

                    titulo_lic = link_el.inner_text().strip()
                    href = link_el.get_attribute("href")
                    pncp_id = extrair_pncp_id(href)

                    if pncp_id in mapa_ids:
                        continue

                    valido, categoria = classificar_objeto(titulo_lic)
                    if valido:
                        link_direto = f"https://licita.pub{href}" if href.startswith("/") else href
                        nova_licitacao = {
                            "id": pncp_id,
                            "categoria": categoria,
                            "orgao": nome_orgao,
                            "valor": 0.0,
                            "objeto": titulo_lic,
                            "cidade": cidade_orgao,
                            "link_edital": link_direto
                        }
                        mapa_ids[pncp_id] = nova_licitacao
                        novos_adicionados += 1
                        print(f"  🎯 [{categoria}] -> {titulo_lic[:75]}...")

                time.sleep(random.randint(1, 3))

            except Exception as err:
                print(f"  ⚠️ Erro ao consultar {nome_orgao}: {err}")

        browser.close()

    with open(ARQUIVO_JSON_LICITACOES, "w", encoding="utf-8") as f:
        json.dump(list(mapa_ids.values()), f, ensure_ascii=False, indent=4)

    total_limpo = faxinar_base_json(ARQUIVO_JSON_LICITACOES)

    print("\n==================================================================")
    print("✅ VARREDURA INTEGRADA CONCLUÍDA COM SUCESSO!")
    print(f"📌 Novas Oportunidades Filtradas Adicionadas: {novos_adicionados}")
    print(f"📊 Total Limpo no 'licitacoes.json': {total_limpo} oportunidades.")
    print("==================================================================")

if __name__ == "__main__":
    executar_varredura_licita_pub()
import os
import re
import json
import time
import random
import unicodedata
import urllib.parse
from playwright.sync_api import sync_playwright

ARQUIVO_JSON_LICITACOES = "licitacoes.json"

# CNPJs dos Órgãos Alvo das 3 Cidades Prioritárias
ORGAOS_ALVO = {
    "45395704000149": {"nome": "FUNDACAO CULTURAL CASSIANO RICARDO", "cidade": "SAO JOSE DOS CAMPOS"},
    "46526471000140": {"nome": "PREFEITURA MUNICIPAL DE SAO JOSE DOS CAMPOS", "cidade": "SAO JOSE DOS CAMPOS"},
    "45393576000108": {"nome": "PREFEITURA MUNICIPAL DE JACAREI", "cidade": "JACAREI"},
    "50437516000176": {"nome": "JACAREI CAMARA MUNICIPAL", "cidade": "JACAREI"},
    "45194248000170": {"nome": "PREFEITURA MUNICIPAL DE CACAPAVA", "cidade": "CACAPAVA"},
    "50453703000143": {"nome": "FUNDACAO DE SAUDE E ASSISTENCIA DE CACAPAVA", "cidade": "CACAPAVA"}
}

# ==============================================================================
# ESTRUTURA OFICIAL DE FILTROS TM ENGENHARIA (PADRONIZADA)
# ==============================================================================
TERMOS_PERMITIDOS = [
    r"\bAVCB\b", r"\bCLCB\b", r"LAUDO.*INCEND", r"PROJETO.*INCEND", r"COMBATE.*INCEND",
    r"RECARGA.*EXTINTOR", r"TESTE.*MANGUEIRA", r"MANUTENC.*HIDRANTE", r"BRIGADA.*INCEND",
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
    r"SEGURANCA.*TRABALHO", r"SAUDE.*TRABALHO", r"SAUDE.*OCUPACIONAL", r"INSALUBRIDADE",
    r"PERICULOSIDADE", r"HIGIENE.*OCUPACIONAL", r"MEDICINA.*TRABALHO", r"ANALISE.*ERGONOMIC",
    r"ADEQUAC.*MAQUINA", r"APRECIAC.*RISCO", r"ART.*MECANICA", r"LAUDO.*MECANICO",
    r"LINHA.*VIDA", r"PONTO.*ANCORAGEM", r"CALDEIRA", r"VASO.*PRESSAO", r"COMPRESSOR",
    r"NR[- ]?10", r"NR[- ]?12", r"NR[- ]?13", r"NR[- ]?18", r"NR[- ]?33", r"NR[- ]?35",
    r"PMOC", r"SPDA", r"PARARAIO", r"LAUDO.*ESTRUTURAL", r"LAUDO.*TECNICO.*ENGENHARIA"
]

TERMOS_PROIBIDOS = [
    r"TENIS", r"SAPATO", r"BOTINA", r"UNIFORME", r"CAFÉ", r"CAFE", r"ACUCAR", r"PAO",
    r"ALIMENTIC", r"GENEROS", r"HOSPITALAR", r"MEDICAMENTO", r"SERINGA", r"IMPRESSORA",
    r"COMPUTADOR", r"CADEIRA", r"VEICULO", r"TRATOR", r"SUCATA", r"PISCINA",
    r"ZELADORIA", r"JARDINAGEM", r"SEGURANCA ARMADA", r"GASOLINA", r"DIESEL",
    r"PAVIMENTACAO", r"ASFALTO", r"ROCAGEM", r"VARRECAO", r"LIXO", r"TAMPAS DE BUEIRO",
    r"CONSTRUCAO DE PREFEITURA", r"OBRA DE PAVIMENTAC"
]

def remover_acentos(texto: str) -> str:
    """Normaliza o texto removendo acentos e convertendo para maiúsculo."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

def validar_objeto_tm(objeto_texto: str) -> bool:
    """Aplica o filtro idêntico ao robô principal para validar termos permitidos e descartar proibidos."""
    texto = remover_acentos(objeto_texto)
    # Descarta imediatamente se contiver qualquer termo proibido
    if any(re.search(re.compile(termo, re.IGNORECASE), texto) for termo in TERMOS_PROIBIDOS):
        return False
    # Aprova se contiver qualquer um dos termos permitidos
    if any(re.search(re.compile(termo, re.IGNORECASE), texto) for termo in TERMOS_PERMITIDOS):
        return True
    return False

def extrair_pncp_id(href: str) -> str:
    """Extrai o ID universal para evitar registros duplicados."""
    match = re.search(r'pncp_id=([^&]+)', href)
    if match:
        return urllib.parse.unquote(match.group(1))
    return str(hash(href))

def executar_varredura_licita_pub():
    print("==================================================================")
    print("🚀 MONITOR REGIONAL LICITA.PUB (FILTROS EXPANDIDOS TM ENGENHARIA)")
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

                    # TRAVA ANTI-DUPLICAÇÃO
                    if pncp_id in mapa_ids:
                        continue

                    # FILTRAGEM RIGOROSA TM ENGENHARIA
                    if validar_objeto_tm(titulo_lic):
                        link_direto = f"https://licita.pub{href}" if href.startswith("/") else href
                        
                        nova_licitacao = {
                            "id": pncp_id,
                            "orgao": nome_orgao,
                            "valor": 0.0,
                            "objeto": titulo_lic,
                            "cidade": cidade_orgao,
                            "link_edital": link_direto
                        }

                        mapa_ids[pncp_id] = nova_licitacao
                        novos_adicionados += 1
                        print(f"  🎯 [OPORTUNIDADE QUALIFICADA FILTRADA] -> {titulo_lic[:75]}...")

                time.sleep(random.randint(1, 3))

            except Exception as err:
                print(f"  ⚠️ Erro ao consultar {nome_orgao}: {err}")

        browser.close()

    lista_final = list(mapa_ids.values())

    with open(ARQUIVO_JSON_LICITACOES, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, ensure_ascii=False, indent=4)

    print("\n==================================================================")
    print("✅ VARREDURA INTEGRADA CONCLUÍDA COM SUCESSO!")
    print(f"📌 Novas Oportunidades Filtradas Adicionadas: {novos_adicionados}")
    print(f"📊 Total Acumulado no 'licitacoes.json': {len(lista_final)} oportunidades.")
    print("==================================================================")

if __name__ == "__main__":
    executar_varredura_licita_pub()
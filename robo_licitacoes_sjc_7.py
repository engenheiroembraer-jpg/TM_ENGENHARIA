import os
import re
import time
import json
import random
import unicodedata
import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from stoplossmanager import StopLossManager
except ImportError:
    StopLossManager = None

URL_PNCP = "https://pncp.gov.br"
URL_PLANILHA_TM = "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"
TELEGRAM_TOKEN = "8269224927:AAGzNVzbb4b8-JDaroQfyWklQh1ISxZPWFw"
TELEGRAM_CHAT_ID = "7193404104"

# ==============================================================================
# CÓDIGOS CATSER ESTRITOS (APENAS SST, TREINAMENTOS E INSPEÇÃO MECÂNICA)
# ==============================================================================
CODIGOS_CATSER_TM = [
    8818,    # Serviços de Engenharia de Segurança do Trabalho
    16438,   # Treinamento e Capacitação Profissional (NRs, Brigada, APH/DEA)
    25470,   # Vistoria, Validação e Certificação (AVCB / CLCB)
    242497,  # Serviço de Vistoria e Emissão de Laudos de Segurança
    25518,   # Inspeção e Ensaio Não Destrutivo (NR-13 / Vasos / Caldeiras)
    25496,   # Laudos Técnicos de Engenharia Mecânica / Industrial
]

CIDADES_ESCOPO = [
    "SAO JOSE DOS CAMPOS", "TAUBATE", "JACAREI", "PINDAMONHANGABA", "GUARATINGUETA",
    "UBATUBA", "SAO SEBASTIAO", "ILHABELA", "CARAGUATATUBA", "CACAPAVA", "LORENA",
    "CRUZEIRO", "APARECIDA", "TREMEMBE", "SAO LUIZ DO PARAITINGA", "CAMPOS DO JORDAO",
    "SANTO ANTONIO DO PINHAL", "SAO BENTO DO SAPUCAI", "SANTA BRANCA", "IGARATA",
    "PARAIBUNA", "JAMBEIRO", "REDENCAO DA SERRA", "NATIVIDADE DA SERRA", "SILVEIRAS",
    "CUNHA", "CACHOEIRA PAULISTA", "CANAS", "POTIM", "ROSEIRA", "LAGOINHA", "LAVRINHAS",
    "QUELUZ", "BANANAL", "ARAPEI", "SAO JOSE DO BARREIRO", "SAO PAULO", "SANTOS",
    "MOGI DAS CRUZES", "SUZANO", "ARUJA", "SANTA ISABEL", "POA", "FERRAZ DE VASCONCELOS",
    "ITAQUAQUECETUBA", "SALESOPOLIS", "GUARULHOS", "BERTIOGA"
]

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

CIDADES_CLEAN = [remover_acentos(c) for c in CIDADES_ESCOPO]

# ==============================================================================
# TERMOS PERMITIDOS POR CATEGORIA (FOCO 100% SST & ENGENHARIA MECÂNICA)
# ==============================================================================
REGRAS_INCLUSAO = {
    "SST & eSocial": [
        r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
        r"\bPPRA\b", r"\bPGRTR\b", r"\bESOCIAL\b", r"\bE-SOCIAL\b",
        r"\bS-2210\b", r"\bS-2220\b", r"\bS-2240\b",
        r"SEGURANCA DO TRABALHO", r"ENGENHARIA DE SEGURANCA", r"SAUDE OCUPACIONAL",
        r"\bINSALUBRIDADE\b", r"\bPERICULOSIDADE\b", r"HIGIENE OCUPACIONAL",
        r"ANALISE ERGONOMICA", r"LAUDO ERGONOMICO", r"MAPA DE RISCO",
        r"ASSESSORIA.*SST", r"CONSULTORIA.*SST", r"GESTAO.*SST", r"\bDOSIMETRIA\b"
    ],
    "Treinamentos NRs & Brigada": [
        r"\bNR[- ]?0?1\b", r"\bNR[- ]?0?5\b", r"\bNR[- ]?0?6\b", r"\bNR[- ]?10\b",
        r"\bNR[- ]?11\b", r"\bNR[- ]?12\b", r"\bNR[- ]?13\b", r"\bNR[- ]?17\b",
        r"\bNR[- ]?20\b", r"\bNR[- ]?23\b", r"\bNR[- ]?33\b", r"\bNR[- ]?35\b",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*NR[- ]?\d+",
        r"TRABALHO EM ALTURA", r"ESPACO CONFINADO", r"\bCIPA\b", r"\bSIPAT\b",
        r"TREINAMENTO.*SEGURANCA.*TRABALHO", r"FORMACAO.*BRIGADA",
        r"TREINAMENTO.*BRIGADA", r"CAPACITACAO.*BRIGADA", r"CURSO.*BRIGADA",
        r"PRIMEIROS SOCORROS", r"ATENDIMENTO PRE[- ]?HOSPITALAR", r"\bAPH\b",
        r"\bSOCORRISTA\b", r"\bDESFIBRILADOR\b", r"\bDEA\b", r"\bHELIPONTO\b"
    ],
    "Engenharia Mecânica & AVCB/PMOC": [
        r"\bAVCB\b", r"\bCLCB\b", r"AUTO DE VISTORIA DO CORPO DE BOMBEIROS",
        r"REGULARIZACAO.*BOMBEIRO", r"PROJETO TECNICO.*INCENDIO",
        r"ADEQUACAO.*MAQUINA", r"APRECIACAO DE RISCO", r"ART.*MECANICA", r"LAUDO MECANICO",
        r"INSPECAO MECANICA", r"ENGENHARIA MECANICA",
        r"LINHA DE VIDA", r"PONTO DE ANCORAGEM", r"TESTE DE ARRANCAMENTO",
        r"\bCALDEIRA[S]?\b", r"VASO[S]? DE PRESSAO", r"COMPRESSOR DE AR", r"INSPECAO.*NR[- ]?13",
        r"\bPMOC\b", r"PLANO DE MANUTENCAO.*OPERACAO.*CONTROLE",
        r"LAUDO.*PLAYGROUND", r"INSPECAO.*PLAYGROUND", r"LAUDO.*BRINQUEDO"
    ]
}

# ==============================================================================
# TERMOS PROIBIDOS: BLOQUEIO DE ENGENHARIA CIVIL, AR-CONDICIONADO E RUÍDO
# ==============================================================================
TERMOS_PROIBIDOS = [
    # 1. Bloqueio Total de Engenharia Civil, Obras, Reformas e Infraestrutura
    r"ENGENHARIA CIVIL", r"OBRA[S]? PUBLICA", r"EXECUCAO DE OBRA", r"SERVICOS DE ENGENHARIA CIVIL",
    r"\bREFORMA\b", r"\bAMPLIACAO\b", r"\bCONSTRUCAO\b", r"\bEDIFICACAO\b", r"\bEDIFICACOES\b",
    r"\bPAVIMENTACAO\b", r"\bRECAPEAMENTO\b", r"ASFALT", r"\bDRENAGEM\b", r"\bTERRAPLENAGEM\b",
    r"\bALVENARIA\b", r"\bFUNDACAO\b", r"CONCRETO ARMADO", r"ESTRUTURA METALICA",
    r"PROJETO ARQUITETONICO", r"PROJETO ESTRUTURAL", r"PROJETO HIDROSSANITARIO",
    r"LAUDO ESTRUTURAL", r"VISTORIA ESTRUTURAL", r"\bPATOLOGIA\b", r"\bFACHADA\b",
    r"\bTOPOGRAFIA\b", r"\bSONDAGEM\b", r"\bGEOTECNIA\b", r"\bIMPERMEABILIZACAO\b",
    r"\bTELHADO\b", r"COBERTURA METALICA", r"PINTURA PREDIAL", r"\bCALCADA\b", r"\bMURO\b",
    r"\bCRECHE\b", r"QUADRA POLIESPORTIVA", r"\bPONTE\b", r"\bVIADUTO\b",
    r"\bSANEAMENTO\b", r"REDE DE ESGOTO", r"REDE DE AGUA", r"\bSINAPI\b", r"\bBDI\b",
    r"TAMPAS DE BUEIRO", r"OBRA.*CIVIL", r"INSTALACAO ELETRICA", r"SUBESTACAO", r"\bSPDA\b",

    # 2. Bloqueio de Ar-Condicionado (Compra, Instalação, Troca de Peças e Limpeza)
    r"AQUISICAO DE AR[- ]?CONDICIONADO", r"COMPRA DE AR[- ]?CONDICIONADO",
    r"INSTALACAO DE AR[- ]?CONDICIONADO", r"MANUTENCAO.*AR[- ]?CONDICIONADO",
    r"CONSERTO.*AR[- ]?CONDICIONADO", r"REPARO.*AR[- ]?CONDICIONADO",
    r"HIGIENIZACAO.*AR", r"LIMPEZA.*AR[- ]?CONDICIONADO", r"LIMPEZA DE DUTOS",
    r"GAS REFRIGERANTE", r"APARELHO.*SPLIT", r"\bREFRIGERACAO\b", r"\bCLIMATIZACAO\b",

    # 3. Bloqueio de Extintores, Mangueiras, Locação de CT e Bombeiro Civil
    r"\bEXTINTOR", r"\bRECARGA\b", r"MANGUEIRA.*INCEND", r"\bHIDRANTE",
    r"CENTRO.*TREINAMENTO", r"LOCACAO.*CENTRO", r"CAMPO.*TREINAMENTO",
    r"POSTO.*BOMBEIRO", r"BOMBEIRO.*CIVIL", r"DETECCAO.*ALARME",

    # 4. Bloqueio de Materiais, EPIs, Locação e Facilities
    r"\bTENIS\b", r"\bSAPATO\b", r"\bBOTINA\b", r"\bUNIFORME", r"\bCAFE\b", r"\bACUCAR\b", r"\bPAO\b",
    r"ALIMENTIC", r"GENEROS", r"HOSPITALAR", r"MEDICAMENTO", r"\bSERINGA", r"\bIMPRESSORA",
    r"\bCOMPUTADOR", r"\bCADEIRA", r"\bVEICULO", r"\bTRATOR", r"\bSUCATA", r"\bPISCINA",
    r"\bZELADORIA\b", r"\bJARDINAGEM\b", r"SEGURANCA ARMADA", r"\bVIGILANCIA\b", r"\bGASOLINA\b", r"\bDIESEL\b",
    r"\bROCAGEM\b", r"\bVARRECAO\b", r"\bLIXO\b", r"AQUISICAO.*EPI", r"FORNECIMENTO.*EPI", r"COMPRA.*EPI",
    r"MANUTENCAO DE ELEVADOR", r"CONSERVACAO DE ELEVADOR"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def validar_regiao(municipio_orgao: str, nome_orgao: str) -> tuple[bool, str]:
    mun_clean = remover_acentos(municipio_orgao).strip()
    org_clean = remover_acentos(nome_orgao).strip()

    if mun_clean:
        for cid in CIDADES_CLEAN:
            if cid == mun_clean or cid in mun_clean:
                return True, cid
        return False, ""

    for cid in CIDADES_CLEAN:
        if cid in org_clean:
            return True, cid

    return False, ""

def classificar_objeto(objeto_texto: str) -> tuple[bool, str]:
    texto = remover_acentos(objeto_texto)
    if not texto:
        return False, ""

    # 1. Barreira de bloqueio rígido
    for termo_proibido in TERMOS_PROIBIDOS:
        if re.search(termo_proibido, texto, re.IGNORECASE):
            return False, ""

    # 2. Exceção inteligente para PMOC puro
    if re.search(r"\bPMOC\b|PLANO DE MANUTENCAO.*OPERACAO.*CONTROLE", texto, re.IGNORECASE):
        return True, "Engenharia Mecânica & AVCB/PMOC"

    # 3. Classificação por área de negócio da TM Engenharia
    for categoria, padroes in REGRAS_INCLUSAO.items():
        for padrao in padroes:
            if re.search(padrao, texto, re.IGNORECASE):
                return True, categoria

    return False, ""

def faxinar_base_json(arquivo_json="licitacoes.json", arquivo_descartados="descartados.json"):
    """Remove do licitacoes.json qualquer item fora do escopo SST/Mecânica ou expirado."""
    ids_descartados = set()
    if os.path.exists(arquivo_descartados):
        try:
            with open(arquivo_descartados, "r", encoding="utf-8") as f:
                ids_descartados = set(json.load(f))
        except Exception:
            pass

    historico = []
    if os.path.exists(arquivo_json):
        try:
            with open(arquivo_json, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except Exception:
            historico = []

    agora = datetime.now()
    lista_limpa = []
    ids_vistos = set()

    for item in historico:
        id_lic = item.get("id")
        if not id_lic or id_lic in ids_descartados or id_lic in ids_vistos:
            continue

        valido, categoria = classificar_objeto(item.get("objeto", ""))
        eh_regiao, _ = validar_regiao(item.get("cidade", ""), item.get("orgao", ""))
        if not (valido and eh_regiao):
            continue

        dt_fim_str = item.get("data_fim") or ""
        if dt_fim_str:
            try:
                dt_fim = datetime.fromisoformat(str(dt_fim_str).replace("Z", "+00:00"))
                dt_agora = datetime.now(dt_fim.tzinfo) if dt_fim.tzinfo else agora
                if dt_fim < dt_agora:
                    continue
            except Exception:
                pass

        item["categoria"] = categoria
        ids_vistos.add(id_lic)
        lista_limpa.append(item)

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(lista_limpa, f, ensure_ascii=False, indent=4)

    return len(lista_limpa)

def edital_esta_aberto(edital: dict) -> bool:
    situacao_nome = str(edital.get("situacaoCompraNome") or edital.get("status") or "").upper()
    termos_encerrados = ["CONCLUÍDA", "CONCLUIDA", "HOMOLOGADA", "ANULADA", "REVOGADA", "ENCERRADA", "CANCELADA"]
    if any(termo in situacao_nome for termo in termos_encerrados):
        return False

    dt_fim_str = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or edital.get("dataAberturaProposta")
    if dt_fim_str:
        try:
            dt_fim = datetime.fromisoformat(str(dt_fim_str).replace("Z", "+00:00"))
            dt_agora = datetime.now(dt_fim.tzinfo) if dt_fim.tzinfo else datetime.now()
            if dt_fim < dt_agora:
                return False
        except Exception:
            pass
    else:
        dt_pub_str = edital.get("dataPublicacaoPncp") or edital.get("dataInclusao")
        if dt_pub_str:
            try:
                dt_pub = datetime.fromisoformat(str(dt_pub_str).replace("Z", "+00:00"))
                dt_agora = datetime.now(dt_pub.tzinfo) if dt_pub.tzinfo else datetime.now()
                if (dt_agora - dt_pub).days > 30:
                    return False
            except Exception:
                pass

    return True

def enviar_planilha(orgao, valor, objeto, link):
    try:
        requests.get(URL_PLANILHA_TM, params={
            "tipo": "sheet", "orgao": orgao, "valor": str(valor),
            "objeto": objeto, "escopo": objeto, "pncp": link
        }, timeout=2.0)
    except Exception:
        pass

def enviar_telegram(mensagem: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}, timeout=2.0)
    except Exception:
        pass

def fazer_requisicao_humana(url, params):
    for tentativa in range(1, 4):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=12.0, verify=False)
            if resp.status_code in [200, 204]:
                return resp
            elif resp.status_code == 429:
                tempo_espera = random.uniform(8.0, 14.0) * tentativa
                print(f"   ⏳ [Simulador Humano] Rate Limit detectado. Pausa tática de {tempo_espera:.1f}s...", flush=True)
                time.sleep(tempo_espera)
            else:
                print(f"   ⚠️ Resposta HTTP: {resp.status_code}", flush=True)
                break
        except Exception as e:
            print(f"   ⚠️ Falha temporária na rede: {e}", flush=True)
            time.sleep(random.uniform(2.0, 4.0))
    return None

def processar_edital(edital, ids_processados, stop_loss, oportunidades_novas, origem_tag=""):
    if not edital_esta_aberto(edital):
        return

    orgao_info = edital.get("orgaoEntidade", {})
    unidade_info = edital.get("unidadeOrgao", {})
    orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "ÓRGÃO PÚBLICO").upper()
    municipio_orgao = str(
        unidade_info.get("municipioNome")
        or orgao_info.get("municipioNome")
        or edital.get("municipioNome")
        or ""
    ).upper()

    eh_da_regiao, cidade_identificada = validar_regiao(municipio_orgao, orgao_nome)
    if not eh_da_regiao:
        return

    objeto = edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or ""
    valido, categoria = classificar_objeto(objeto)
    if not valido:
        return

    cnpj = re.sub(r"\D", "", str(orgao_info.get("cnpj") or edital.get("cnpjOrgao") or ""))
    ano = edital.get("anoCompra") or edital.get("anoContratacao")
    seq = edital.get("sequencialCompra") or edital.get("sequencialContratacao")

    id_unico = f"{cnpj}_{ano}_{seq}" if (cnpj and ano and seq) else str(hash(objeto))
    if id_unico in ids_processados:
        return
    ids_processados.add(id_unico)

    valor_estimado = float(edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0)
    if stop_loss and hasattr(stop_loss, 'validar_lance') and valor_estimado > 0:
        if not stop_loss.validar_lance(valor_estimado):
            return

    link_direto = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else "https://pncp.gov.br"
    txt_valor = f"R$ {valor_estimado:,.2f}" if valor_estimado > 0 else "Sob Consulta em Edital"
    dt_fim_prop = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or edital.get("dataAberturaProposta") or ""

    print(f"   🎯 [{categoria}] ({cidade_identificada}): {orgao_nome[:35]} | {txt_valor}", flush=True)

    enviar_planilha(orgao_nome, valor_estimado, f"[{categoria}] {objeto}", link_direto)
    enviar_telegram(
        f"🔥 *OPORTUNIDADE {categoria.upper()}*{origem_tag}\n\n"
        f"🏢 *Órgão:* {orgao_nome}\n"
        f"📍 *Cidade:* {cidade_identificada}\n"
        f"💰 *Valor Estimado:* {txt_valor}\n"
        f"📝 *Objeto:* _{objeto[:200]}_\n\n"
        f"🔗 [Acessar Edital]({link_direto})"
    )

    oportunidades_novas.append({
        "id": id_unico,
        "categoria": categoria,
        "orgao": orgao_nome,
        "valor": valor_estimado,
        "objeto": objeto,
        "cidade": cidade_identificada,
        "link_edital": link_direto,
        "data_fim": dt_fim_prop
    })

def executar():
    print("==================================================================")
    print("🚀 MINERADOR TM ENGENHARIA: SST & ENGENHARIA MECÂNICA (BLINDADO)")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    hoje = datetime.now()
    dt_inicio = (hoje - timedelta(days=30)).strftime("%Y%m%d")
    dt_fim = (hoje + timedelta(days=60)).strftime("%Y%m%d")

    oportunidades_novas = []
    ids_processados = set()

    modalidades = [8, 6, 9, 4, 5, 7]
    for mod in modalidades:
        print(f"\n🔍 [ETAPA 1/2] Lendo Modalidade PNCP: {mod} em SP...", flush=True)
        pagina = 1
        total_paginas = 1

        while pagina <= total_paginas:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
            params = {
                "dataInicial": dt_inicio,
                "dataFinal": dt_fim,
                "codigoModalidadeContratacao": mod,
                "uf": "SP",
                "pagina": pagina,
                "tamanhoPagina": 50
            }

            resp = fazer_requisicao_humana(url, params)
            if not resp or resp.status_code == 204:
                break

            dados = resp.json()
            lista = dados.get("data", []) if isinstance(dados, dict) else []
            if isinstance(dados, dict) and "totalPaginas" in dados:
                total_paginas = int(dados.get("totalPaginas") or 1)
            if not lista:
                break

            print(f"   ↳ Mod. {mod} (Pág. {pagina}/{total_paginas}): {len(lista)} editais lidos...", flush=True)
            for edital in lista:
                processar_edital(edital, ids_processados, stop_loss, oportunidades_novas)

            pagina += 1
            time.sleep(random.uniform(1.8, 3.6))
        time.sleep(random.uniform(3.0, 5.0))

    print("\n🔍 [ETAPA 2/2] Mineração por Códigos CATSER de SST & Mecânica...", flush=True)
    for catser in CODIGOS_CATSER_TM:
        pagina = 1
        total_paginas_catser = 1

        while pagina <= total_paginas_catser:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
            params = {
                "codigoItemCatalogo": catser,
                "uf": "SP",
                "pagina": pagina,
                "tamanhoPagina": 50
            }

            resp = fazer_requisicao_humana(url, params)
            if not resp or resp.status_code == 204:
                break

            dados = resp.json()
            lista = dados.get("data", []) if isinstance(dados, dict) else []
            if isinstance(dados, dict) and "totalPaginas" in dados:
                total_paginas_catser = int(dados.get("totalPaginas") or 1)
            if not lista:
                break

            print(f"   ↳ CATSER {catser} (Pág. {pagina}/{total_paginas_catser}): {len(lista)} editais lidos...", flush=True)
            for edital in lista:
                processar_edital(edital, ids_processados, stop_loss, oportunidades_novas, f" (CATSER {catser})")

            pagina += 1
            time.sleep(random.uniform(1.8, 3.6))
        time.sleep(random.uniform(3.0, 5.0))

    ARQUIVO_JSON = "licitacoes.json"
    historico_existente = []
    if os.path.exists(ARQUIVO_JSON):
        try:
            with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
                historico_existente = json.load(f)
        except Exception:
            historico_existente = []

    mapa_licitacoes = {item["id"]: item for item in historico_existente}
    for op in oportunidades_novas:
        mapa_licitacoes[op["id"]] = op

    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(list(mapa_licitacoes.values()), f, ensure_ascii=False, indent=4)

    total_limpo = faxinar_base_json(ARQUIVO_JSON)

    print("\n==================================================================")
    print("✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"📌 Novas Oportunidades Encontradas Hoje: {len(oportunidades_novas)}")
    print(f"🏆 Total de Oportunidades Puras (SST/Mecânica) no Cockpit: {total_limpo}")
    print("==================================================================")

if __name__ == "__main__":
    executar()
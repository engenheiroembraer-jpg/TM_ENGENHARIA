import os
import re
import time
import json
import random
import hashlib
import unicodedata
import requests
from datetime import datetime, timedelta, timezone

try:
    from stoplossmanager import StopLossManager
except ImportError:
    StopLossManager = None

# ==============================================================================
# CONFIGURAÇÕES GERAIS (PRODUÇÃO — PRONTO PARA GITHUB ACTIONS)
# ==============================================================================
URL_PNCP = "https://pncp.gov.br"
URL_PLANILHA_TM = os.getenv(
    "URL_PLANILHA_TM",
    "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"
)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7193404104")

# ==============================================================================
# CÓDIGOS CATSER ESTRITOS (SST, VISTORIA/AVCB, TREINAMENTOS NR E MECÂNICA)
# ==============================================================================
CODIGOS_CATSER_TM = [
    8818,    # Serviços de Engenharia de Segurança do Trabalho
    16438,   # Treinamento e Capacitação Profissional (NRs, PEMT/PTA, NR-18, NR-35)
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
# REGRAS DE INCLUSÃO: SST, MECÂNICA, NR-18 / PLATAFORMA ELEVATÓRIA E METÁLICAS
# ==============================================================================
REGRAS_INCLUSAO = {
    "1. Laudos, Programas & Gestão SST": [
        r"\bLTCAT\b", r"\bPGR\b", r"\bGRO\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
        r"LAUDO.*INSALUBRIDADE", r"LAUDO.*PERICULOSIDADE",
        r"ADICIONAL DE INSALUBRIDADE", r"ADICIONAL DE PERICULOSIDADE",
        r"ANALISE ERGONOMICA", r"LAUDO ERGONOMICO",
        r"DOSIMETRIA DE RUIDO", r"AVALIACAO DE RUIDO", r"AVALIACAO AMBIENTAL.*TRABALHO",
        r"HIGIENE OCUPACIONAL", r"ENGENHARIA DE SEGURANCA DO TRABALHO",
        r"SEGURANCA E MEDICINA DO TRABALHO", r"SEGURANCA E SAUDE DO TRABALHO",
        r"(ELABORACAO|ATUALIZACAO|REVISAO|GESTAO|ASSESSORIA|CONSULTORIA).*SEGURANCA DO TRABALHO",
        r"(ELABORACAO|ATUALIZACAO|REVISAO|GESTAO|ASSESSORIA|CONSULTORIA).*SAUDE OCUPACIONAL",
        r"\bS-2210\b", r"\bS-2220\b", r"\bS-2240\b",
        r"(SST|SEGURANCA|SAUDE).*(ESOCIAL|E-SOCIAL)"
    ],
    "2. NR-18, Plataforma Elevatória (PEMT/PTA) & Treinamentos Técnicos": [
        r"\bNR[- ]?18\b",
        r"\bPCMAT\b",
        r"PGR.*CONSTRUCAO",
        r"PLATAFORMA[S]? ELEVATORIA[S]?",
        r"\bPEMT\b",
        r"\bPTA\b.*(PLATAFORMA|TRABALHO EM ALTURA|NR[- ]?18|OPERADOR)",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*PLATAFORMA",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?18",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?35",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?11",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?12",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?10",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM).*NR[- ]?33",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*TRABALHO EM ALTURA",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*ESPACO CONFINADO",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*EMPILHADEIRA",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*PONTE ROLANTE",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*MUNCK",
        r"(LAUDO|INSPECAO|PROJETO|DIMENSIONAMENTO|ART).*ANDAIME[S]?",
        r"(LAUDO|INSPECAO|PROJETO|DIMENSIONAMENTO|ART).*BALANCIM",
        r"(LAUDO|INSPECAO|PROJETO|ART).*GRUA[S]?",
        r"PLANO DE RIGGING", r"PLANO DE ICAMENTO"
    ],
    "3. AVCB / CLCB & Projetos de Incêndio": [
        r"\bAVCB\b", r"\bCLCB\b",
        r"AUTO DE VISTORIA DO CORPO DE BOMBEIROS",
        r"CERTIFICADO DE LICENCA DO CORPO DE BOMBEIROS",
        r"REGULARIZACAO.*CORPO DE BOMBEIROS",
        r"PROJETO TECNICO.*INCENDIO",
        r"(PROJETO|LAUDO|VISTORIA|REGULARIZACAO).*PREVENCAO.*INCENDIO"
    ],
    "4. PMOC & Engenharia Mecânica (Laudos/NR-12/NR-13/Ancoragem)": [
        r"(ELABORACAO|IMPLEMENTACAO|ATUALIZACAO|GESTAO|LAUDO|ART|RESPONSABILIDADE TECNICA).*\bPMOC\b",
        r"\bPMOC\b",
        r"PLANO DE MANUTENCAO.*OPERACAO.*CONTROLE",
        r"(INSPECAO|LAUDO|ENSAIO|TESTE|ART|CERTIFICACAO).*NR[- ]?13",
        r"(INSPECAO|LAUDO|ENSAIO|TESTE|INTEGRIDADE).*\bCALDEIRA[S]?\b",
        r"(INSPECAO|LAUDO|ENSAIO|TESTE|INTEGRIDADE).*VASO[S]? DE PRESSAO",
        r"(INSPECAO|LAUDO|ENSAIO|TESTE).*COMPRESSOR",
        r"(ADEQUACAO|LAUDO|INVENTARIO|APRECIACAO DE RISCO|ANALISE DE RISCO|DIAGNOSTICO).*NR[- ]?12",
        r"ENGENHARIA MECANICA",
        r"(INSPECAO|LAUDO|PERICIA|VISTORIA|ART).*MECANIC[OA]",
        r"(INSPECAO|LAUDO|TESTE|PROJETO|DIMENSIONAMENTO).*LINHA DE VIDA",
        r"(INSPECAO|LAUDO|TESTE|PROJETO|DIMENSIONAMENTO).*PONTO[S]? DE ANCORAGEM",
        r"(INSPECAO|LAUDO|TESTE|PROJETO).*ANCORAGEM.*NR[- ]?35",
        r"TESTE DE ARRANCAMENTO",
        r"(LAUDO|INSPECAO|VISTORIA).*PLAYGROUND",
        r"(LAUDO|INSPECAO|VISTORIA).*BRINQUEDO[S]?"
    ],
    "5. Projetos & Laudos de Estrutura Metálica": [
        r"(PROJETO|CALCULO|LAUDO|INSPECAO|VISTORIA|PERICIA|DIAGNOSTICO|REFORCO).*ESTRUTURA[S]? METALICA[S]?",
        r"ESTRUTURA[S]? METALICA[S]?.*(PROJETO|CALCULO|LAUDO|INSPECAO|VISTORIA|PERICIA)"
    ]
}

# ==============================================================================
# EXCEÇÕES DE SALVAMENTO: SE CITAR ISSO, NÃO BLOQUEIA MESMO EM AMBIENTE DE OBRA
# ==============================================================================
EXCECOES_OBRA_SEGURANCA = [
    r"\bNR[- ]?18\b", r"\bPCMAT\b", r"PLATAFORMA[S]? ELEVATORIA[S]?", r"\bPEMT\b",
    r"LINHA DE VIDA", r"PONTO[S]? DE ANCORAGEM", r"TESTE DE ARRANCAMENTO",
    r"PLANO DE RIGGING", r"PLANO DE ICAMENTO", r"SEGURANCA DO TRABALHO"
]

# ==============================================================================
# TERMOS PROIBIDOS: MURALHA CONTRA RUÍDO (OBRAS COMUNS, BRAÇAL, COMPRAS E FACILITIES)
# ==============================================================================
TERMOS_PROIBIDOS_OBRA_CIVIL = [
    r"ENGENHARIA CIVIL", r"OBRA[S]? PUBLICA", r"EXECUCAO DE OBRA", r"SERVICOS DE ENGENHARIA CIVIL",
    r"\bREFORMA\b", r"\bAMPLIACAO\b", r"\bCONSTRUCAO\b", r"\bEDIFICACAO\b", r"\bEDIFICACOES\b",
    r"\bPAVIMENTACAO\b", r"\bRECAPEAMENTO\b", r"ASFALT", r"\bDRENAGEM\b", r"\bTERRAPLENAGEM\b",
    r"\bALVENARIA\b", r"\bFUNDACAO\b", r"CONCRETO ARMADO",
    r"PROJETO ARQUITETONICO", r"PROJETO HIDROSSANITARIO",
    r"LAUDO ESTRUTURAL.*CONCRETO", r"\bPATOLOGIA\b", r"\bFACHADA\b",
    r"\bTOPOGRAFIA\b", r"\bSONDAGEM\b", r"\bGEOTECNIA\b", r"\bIMPERMEABILIZACAO\b",
    r"\bTELHADO\b", r"PINTURA PREDIAL", r"\bCALCADA\b", r"\bMURO\b",
    r"\bCRECHE\b", r"QUADRA POLIESPORTIVA", r"\bPONTE\b", r"\bVIADUTO\b",
    r"\bSANEAMENTO\b", r"REDE DE ESGOTO", r"REDE DE AGUA", r"\bSINAPI\b", r"\bBDI\b",
    r"TAMPAS DE BUEIRO", r"OBRA.*CIVIL", r"INSTALACAO ELETRICA", r"SUBESTACAO", r"\bSPDA\b"
]

TERMOS_PROIBIDOS_GERAIS = [
    # 1. Bloqueio de Manutenção Física/Corretiva de Ar-Condicionado, Peças e Frota
    r"MANUTENCAO PREVENTIVA E CORRETIVA", r"MANUTENCAO CORRETIVA",
    r"FORNECIMENTO DE PECAS", r"REPOSICAO DE PECAS", r"TROCA DE PECAS",
    r"AQUISICAO DE AR[- ]?CONDICIONADO", r"COMPRA DE AR[- ]?CONDICIONADO",
    r"INSTALACAO DE AR[- ]?CONDICIONADO", r"MANUTENCAO.*AR[- ]?CONDICIONADO",
    r"CONSERTO.*AR[- ]?CONDICIONADO", r"REPARO.*AR[- ]?CONDICIONADO",
    r"INSTALACAO.*SISTEMA[S]? DE REFRIGERACAO", r"MONTAGEM.*SISTEMA[S]? DE REFRIGERACAO",
    r"MANUTENCAO.*SISTEMA[S]? DE REFRIGERACAO",
    r"HIGIENIZACAO.*AR", r"LIMPEZA.*AR[- ]?CONDICIONADO", r"LIMPEZA DE DUTOS",
    r"GAS REFRIGERANTE", r"APARELHO.*SPLIT",
    r"LOCACAO DE PLATAFORMA", r"ALUGUEL DE PLATAFORMA", r"AQUISICAO DE PLATAFORMA", r"COMPRA DE PLATAFORMA",
    r"MANUTENCAO DE MAQUINA", r"CONSERTO DE MAQUINA", r"REPARO DE MAQUINA",
    r"MANUTENCAO DE VEICULO", r"\bFROTA\b", r"MECANICA AUTOMOTIVA", r"AUTO MECANICA",
    r"PECAS AUTOMOTIVAS", r"\bPNEU[S]?\b", r"OLEO LUBRIFICANTE",

    # 2. Bloqueio de Terceirização de Mão de Obra, Postos e Bombeiro Civil
    r"POSTO[S]? DE TRABALHO", r"MAO DE OBRA RESIDENTE", r"DEDICACAO EXCLUSIVA",
    r"LOCACAO DE MAO DE OBRA", r"CESSAO DE MAO DE OBRA", r"PROFISSIONAL RESIDENTE",
    r"POSTO.*BOMBEIRO", r"BOMBEIRO.*CIVIL", r"CONTRATACAO DE BRIGADISTA",
    r"\bRECEPCIONISTA\b", r"\bPORTEIRO\b", r"\bMOTORISTA\b", r"\bCOPEIRA\b",

    # 3. Bloqueio de Instalação/Manutenção de Extintores, Alarmes e Hidrantes
    r"\bEXTINTOR", r"\bRECARGA\b", r"MANGUEIRA.*INCEND", r"\bHIDRANTE",
    r"DETECCAO.*ALARME", r"MONITORIZACAO.*ALARME", r"INSTALACAO.*ALARME",
    r"INSTALACAO.*PROTECAO CONTRA INCENDIO", r"MONTAGEM.*PROTECAO CONTRA INCENDIO",
    r"MANUTENCAO.*PROTECAO CONTRA INCENDIO", r"MANUTENCAO.*COMBATE A INCENDIO",
    r"INSTALACAO DE SISTEMA DE COMBATE A INCENDIO",
    r"MANUTENCAO DE SISTEMA DE COMBATE A INCENDIO",

    # 4. Bloqueio de Materiais, EPIs, Medicina Assistencial, Limpeza e Elevadores
    r"\bTENIS\b", r"\bSAPATO\b", r"\bBOTINA\b", r"\bUNIFORME", r"\bCAFE\b", r"\bACUCAR\b", r"\bPAO\b",
    r"ALIMENTIC", r"GENEROS", r"HOSPITALAR", r"MEDICAMENTO", r"\bSERINGA", r"\bIMPRESSORA",
    r"\bCOMPUTADOR", r"\bNOTEBOOK\b", r"\bCADEIRA", r"\bMOBILIARIO\b", r"\bVEICULO", r"\bTRATOR",
    r"\bSUCATA", r"\bPISCINA", r"\bZELADORIA\b", r"\bJARDINAGEM\b", r"SEGURANCA ARMADA",
    r"\bVIGILANCIA\b", r"\bGASOLINA\b", r"\bDIESEL\b", r"\bCOMBUSTIVEL\b",
    r"\bROCAGEM\b", r"\bVARRECAO\b", r"COLETA DE LIXO", r"\bDEDETIZACAO\b", r"\bLIMPEZA PREDIAL\b",
    r"AQUISICAO.*EPI", r"FORNECIMENTO.*EPI", r"COMPRA.*EPI",
    r"MANUTENCAO DE ELEVADOR", r"CONSERVACAO DE ELEVADOR", r"MODERNIZACAO.*ELEVADOR",
    r"EXAME LABORATORIAL", r"CLINICA MEDICA", r"CONSULTA MEDICA", r"ATENDIMENTO MEDICO",
    r"\bODONTOLOG", r"\bENFERMAGEM\b", r"\bFISIOTERAPIA\b",

    # 5. Bloqueio de Eventos, Transporte, Contabilidade, Jurídico, TI e Insumos
    r"\bBUFFET\b", r"\bCOFFEE BREAK\b", r"\bPALESTRANTE\b", r"\bCONGRESSO\b", r"\bSONORIZACAO\b",
    r"TRANSPORTE.*(ESTUDANTE|ESCOLAR|ALUNO|DOCENTE|PASSAGEIRO)",
    r"\bDIRF\b", r"\bEFD[- ]?REINF\b", r"\bCONTABIL", r"\bTRIBUTAR", r"\bFOLHA DE PAGAMENTO\b",
    r"ASSESSORIA JURIDICA", r"CONSULTORIA JURIDICA", r"\bADVOCACIA\b",
    r"LICENCA DE SOFTWARE", r"LINK DE INTERNET", r"TELEFONIA",
    r"AQUISICAO DE INSUMO", r"COMPRA DE INSUMO", r"FORNECIMENTO DE INSUMO",
    r"AQUISICAO DE MATERIAL", r"COMPRA DE MATERIAL", r"FORNECIMENTO DE MATERIAL",
    r"ENERGIA NUCLEAR", r"\bRADIOLOGIA\b"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def gerar_id_deterministico(cnpj: str, ano, seq, objeto: str, municipio: str) -> str:
    if cnpj and ano and seq:
        return f"{cnpj}_{ano}_{seq}"
    chave_base = f"{remover_acentos(municipio)}|{remover_acentos(objeto)[:250]}"
    digest = hashlib.sha256(chave_base.encode("utf-8")).hexdigest()[:16]
    return f"PNCP_{digest}"

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

def classificar_objeto(objeto_texto: str, itens_texto: str = "") -> tuple[bool, str]:
    obj_clean = remover_acentos(objeto_texto)
    itens_clean = remover_acentos(itens_texto)
    texto_avaliado = f"{obj_clean} {itens_clean}".strip()

    if not texto_avaliado:
        return False, ""

    # 1. Bloqueio absoluto de ruído geral (compras, manutenção braçal, facilities, posto)
    for termo_proibido in TERMOS_PROIBIDOS_GERAIS:
        if re.search(termo_proibido, texto_avaliado, re.IGNORECASE):
            return False, ""

    # 2. Bloqueio de obra civil comum, EXCETO se envolver NR-18, PEMT, ancoragem ou rigging
    tem_excecao_seguranca = any(
        re.search(exc, texto_avaliado, re.IGNORECASE) for exc in EXCECOES_OBRA_SEGURANCA
    )
    if not tem_excecao_seguranca:
        for termo_obra in TERMOS_PROIBIDOS_OBRA_CIVIL:
            if re.search(termo_obra, texto_avaliado, re.IGNORECASE):
                return False, ""

    # 3. Classificação estrita por frente intelectual & treinamentos técnicos
    for categoria, padroes in REGRAS_INCLUSAO.items():
        for padrao in padroes:
            if re.search(padrao, texto_avaliado, re.IGNORECASE):
                return True, categoria

    return False, ""

def _parse_data_segura(data_str: str):
    if not data_str:
        return None
    try:
        dt = datetime.fromisoformat(str(data_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))
        return dt
    except Exception:
        return None

def edital_esta_aberto(edital: dict) -> tuple[bool, str]:
    """Garante rigorosamente que o edital ainda está aberto para disputa ou envio de proposta."""
    situacao_id = edital.get("situacaoCompraId")
    if situacao_id is not None:
        try:
            if int(situacao_id) != 1:
                return False, ""
        except (ValueError, TypeError):
            pass

    situacao_nome = remover_acentos(str(edital.get("situacaoCompraNome") or edital.get("status") or ""))
    termos_encerrados = [
        "CONCLUIDA", "CONCLUIDO", "HOMOLOGADA", "HOMOLOGADO",
        "ANULADA", "ANULADO", "REVOGADA", "REVOGADO",
        "ENCERRADA", "ENCERRADO", "CANCELADA", "CANCELADO",
        "SUSPENSA", "SUSPENSO", "DESERTA", "FRACASSADA", "ADJUDICADA"
    ]
    if any(termo in situacao_nome for termo in termos_encerrados):
        return False, ""

    agora = datetime.now(timezone(timedelta(hours=-3)))

    dt_fim_prop = _parse_data_segura(
        edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta")
    )
    dt_abertura = _parse_data_segura(edital.get("dataAberturaProposta"))

    if dt_fim_prop:
        if dt_fim_prop <= (agora + timedelta(minutes=15)):
            return False, ""
        return True, dt_fim_prop.isoformat()

    if dt_abertura:
        if dt_abertura <= (agora + timedelta(minutes=15)):
            return False, ""
        return True, dt_abertura.isoformat()

    dt_pub = _parse_data_segura(edital.get("dataPublicacaoPncp") or edital.get("dataInclusao"))
    if dt_pub and (agora - dt_pub).days <= 25:
        return True, ""

    return False, ""

def faxinar_base_json(arquivo_json="licitacoes.json", arquivo_descartados="descartados.json"):
    """Remove do licitacoes.json qualquer item fora do escopo, encerrado ou vencido."""
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

    agora = datetime.now(timezone(timedelta(hours=-3)))
    lista_limpa = []
    ids_vistos = set()

    for item in historico:
        id_lic = item.get("id")
        if not id_lic or id_lic in ids_descartados or id_lic in ids_vistos:
            continue

        valido, categoria = classificar_objeto(item.get("objeto", ""), item.get("itens_resumo", ""))
        eh_regiao, _ = validar_regiao(item.get("cidade", ""), item.get("orgao", ""))
        if not (valido and eh_regiao):
            continue

        dt_fim = _parse_data_segura(item.get("data_fim") or "")
        if dt_fim:
            if dt_fim <= (agora + timedelta(minutes=15)):
                continue
        else:
            dt_cap = _parse_data_segura(item.get("data_captura") or "")
            if not dt_cap or (agora - dt_cap).days > 10:
                continue

        item["categoria"] = categoria
        ids_vistos.add(id_lic)
        lista_limpa.append(item)

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(lista_limpa, f, ensure_ascii=False, indent=4)

    return len(lista_limpa)

def enviar_planilha(orgao: str, valor: float, objeto: str, link: str):
    try:
        requests.get(
            URL_PLANILHA_TM,
            params={
                "tipo": "sheet", "orgao": orgao, "valor": str(valor),
                "objeto": objeto, "escopo": objeto, "pncp": link
            },
            timeout=4.0
        )
    except Exception:
        pass

def enviar_telegram(mensagem: str):
    if not TELEGRAM_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"},
            timeout=4.0
        )
    except Exception:
        pass

def fazer_requisicao_humana(url: str, params: dict = None, max_tentativas: int = 3, timeout_req: float = 14.0, silencioso: bool = False):
    for tentativa in range(1, max_tentativas + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout_req, verify=True)
            if resp.status_code in [200, 204]:
                return resp
            elif resp.status_code == 429:
                tempo_espera = random.uniform(6.0, 12.0) * tentativa
                if not silencioso:
                    print(f"   ⏳ [Simulador Humano] Rate Limit (429). Pausa de {tempo_espera:.1f}s...", flush=True)
                time.sleep(tempo_espera)
            else:
                if not silencioso:
                    print(f"   ⚠️ Resposta HTTP {resp.status_code} em {url}", flush=True)
                break
        except Exception as e:
            if not silencioso:
                print(f"   ⚠️ Falha temporária na rede: {e}", flush=True)
            if tentativa < max_tentativas:
                time.sleep(random.uniform(1.5, 3.0))
    return None

def buscar_descricao_itens_pncp(cnpj: str, ano, seq) -> str:
    """Consulta rápida (1 tentativa) dos itens da compra para validar objetos genéricos."""
    if not (cnpj and ano and seq):
        return ""
    url_itens = f"{URL_PNCP}/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    resp = fazer_requisicao_humana(
        url_itens,
        params={"pagina": 1, "tamanhoPagina": 15},
        max_tentativas=1,
        timeout_req=4.0,
        silencioso=True
    )
    if not resp or resp.status_code != 200:
        return ""
    try:
        dados = resp.json()
        lista_itens = dados if isinstance(dados, list) else dados.get("data", [])
        descricoes = [
            str(it.get("descricao") or it.get("materialOuServicoNome") or "").strip()
            for it in lista_itens[:15]
        ]
        return " ; ".join([d for d in descricoes if d])
    except Exception:
        return ""

def processar_edital(edital, ids_processados, stop_loss, oportunidades_novas, origem_tag=""):
    aberto, data_limite_iso = edital_esta_aberto(edital)
    if not aberto:
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

    cnpj = re.sub(r"\D", "", str(orgao_info.get("cnpj") or edital.get("cnpjOrgao") or ""))
    ano = edital.get("anoCompra") or edital.get("anoContratacao")
    seq = edital.get("sequencialCompra") or edital.get("sequencialContratacao")
    objeto = edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or ""

    id_unico = gerar_id_deterministico(cnpj, ano, seq, objeto, cidade_identificada)
    if id_unico in ids_processados:
        return
    ids_processados.add(id_unico)

    valido, categoria = classificar_objeto(objeto)
    itens_texto = ""

    obj_norm = remover_acentos(objeto)
    if not valido and any(k in obj_norm for k in [
        "ENGENHARIA", "LAUDO", "INSPECAO", "SEGURANCA", "MECANICA",
        "METALICA", "BOMBEIRO", "TREINAMENTO", "CAPACITACAO", "PLATAFORMA"
    ]):
        itens_texto = buscar_descricao_itens_pncp(cnpj, ano, seq)
        if itens_texto:
            valido, categoria = classificar_objeto(objeto, itens_texto)

    if not valido:
        return

    valor_estimado = float(edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0)
    if stop_loss and hasattr(stop_loss, "validar_lance") and valor_estimado > 0:
        if not stop_loss.validar_lance(valor_estimado):
            return

    link_direto = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else "https://pncp.gov.br"
    txt_valor = f"R$ {valor_estimado:,.2f}" if valor_estimado > 0 else "Sob Consulta em Edital"

    print(f"   🎯 [{categoria}] ({cidade_identificada}): {orgao_nome[:35]} | {txt_valor} | Fim: {data_limite_iso[:16]}", flush=True)

    enviar_planilha(orgao_nome, valor_estimado, f"[{categoria}] {objeto}", link_direto)
    enviar_telegram(
        f"🔥 *OPORTUNIDADE ABERTA — {categoria.upper()}*{origem_tag}\n\n"
        f"🏢 *Órgão:* {orgao_nome}\n"
        f"📍 *Cidade:* {cidade_identificada}\n"
        f"💰 *Valor Estimado:* {txt_valor}\n"
        f"⏳ *Encerramento:* {data_limite_iso[:16] if data_limite_iso else 'Dispensa Recente (ver edital)'}\n"
        f"📝 *Objeto:* _{objeto[:220]}_\n\n"
        f"🔗 [Acessar Edital]({link_direto})"
    )

    oportunidades_novas.append({
        "id": id_unico,
        "categoria": categoria,
        "orgao": orgao_nome,
        "valor": valor_estimado,
        "objeto": objeto,
        "itens_resumo": itens_texto[:400],
        "cidade": cidade_identificada,
        "link_edital": link_direto,
        "data_fim": data_limite_iso,
        "data_captura": datetime.now(timezone(timedelta(hours=-3))).isoformat()
    })

def executar():
    print("==================================================================")
    print("🚀 MINERADOR TM ENGENHARIA: SST, NR-18/PEMT, AVCB, MECÂNICA & METÁLICAS")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    hoje = datetime.now()
    dt_inicio = (hoje - timedelta(days=20)).strftime("%Y%m%d")
    dt_fim = (hoje + timedelta(days=60)).strftime("%Y%m%d")

    oportunidades_novas = []
    ids_processados = set()

    modalidades = [6, 8, 9, 4, 5, 7]
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
            time.sleep(random.uniform(1.2, 2.4))
        time.sleep(random.uniform(2.0, 3.5))

    print("\n🔍 [ETAPA 2/2] Mineração por Códigos CATSER (Apenas Vigentes)...", flush=True)
    for catser in CODIGOS_CATSER_TM:
        pagina = 1
        total_paginas_catser = 1

        while pagina <= total_paginas_catser:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
            params = {
                "dataInicial": dt_inicio,
                "dataFinal": dt_fim,
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
            time.sleep(random.uniform(1.2, 2.4))
        time.sleep(random.uniform(2.0, 3.5))

    ARQUIVO_JSON = "licitacoes.json"
    historico_existente = []
    if os.path.exists(ARQUIVO_JSON):
        try:
            with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
                historico_existente = json.load(f)
        except Exception:
            historico_existente = []

    mapa_licitacoes = {item["id"]: item for item in historico_existente if item.get("id")}
    for op in oportunidades_novas:
        mapa_licitacoes[op["id"]] = op

    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(list(mapa_licitacoes.values()), f, ensure_ascii=False, indent=4)

    total_limpo = faxinar_base_json(ARQUIVO_JSON)

    print("\n==================================================================")
    print("✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"📌 Novas Oportunidades Abertas Encontradas Hoje: {len(oportunidades_novas)}")
    print(f"🏆 Total de Oportunidades Ativas no Cockpit: {total_limpo}")
    print("==================================================================")

if __name__ == "__main__":
    executar()

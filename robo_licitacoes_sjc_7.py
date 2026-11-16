import os
import re
import time
import json
import random
import hashlib
import unicodedata
import requests
import urllib3
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from stoplossmanager import StopLossManager
except ImportError:
    StopLossManager = None

# ==============================================================================
# 1. CONFIGURAÇÕES GERAIS (PRODUÇÃO — PNCP /proposta + QUERIDO DIÁRIO)
# ==============================================================================
URL_PNCP = "https://pncp.gov.br"
URL_QUERIDO_DIARIO = "https://api.queridodiario.ok.org.br/gazettes"

URL_PLANILHA_TM = os.getenv(
    "URL_PLANILHA_TM",
    "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"
)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7193404104")

# Mapeamento Cidade -> Código IBGE (Querido Diário)
MUNICIPIOS_IBGE = {
    "SAO JOSE DOS CAMPOS": "3549904",
    "TAUBATE": "3554102",
    "JACAREI": "3524402",
    "PINDAMONHANGABA": "3538006",
    "GUARATINGUETA": "3518404",
    "CACAPAVA": "3508504",
    "LORENA": "3527207",
    "CRUZEIRO": "3513405",
    "CARAGUATATUBA": "3510500",
    "UBATUBA": "3555406",
    "SAO SEBASTIAO": "3550704",
    "ILHABELA": "3520400",
    "SAO PAULO": "3550308",
    "GUARULHOS": "3518800",
    "MOGI DAS CRUZES": "3530607",
    "SUZANO": "3552502",
    "SANTOS": "3548500",
}

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

QUERIES_DIARIO_OFICIAL = [
    '"NR-12" OR "NR 12" OR "segurança em máquinas"',
    '"NR-35" OR "NR 35" OR "linha de vida" OR "ancoragem"',
    '"LTCAT" OR "PGR" OR "engenharia de segurança do trabalho"',
    '"AVCB" OR "CLCB" OR "vistoria do corpo de bombeiros"',
    '"PMOC" OR "laudo técnico mecânico" OR "estrutura metálica"'
]

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

CIDADES_CLEAN = [remover_acentos(c) for c in CIDADES_ESCOPO]

# ==============================================================================
# 2. BLOQUEIOS E EXCEÇÕES CIRÚRGICAS
# ==============================================================================
TERMOS_PROIBIDOS_COMPRA = [
    r"\bAQUISICAO\b", r"\bCOMPRA DE\b", r"\bCOMPRAS DE\b",
    r"FORNECIMENTO DE MATERIAL", r"FORNECIMENTO DE EQUIPAMENTO",
    r"FORNECIMENTO DE PECAS", r"FORNECIMENTO DE INSUMO",
    r"FORNECIMENTO DE PRODUTO", r"FORNECIMENTO DE MOBILIARIO",
    r"FORNECIMENTO DE UNIFORME", r"FORNECIMENTO DE EPI",
    r"REGISTRO DE PRECOS PARA FUTURA AQUISICAO", r"REGISTRO DE PRECOS PARA AQUISICAO",
    r"EQUIPAMENTO[S]? DE LABORATORIO", r"REDE SEM FIO", r"\bWI[- ]?FI\b",
    r"\bROTEADOR", r"\bSWITCH\b", r"\bTECIDO[S]?\b", r"\bLONA[S]?\b",
    r"\bBANNER[S]?\b", r"PAINEL PERSONALIZADO", r"PAINEIS PERSONALIZADOS",
    r"\bSOFTWARE\b", r"\bLICENCA DE USO\b",
]

TERMOS_PROIBIDOS_OBRA_E_BRACAL = [
    # Obras, tubulação, hidráulica e civil
    r"ENGENHARIA CIVIL", r"OBRA[S]? PUBLICA", r"EXECUCAO DE OBRA", r"SERVICOS DE ENGENHARIA CIVIL",
    r"\bREFORMA\b", r"\bAMPLIACAO\b", r"\bCONSTRUCAO\b", r"\bEDIFICACAO\b", r"\bEDIFICACOES\b",
    r"\bPAVIMENTACAO\b", r"\bRECAPEAMENTO\b", r"ASFALT", r"\bDRENAGEM\b", r"\bTERRAPLENAGEM\b",
    r"\bALVENARIA\b", r"\bFUNDACAO\b", r"CONCRETO ARMADO", r"PROJETO ARQUITETONICO",
    r"PROJETO HIDROSSANITARIO", r"LAUDO ESTRUTURAL.*CONCRETO", r"\bPATOLOGIA\b", r"\bFACHADA\b",
    r"\bTOPOGRAFIA\b", r"\bSONDAGEM\b", r"\bGEOTECNIA\b", r"\bIMPERMEABILIZACAO\b",
    r"\bTELHADO\b", r"PINTURA PREDIAL", r"\bCALCADA\b", r"\bMURO\b", r"\bCRECHE\b",
    r"QUADRA POLIESPORTIVA", r"\bPONTE\b", r"\bVIADUTO\b", r"\bSANEAMENTO\b",
    r"REDE DE ESGOTO", r"REDE DE AGUA", r"\bSINAPI\b", r"\bBDI\b", r"TAMPAS DE BUEIRO",
    r"OBRA.*CIVIL", r"INSTALACAO ELETRICA", r"SUBESTACAO", r"\bSPDA\b",
    r"\bTUBULACAO\b", r"\bTUBULACOES\b", r"\bESCAVACAO\b", r"REDE ENTERRADA",
    r"MANUTENCAO HIDRAULICA", r"INSTALACAO HIDRAULICA", r"\bENCANAMENTO\b",

    # Terceirização de mão de obra operacional / braçal / postos fixos
    r"TERCEIRIZACAO DE MAO DE OBRA", r"POSTO[S]? DE TRABALHO", r"MAO DE OBRA RESIDENTE",
    r"DEDICACAO EXCLUSIVA", r"LOCACAO DE MAO DE OBRA", r"CESSAO DE MAO DE OBRA",
    r"PROFISSIONAL RESIDENTE", r"POSTO.*BOMBEIRO", r"BOMBEIRO.*CIVIL",
    r"CONTRATACAO DE BRIGADISTA", r"\bRECEPCIONISTA\b", r"\bPORTEIRO\b",
    r"\bMOTORISTA\b", r"\bCOPEIRA\b", r"SERVICOS GERAIS", r"\bAUXILIAR DE\b",
    r"\bAJUDANTE\b", r"\bPEDREIRO\b", r"\bSERVENTE\b", r"\bSOLDADOR\b", r"\bCALDEIREIRO\b",

    # NR-13 explicitamente excluída
    r"\bNR[- ]?13\b", r"\bCALDEIRA[S]?\b", r"VASO[S]? DE PRESSAO",

    # Manutenção física de ar-condicionado, máquinas, elevadores e frota
    r"MANUTENCAO PREVENTIVA E CORRETIVA", r"MANUTENCAO CORRETIVA",
    r"REPOSICAO DE PECAS", r"TROCA DE PECAS",
    r"INSTALACAO DE AR[- ]?CONDICIONADO", r"MANUTENCAO.*AR[- ]?CONDICIONADO",
    r"CONSERTO.*AR[- ]?CONDICIONADO", r"REPARO.*AR[- ]?CONDICIONADO",
    r"INSTALACAO.*REFRIGERACAO", r"MONTAGEM.*REFRIGERACAO", r"MANUTENCAO.*REFRIGERACAO",
    r"HIGIENIZACAO.*AR", r"LIMPEZA.*AR[- ]?CONDICIONADO", r"LIMPEZA DE DUTOS",
    r"GAS REFRIGERANTE", r"APARELHO.*SPLIT",
    r"LOCACAO DE PLATAFORMA", r"ALUGUEL DE PLATAFORMA",
    r"MANUTENCAO DE MAQUINA", r"CONSERTO DE MAQUINA", r"REPARO DE MAQUINA",
    r"MANUTENCAO DE VEICULO", r"\bFROTA\b", r"MECANICA AUTOMOTIVA", r"AUTO MECANICA",
    r"\bPNEU[S]?\b", r"OLEO LUBRIFICANTE",
    r"MANUTENCAO DE ELEVADOR", r"CONSERVACAO DE ELEVADOR", r"MODERNIZACAO.*ELEVADOR",

    # Extintores, alarmes, hidrantes, limpeza, eventos e outros ruídos
    r"\bEXTINTOR", r"\bRECARGA\b", r"MANGUEIRA.*INCEND", r"\bHIDRANTE",
    r"DETECCAO.*ALARME", r"MONITORIZACAO.*ALARME", r"INSTALACAO.*ALARME",
    r"INSTALACAO.*PROTECAO CONTRA INCENDIO", r"MONTAGEM.*PROTECAO CONTRA INCENDIO",
    r"MANUTENCAO.*PROTECAO CONTRA INCENDIO", r"MANUTENCAO.*COMBATE A INCENDIO",
    r"INSTALACAO DE SISTEMA DE COMBATE A INCENDIO", r"MANUTENCAO DE SISTEMA DE COMBATE A INCENDIO",
    r"\bTENIS\b", r"\bSAPATO\b", r"\bBOTINA\b", r"\bUNIFORME", r"\bCAFE\b", r"\bACUCAR\b",
    r"ALIMENTIC", r"GENEROS", r"HOSPITALAR", r"MEDICAMENTO", r"\bSERINGA", r"\bIMPRESSORA",
    r"\bCOMPUTADOR", r"\bNOTEBOOK\b", r"\bCADEIRA", r"\bMOBILIARIO\b", r"\bVEICULO", r"\bTRATOR",
    r"\bSUCATA", r"\bPISCINA", r"\bZELADORIA\b", r"\bJARDINAGEM\b", r"SEGURANCA ARMADA",
    r"\bVIGILANCIA\b", r"\bGASOLINA\b", r"\bDIESEL\b", r"\bCOMBUSTIVEL\b",
    r"\bROCAGEM\b", r"\bVARRECAO\b", r"COLETA DE LIXO", r"\bDEDETIZACAO\b", r"\bLIMPEZA PREDIAL\b",
    r"EXAME LABORATORIAL", r"CLINICA MEDICA", r"CONSULTA MEDICA", r"ATENDIMENTO MEDICO",
    r"\bODONTOLOG", r"\bENFERMAGEM\b", r"\bFISIOTERAPIA\b",
    r"\bBUFFET\b", r"\bCOFFEE BREAK\b", r"\bPALESTRANTE\b", r"\bCONGRESSO\b", r"\bSONORIZACAO\b",
    r"TRANSPORTE.*(ESTUDANTE|ESCOLAR|ALUNO|DOCENTE|PASSAGEIRO)",
    r"\bDIRF\b", r"\bEFD[- ]?REINF\b", r"\bCONTABIL", r"\bTRIBUTAR", r"\bFOLHA DE PAGAMENTO\b",
    r"ASSESSORIA JURIDICA", r"CONSULTORIA JURIDICA", r"\bADVOCACIA\b",
    r"LINK DE INTERNET", r"TELEFONIA", r"ENERGIA NUCLEAR", r"\bRADIOLOGIA\b"
]

EXCECOES_OBRA_SEGURANCA = [
    r"\bNR[- ]?12\b", r"\bNR[- ]?35\b", r"\bNR[- ]?18\b", r"\bPCMAT\b",
    r"PLATAFORMA[S]? ELEVATORIA[S]?", r"\bPEMT\b",
    r"LINHA DE VIDA", r"PONTO[S]? DE ANCORAGEM", r"TESTE DE ARRANCAMENTO",
    r"PLANO DE RIGGING", r"PLANO DE ICAMENTO"
]

# ==============================================================================
# 3. REGRAS DE INCLUSÃO ESTRITAS
# ==============================================================================
REGRAS_INCLUSAO = {
    "1. Laudos, Programas & Gestão SST": [
        r"\bLTCAT\b", r"\bPGR\b", r"\bGRO\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
        r"LAUDO.*INSALUBRIDADE", r"LAUDO.*PERICULOSIDADE",
        r"ADICIONAL DE INSALUBRIDADE", r"ADICIONAL DE PERICULOSIDADE",
        r"ANALISE ERGONOMICA", r"LAUDO ERGONOMICO",
        r"DOSIMETRIA DE RUIDO", r"AVALIACAO DE RUIDO", r"AVALIACAO AMBIENTAL.*TRABALHO",
        r"HIGIENE OCUPACIONAL",
        r"(ELABORACAO|ATUALIZACAO|REVISAO|GESTAO|ASSESSORIA|CONSULTORIA|PRESTACAO DE SERVICO).*SEGURANCA DO TRABALHO",
        r"(ELABORACAO|ATUALIZACAO|REVISAO|GESTAO|ASSESSORIA|CONSULTORIA|PRESTACAO DE SERVICO).*SAUDE OCUPACIONAL",
        r"ENGENHARIA DE SEGURANCA DO TRABALHO",
        r"SEGURANCA E MEDICINA DO TRABALHO", r"SEGURANCA E SAUDE DO TRABALHO",
        r"\bS-2210\b", r"\bS-2220\b", r"\bS-2240\b",
        r"(SST|SEGURANCA|SAUDE).*(ESOCIAL|E-SOCIAL)"
    ],
    "2. NR-18, Plataforma Elevatória (PEMT/PTA) & Treinamentos Técnicos": [
        r"\bNR[- ]?18\b", r"\bPCMAT\b", r"PGR.*CONSTRUCAO",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO|OPERACAO).*PLATAFORMA[S]? ELEVATORIA[S]?",
        r"\bPEMT\b",
        r"\bPTA\b.*(PLATAFORMA|TRABALHO EM ALTURA|NR[- ]?18|OPERADOR)",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?18",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?35",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?11",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?12",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?10",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?33",
        r"(TREINAMENTO|CAPACITACAO|CURSO|RECICLAGEM|HABILITACAO).*NR[- ]?23",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*TRABALHO EM ALTURA",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*ESPACO CONFINADO",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*EMPILHADEIRA",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*PONTE ROLANTE",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*MUNCK",
        r"(TREINAMENTO|CAPACITACAO|CURSO).*BRIGADA DE INCENDIO",
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
    "4. PMOC & Engenharia Mecânica (Laudos / NR-12 / Ancoragem)": [
        r"(ELABORACAO|IMPLEMENTACAO|ATUALIZACAO|GESTAO|LAUDO|ART|RESPONSABILIDADE TECNICA).*\bPMOC\b",
        r"\bPMOC\b",
        r"PLANO DE MANUTENCAO.*OPERACAO.*CONTROLE",
        r"(ADEQUACAO|LAUDO|INVENTARIO|APRECIACAO DE RISCO|ANALISE DE RISCO|DIAGNOSTICO|INSTALACAO).*NR[- ]?12",
        r"\bNR[- ]?12\b",
        r"(LAUDO|INSPECAO|PERICIA|VISTORIA|PROJETO|ART).*ENGENHARIA MECANICA",
        r"(INSPECAO|LAUDO|PERICIA|VISTORIA|ART).*MECANIC[OA]",
        r"(INSPECAO|LAUDO|TESTE|PROJETO|DIMENSIONAMENTO|INSTALACAO).*LINHA DE VIDA",
        r"(INSPECAO|LAUDO|TESTE|PROJETO|DIMENSIONAMENTO|INSTALACAO).*PONTO[S]? DE ANCORAGEM",
        r"(INSPECAO|LAUDO|TESTE|PROJETO|INSTALACAO).*ANCORAGEM.*NR[- ]?35",
        r"TESTE DE ARRANCAMENTO",
        r"(LAUDO|INSPECAO|VISTORIA).*PLAYGROUND",
        r"(LAUDO|INSPECAO|VISTORIA).*BRINQUEDO[S]?"
    ],
    "5. Projetos & Laudos de Estrutura Metálica": [
        r"(PROJETO|CALCULO|LAUDO|INSPECAO|VISTORIA|PERICIA|DIAGNOSTICO|REFORCO).*ESTRUTURA[S]? METALICA[S]?",
        r"ESTRUTURA[S]? METALICA[S]?.*(PROJETO|CALCULO|LAUDO|INSPECAO|VISTORIA|PERICIA)"
    ]
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
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

def classificar_objeto(objeto_texto: str) -> tuple[bool, str]:
    obj_clean = remover_acentos(objeto_texto).strip()
    if not obj_clean:
        return False, ""

    tem_excecao_seguranca = any(
        re.search(exc, obj_clean, re.IGNORECASE) for exc in EXCECOES_OBRA_SEGURANCA
    )

    if not tem_excecao_seguranca:
        for termo_compra in TERMOS_PROIBIDOS_COMPRA:
            if re.search(termo_compra, obj_clean, re.IGNORECASE):
                return False, ""

    for termo_proibido in TERMOS_PROIBIDOS_OBRA_E_BRACAL:
        if re.search(termo_proibido, obj_clean, re.IGNORECASE):
            if tem_excecao_seguranca and not any(
                k in obj_clean for k in ["TUBULACAO", "ESCAVACAO", "NR-13", "NR 13", "CALDEIRA", "POSTO DE TRABALHO"]
            ):
                continue
            return False, ""

    for categoria, padroes in REGRAS_INCLUSAO.items():
        for padrao in padroes:
            if re.search(padrao, obj_clean, re.IGNORECASE):
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

        if str(id_lic).startswith("QD_"):
            dt_cap = _parse_data_segura(item.get("data_captura") or "")
            if dt_cap and (agora - dt_cap).days <= 15:
                ids_vistos.add(id_lic)
                lista_limpa.append(item)
            continue

        valido, categoria = classificar_objeto(item.get("objeto", ""))
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

def fazer_requisicao_humana(url: str, params=None, max_tentativas: int = 3, timeout_req: float = 15.0):
    usar_verify = True
    for tentativa in range(1, max_tentativas + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout_req, verify=usar_verify)
            if resp.status_code in [200, 204]:
                return resp
            elif resp.status_code == 429:
                tempo_espera = random.uniform(6.0, 12.0) * tentativa
                print(f"   ⏳ [Simulador Humano] Rate Limit (429). Pausa de {tempo_espera:.1f}s...", flush=True)
                time.sleep(tempo_espera)
            else:
                print(f"   ⚠️ Resposta HTTP {resp.status_code} em {url}", flush=True)
                break
        except requests.exceptions.SSLError:
            usar_verify = False
            if tentativa < max_tentativas:
                time.sleep(1.0)
        except Exception as e:
            print(f"   ⚠️ Falha temporária na rede: {e}", flush=True)
            if tentativa < max_tentativas:
                time.sleep(random.uniform(1.5, 3.0))
    return None

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
        "cidade": cidade_identificada,
        "link_edital": link_direto,
        "data_fim": data_limite_iso,
        "data_captura": datetime.now(timezone(timedelta(hours=-3))).isoformat()
    })

# ==============================================================================
# 4. ETAPA 1/2: VARREDURA PNCP & BEC/SP — 100% DOS EDITAIS ABERTOS HOJE
# ==============================================================================
def buscar_pncp_propostas_abertas(ids_processados, stop_loss, oportunidades_novas):
    hoje = datetime.now()
    dt_fim_busca = (hoje + timedelta(days=60)).strftime("%Y%m%d")
    modalidades = [6, 8, 9, 4, 5, 7]

    for mod in modalidades:
        print(f"\n🔍 [ETAPA 1/2 - PNCP & BEC/SP PROPOSTAS ABERTAS] Modalidade {mod} em SP...", flush=True)
        pagina = 1
        total_paginas = 1

        while pagina <= total_paginas:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/proposta"
            params = {
                "dataFinal": dt_fim_busca,
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

            print(f"   ↳ Mod. {mod} (Pág. {pagina}/{total_paginas}): {len(lista)} editais abertos...", flush=True)
            for edital in lista:
                processar_edital(edital, ids_processados, stop_loss, oportunidades_novas, " [PNCP]")

            pagina += 1
            time.sleep(random.uniform(0.8, 1.5))

# ==============================================================================
# 5. ETAPA 2/2: QUERIDO DIÁRIO (DIÁRIOS OFICIAIS MUNICIPAIS — 15 DIAS)
# ==============================================================================
def buscar_querido_diario(ids_processados, oportunidades_novas):
    print("\n📰 [ETAPA 2/2 - QUERIDO DIÁRIO] Varrendo Diários Oficiais Municipais (15 dias)...", flush=True)
    hoje = datetime.now()
    dt_inicio = (hoje - timedelta(days=15)).strftime("%Y-%m-%d")
    dt_fim = hoje.strftime("%Y-%m-%d")

    codigos_ibge = list(MUNICIPIOS_IBGE.values())

    for query_str in QUERIES_DIARIO_OFICIAL:
        params = [
            ("published_since", dt_inicio),
            ("published_until", dt_fim),
            ("querystring", query_str),
            ("excerpt_size", 350),
            ("number_of_excerpts", 1),
            ("size", 30)
        ]
        for ibge in codigos_ibge:
            params.append(("territory_ids", ibge))

        resp = fazer_requisicao_humana(URL_QUERIDO_DIARIO, params=params)
        if not resp or resp.status_code != 200:
            continue

        dados = resp.json()
        gazettes = dados.get("gazettes", [])

        for doc in gazettes:
            cidade = remover_acentos(doc.get("territory_name", "MUNICÍPIO SP"))
            data_pub = doc.get("date", "")
            url_pdf = doc.get("url", "")
            trechos = doc.get("excerpts", [])
            trecho_limpo = re.sub(r"<[^>]+>", "", trechos[0]).strip() if trechos else ""

            trecho_upper = remover_acentos(trecho_limpo)
            if any(ruido in trecho_upper for ruido in ["APOSENTADORIA", "EXONERACAO", "LICENCA PREMIO", "AUTO DE INFRACAO"]):
                continue

            if not any(ctx in trecho_upper for ctx in ["PREGAO", "DISPENSA", "LICITACAO", "EDITAL", "CONTRATACAO", "TOMADA DE PRECOS", "CONCORRENCIA", "COTACAO"]):
                continue

            hash_id = hashlib.sha256(f"QD|{cidade}|{data_pub}|{trecho_upper[:120]}".encode()).hexdigest()[:16]
            id_unico = f"QD_{hash_id}"

            if id_unico in ids_processados:
                continue
            ids_processados.add(id_unico)

            print(f"   🎯 [DIÁRIO OFICIAL] ({cidade} - {data_pub}): {trecho_limpo[:80]}...", flush=True)

            enviar_planilha(f"DIÁRIO OFICIAL - {cidade}", 0.0, f"[DIÁRIO OFICIAL] {trecho_limpo[:250]}", url_pdf)
            enviar_telegram(
                f"📰 *ALERTA DIÁRIO OFICIAL — {cidade}*\n\n"
                f"📅 *Publicado em:* {data_pub}\n"
                f"🔍 *Busca:* `{query_str}`\n"
                f"📝 *Trecho:* _{trecho_limpo[:300]}..._\n\n"
                f"🔗 [Abrir PDF do Diário Oficial]({url_pdf})"
            )

            oportunidades_novas.append({
                "id": id_unico,
                "categoria": "Diário Oficial (Querido Diário)",
                "orgao": f"PREFEITURA / DIÁRIO DE {cidade}",
                "valor": 0.0,
                "objeto": trecho_limpo[:400],
                "cidade": cidade,
                "link_edital": url_pdf,
                "data_fim": "",
                "data_captura": datetime.now(timezone(timedelta(hours=-3))).isoformat()
            })

        time.sleep(random.uniform(0.8, 1.5))

# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================
def executar():
    print("==================================================================")
    print("🚀 MINERADOR TM ENGENHARIA: PNCP & BEC/SP (/proposta) + QUERIDO DIÁRIO")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    oportunidades_novas = []
    ids_processados = set()

    buscar_pncp_propostas_abertas(ids_processados, stop_loss, oportunidades_novas)
    buscar_querido_diario(ids_processados, oportunidades_novas)

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
    print(f"📌 Novas Oportunidades Encontradas Hoje: {len(oportunidades_novas)}")
    print(f"🏆 Total de Oportunidades Ativas no Cockpit: {total_limpo}")
    print("==================================================================")

if __name__ == "__main__":
    executar()

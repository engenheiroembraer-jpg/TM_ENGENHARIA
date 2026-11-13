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
# CÓDIGOS CATSER OFICIAIS TM ENGENHARIA (SST, TREINAMENTOS NR/BRIGADA & MECÂNICA)
# ==============================================================================
CODIGOS_CATSER_TM = [
    8818,    # Serviços de Engenharia de Segurança do Trabalho
    25550,   # Consultoria e Assessoria - Engenharia
    16438,   # Treinamento e Capacitação Profissional (NRs, Brigada, APH/DEA)
    25470,   # Vistoria, Validação e Certificação (AVCB / CLCB)
    242497,  # Serviço de Vistoria e Emissão de Laudos de Segurança
    25518,   # Inspeção e Ensaio Não Destrutivo (NR-13 / Vasos / Caldeiras)
    25496,   # Laudos Técnicos de Engenharia Mecânica / Industrial
    23639    # Elaboração / Análise de Projetos de Engenharia
]

CIDADES_ESCOPO = [
    "SAO JOSE DOS CAMPOS", "TAUBATE", "JACAREI", "PINDAMONHANGABA", "GUARATINGUETA",
    "UBATUBA", "SAO SEBASTIAO", "ILHABELA", "CARAGUATATUBA", "CACAPAVA", "LORENA",
    "CRUZEIRO", "APARECIDA", "TREMEMBE", "SAO LUIZ DO PARAITINGA", "CAMPOS DO JORDAO",
    "SANTO ANTONIO DO PINHAL", "SAO BENTO DO SAPUCAI", "SANTA BRANCA", "IGARATA",
    "PARAIBUNA", "JAMBEIRO", "REDENCAO DA SERRA", "NATIVIDADE DA SERRA", "SILVEIRAS",
    "CUNHA", "CACHOEIRA PAULISTA", "CANAS", "POTIM", "ROSEIRA", "LAGOINHA", "LAVRINHAS",
    "QUELUZ", "BANANAL", "ARAAPEI", "SAO JOSE DO BARREIRO", "SAO PAULO", "SANTOS",
    "MOGI DAS CRUZES", "SUZANO", "ARUJA", "SANTA ISABEL", "POA", "FERRAZ DE VASCONCELOS",
    "ITAQUAQUECETUBA", "SALESOPOLIS", "GUARULHOS"
]

def remover_acentos(texto: str) -> str:
    if not texto: return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

CIDADES_CLEAN = [remover_acentos(c) for c in CIDADES_ESCOPO]

# ==============================================================================
# TERMOS PERMITIDOS: CREA-SP (SST + MECÂNICA) + CERTIFICADOS DE INSTRUTOR
# ==============================================================================
TERMOS_PERMITIDOS = [
    # Documentos Legais SST & eSocial
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
    r"\bPPRA\b", r"\bPCMAT\b", r"\bPGRTR\b", r"ESOCIAL", r"E-SOCIAL",
    r"S-2210", r"S-2220", r"S-2240", r"EVENTOS.*SST", r"GESTAO.*SST",
    r"SEGURANCA.*TRABALHO", r"ENGENHARIA.*SEGURANCA", r"SAUDE.*OCUPACIONAL",
    r"INSALUBRIDADE", r"PERICULOSIDADE", r"HIGIENE.*OCUPACIONAL",
    r"ANALISE.*ERGONOMIC", r"LAUDO.*ERGONOMIC", r"MAPA.*RISCO",
    r"LAUDO.*AMBIENTAL", r"ASSESSORIA.*SST", r"CONSULTORIA.*SST",

    # Treinamentos Habilitados pelos Certificados (NRs, Brigada, APH/DEA, Heliponto)
    r"NR[- ]?0?1\b", r"NR[- ]?0?5\b", r"NR[- ]?0?6\b", r"NR[- ]?10\b",
    r"NR[- ]?11\b", r"NR[- ]?12\b", r"NR[- ]?13\b", r"NR[- ]?17\b",
    r"NR[- ]?18\b", r"NR[- ]?20\b", r"NR[- ]?23\b", r"NR[- ]?33\b", r"NR[- ]?35\b",
    r"TREINAMENTO.*NR", r"CAPACITACAO.*NR", r"CURSO.*NR[- ]?\d+",
    r"TRABALHO.*ALTURA", r"ESPACO.*CONFINADO", r"\bCIPA\b", r"\bSIPAT\b",
    r"TREINAMENTO.*SEGURANCA.*TRABALHO", r"FORMACAO.*BRIGADA",
    r"TREINAMENTO.*BRIGADA", r"CAPACITACAO.*BRIGADA", r"CURSO.*BRIGADA",
    r"PRIMEIROS.*SOCORROS", r"ATENDIMENTO.*PRE[- ]?HOSPITALAR", r"\bAPH\b",
    r"SOCORRISTA", r"DESFIBRILADOR", r"\bDEA\b", r"INFLAMAVEIS",
    r"HELIPONTO", r"OPERACOES.*HELIPONTO",

    # Projetos e Regularização (Sem recarga/compra de equipamentos)
    r"\bAVCB\b", r"\bCLCB\b", r"LAUDO.*INCEND", r"PROJETO.*INCEND",
    r"REGULARIZACAO.*BOMBEIRO", r"PROJETO.*TECNICO.*INCEND",

    # Engenharia Mecânica, Máquinas, Laudos & Inspeções
    r"ADEQUAC.*MAQUINA", r"APRECIAC.*RISCO", r"ART.*MECANICA", r"LAUDO.*MECANICO",
    r"INSPECAO.*MECANICA", r"LINHA.*VIDA", r"PONTO.*ANCORAGEM", r"TESTE.*ARRANCAMENTO",
    r"CALDEIRA", r"VASO.*PRESSAO", r"COMPRESSOR", r"TESTE.*HIDROSTATICO",
    r"\bPMOC\b", r"PLANO.*MANUTENCAO.*OPERACAO.*CONTROLE",
    r"PLAYGROUND", r"BRINQUEDO.*INFANTIL", r"ELEVADOR", r"PLATAFORMA.*ELEVATORIA",
    r"LAUDO.*TECNICO.*ENGENHARIA", r"RESPONSABILIDADE.*TECNICA"
]

# ==============================================================================
# TERMOS PROIBIDOS: BLOQUEIO DE RECARGA DE EXTINTOR, LOCAÇÃO DE CT E OBRAS
# ==============================================================================
TERMOS_PROIBIDOS = [
    # Bloqueio de recarga de extintor, mangueiras e locação de centro de treinamento
    r"EXTINTOR", r"RECARGA", r"MANGUEIRA.*INCEND", r"HIDRANTE",
    r"CENTRO.*TREINAMENTO", r"LOCACAO.*CENTRO", r"CAMPO.*TREINAMENTO",
    r"POSTO.*BOMBEIRO", r"BOMBEIRO.*CIVIL", r"DETECCAO.*ALARME",

    # Bloqueio de materiais, obras civis e serviços gerais fora do escopo
    r"TENIS", r"SAPATO", r"BOTINA", r"UNIFORME", r"CAFÉ", r"CAFE", r"ACUCAR", r"PAO",
    r"ALIMENTIC", r"GENEROS", r"HOSPITALAR", r"MEDICAMENTO", r"SERINGA", r"IMPRESSORA",
    r"COMPUTADOR", r"CADEIRA", r"VEICULO", r"TRATOR", r"SUCATA", r"PISCINA",
    r"ZELADORIA", r"JARDINAGEM", r"SEGURANCA ARMADA", r"VIGILANCIA", r"GASOLINA", r"DIESEL",
    r"PAVIMENTACAO", r"ASFALTO", r"ROCAGEM", r"VARRECAO", r"LIXO", r"TAMPAS DE BUEIRO",
    r"CONSTRUCAO DE PREFEITURA", r"OBRA DE PAVIMENTAC", r"OBRA.*CIVIL", r"REFORMA.*PREDIAL",
    r"AQUISICAO.*EPI", r"FORNECIMENTO.*EPI", r"COMPRA.*EPI"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def validar_regiao(cidade_orgao: str, nome_orgao: str) -> tuple[bool, str]:
    texto = remover_acentos(f"{cidade_orgao} {nome_orgao}")
    for cid in CIDADES_CLEAN:
        if cid in texto:
            return True, cid
    if any(k in texto for k in ["SAO PAULO", "SUBPREFEITURA", "SECRETARIA", "ESTADO DE SAO PAULO", "GOVERNO", "UNIVERSIDADE", "INSTITUTO", "FUNDACAO", "CAMARA", "PREFEITURA"]):
        return True, "SÃO PAULO / REGIONAL"
    return False, ""

def validar_objeto(objeto_texto: str) -> bool:
    texto = remover_acentos(objeto_texto)
    if any(re.search(re.compile(termo, re.IGNORECASE), texto) for termo in TERMOS_PROIBIDOS):
        return False
    if any(re.search(re.compile(termo, re.IGNORECASE), texto) for termo in TERMOS_PERMITIDOS):
        return True
    return False

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

def executar():
    print("==================================================================")
    print("🚀 MINERADOR TM ENGENHARIA: SST, TREINAMENTOS NR/BRIGADA & MECÂNICA")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    hoje = datetime.now()
    
    dt_inicio = (hoje - timedelta(days=30)).strftime("%Y%m%d")
    dt_fim = (hoje + timedelta(days=60)).strftime("%Y%m%d")

    total_oportunidades = 0
    oportunidades_novas = []
    ids_processados = set()

    # ETAPA 1: MINERAÇÃO PAGINADA COMPLETA POR MODALIDADES NO ESTADO DE SP
    modalidades = [8, 6, 4, 1, 2, 3, 5, 7]
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
                if not edital_esta_aberto(edital):
                    continue

                orgao_info = edital.get("orgaoEntidade", {})
                orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "ÓRGÃO PÚBLICO").upper()
                municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "").upper()

                eh_da_regiao, cidade_identificada = validar_regiao(municipio_orgao, orgao_nome)
                if not eh_da_regiao:
                    continue

                objeto = edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or ""
                if not validar_objeto(objeto):
                    continue

                cnpj = re.sub(r"\D", "", str(orgao_info.get("cnpj") or edital.get("cnpjOrgao") or ""))
                ano = edital.get("anoCompra") or edital.get("anoContratacao")
                seq = edital.get("sequencialCompra") or edital.get("sequencialContratacao")

                id_unico = f"{cnpj}_{ano}_{seq}" if (cnpj and ano and seq) else str(hash(objeto))
                if id_unico in ids_processados:
                    continue
                ids_processados.add(id_unico)

                valor_estimado = float(edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0)
                if stop_loss and hasattr(stop_loss, 'validar_lance') and valor_estimado > 0:
                    if not stop_loss.validar_lance(valor_estimado):
                        continue

                total_oportunidades += 1
                link_direto = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else "https://pncp.gov.br"
                txt_valor = f"R$ {valor_estimado:,.2f}" if valor_estimado > 0 else "Sob Consulta em Edital"

                dt_fim_prop = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or edital.get("dataAberturaProposta") or ""

                print(f"   🎯 OPORTUNIDADE FILTRADA ({cidade_identificada}): {orgao_nome[:35]} | Valor: {txt_valor}", flush=True)

                enviar_planilha(orgao_nome, valor_estimado, objeto, link_direto)
                enviar_telegram(
                    f"🔥 *OPORTUNIDADE SST/ENGENHARIA (PNCP SP)*\n\n"
                    f"🏢 *Órgão:* {orgao_nome}\n"
                    f"📍 *Cidade:* {cidade_identificada}\n"
                    f"💰 *Valor Estimado:* {txt_valor}\n"
                    f"📝 *Objeto:* _{objeto[:200]}_\n\n"
                    f"🔗 [Acessar Edital]({link_direto})"
                )

                oportunidades_novas.append({
                    "id": id_unico, "orgao": orgao_nome, "valor": valor_estimado,
                    "objeto": objeto, "cidade": cidade_identificada, "link_edital": link_direto,
                    "data_fim": dt_fim_prop
                })

            pagina += 1
            time.sleep(random.uniform(1.8, 3.6))

        time.sleep(random.uniform(4.0, 7.0))

    # ETAPA 2: MINERAÇÃO PAGINADA COMPLETA POR CÓDIGOS CATSER DE ENGENHARIA
    print("\n🔍 [ETAPA 2/2] Mineração por Códigos CATSER de Engenharia/SST...", flush=True)
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
                if not edital_esta_aberto(edital):
                    continue

                orgao_info = edital.get("orgaoEntidade", {})
                orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "ÓRGÃO PÚBLICO").upper()
                municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "").upper()

                eh_da_regiao, cidade_identificada = validar_regiao(municipio_orgao, orgao_nome)
                if not eh_da_regiao:
                    continue

                objeto = edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or ""
                if not validar_objeto(objeto):
                    continue

                cnpj = re.sub(r"\D", "", str(orgao_info.get("cnpj") or edital.get("cnpjOrgao") or ""))
                ano = edital.get("anoCompra") or edital.get("anoContratacao")
                seq = edital.get("sequencialCompra") or edital.get("sequencialContratacao")

                id_unico = f"{cnpj}_{ano}_{seq}" if (cnpj and ano and seq) else str(hash(objeto))
                if id_unico in ids_processados:
                    continue
                ids_processados.add(id_unico)

                valor_estimado = float(edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0)
                if stop_loss and hasattr(stop_loss, 'validar_lance') and valor_estimado > 0:
                    if not stop_loss.validar_lance(valor_estimado):
                        continue

                total_oportunidades += 1
                link_direto = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else "https://pncp.gov.br"
                txt_valor = f"R$ {valor_estimado:,.2f}" if valor_estimado > 0 else "Sob Consulta em Edital"

                dt_fim_prop = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or edital.get("dataAberturaProposta") or ""

                print(f"   🎯 OPORTUNIDADE FILTRADA (CATSER {catser} | {cidade_identificada}): {orgao_nome[:35]} | Valor: {txt_valor}", flush=True)

                enviar_planilha(orgao_nome, valor_estimado, objeto, link_direto)
                enviar_telegram(
                    f"🔥 *OPORTUNIDADE PURA (CATSER {catser})*\n\n"
                    f"🏢 *Órgão:* {orgao_nome}\n"
                    f"📍 *Cidade:* {cidade_identificada}\n"
                    f"💰 *Valor Estimado:* {txt_valor}\n"
                    f"📝 *Objeto:* _{objeto[:200]}_\n\n"
                    f"🔗 [Acessar Edital]({link_direto})"
                )

                oportunidades_novas.append({
                    "id": id_unico, "orgao": orgao_nome, "valor": valor_estimado,
                    "objeto": objeto, "cidade": cidade_identificada, "link_edital": link_direto,
                    "data_fim": dt_fim_prop
                })

            pagina += 1
            time.sleep(random.uniform(1.8, 3.6))

        time.sleep(random.uniform(4.0, 7.0))

    # ==============================================================================
    # MELHORIA APLICADA: GRAVAÇÃO ACUMULATIVA + FAXINA DE EXTINTORES + DESCARTADOS
    # ==============================================================================
    ARQUIVO_JSON = "licitacoes.json"
    ARQUIVO_DESCARTADOS = "descartados.json"
    historico_existente = []
    ids_descartados = set()

    if os.path.exists(ARQUIVO_DESCARTADOS):
        try:
            with open(ARQUIVO_DESCARTADOS, "r", encoding="utf-8") as f:
                ids_descartados = set(json.load(f))
        except Exception:
            ids_descartados = set()

    if os.path.exists(ARQUIVO_JSON):
        try:
            with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
                historico_existente = json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao carregar historico local: {e}", flush=True)
            historico_existente = []

    # Mescla histórico limpando automaticamente qualquer item que agora cai nos TERMOS_PROIBIDOS
    mapa_licitacoes = {
        item["id"]: item
        for item in historico_existente
        if item["id"] not in ids_descartados and validar_objeto(item.get("objeto", ""))
    }

    for op in oportunidades_novas:
        if op["id"] not in ids_descartados:
            mapa_licitacoes[op["id"]] = op

    agora = datetime.now()
    lista_final_acumulada = []

    for id_lic, item in mapa_licitacoes.items():
        dt_fim_str = item.get("data_fim") or ""
        edital_expirado = False

        if dt_fim_str:
            try:
                dt_fim_clean = str(dt_fim_str).replace("Z", "+00:00")
                dt_fim = datetime.fromisoformat(dt_fim_clean)
                dt_agora = datetime.now(dt_fim.tzinfo) if dt_fim.tzinfo else agora
                if dt_fim < dt_agora:
                    edital_expirado = True
            except Exception:
                pass

        if not edital_expirado:
            lista_final_acumulada.append(item)

    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(lista_final_acumulada, f, ensure_ascii=False, indent=4)

    print("\n==================================================================")
    print(f"✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"📌 Novas Oportunidades Encontradas Hoje: {len(oportunidades_novas)}")
    print(f"🏆 Total de Oportunidades Abertas Mantidas no Cockpit: {len(lista_final_acumulada)}")
    print("==================================================================")

if __name__ == "__main__":
    executar()
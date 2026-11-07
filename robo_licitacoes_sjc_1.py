import os
import re
import time
import json
import unicodedata
import requests
from datetime import datetime, timedelta

# ==============================================================================
# IMPORTAÇÃO DO MÓDULO STOP LOSS
# ==============================================================================
try:
    from stoplossmanager import StopLossManager
except ImportError:
    StopLossManager = None

# ==============================================================================
# CONFIGURAÇÕES E APIS
# ==============================================================================
URL_PNCP = "https://pncp.gov.br"
URL_PLANILHA_TM = "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"

TELEGRAM_TOKEN = "8269224927:AAGzNVzbb4b8-JDaroQfyWklQh1ISxZPWFw"
TELEGRAM_CHAT_ID = "7193404104"

# ==============================================================================
# LISTA EXPANDIDA DE CÓDIGOS CATSER (GOVERNO FEDERAL / PNCP)
# ==============================================================================
CODIGOS_CATSER_TM = [
    "8818",    # Serviços de Engenharia de Segurança do Trabalho
    "25550",   # Consultoria e Assessoria - Engenharia
    "13412",   # Manutenção / Instalação de Sistema de Combate a Incêndio
    "16438",   # Treinamento e Capacitação Profissional (NRs, Brigada)
    "25470",   # Vistoria, Validação e Certificação (AVCB / CLCB)
    "242497",  # Serviço de Vistoria e Emissão de Laudos de Segurança
    "25518",   # Inspeção e Ensaio Não Destrutivo (Vasos, Caldeiras, Estruturas)
    "25496",   # Laudos Técnicos de Engenharia Mecânica / Estrutural
    "23639"    # Elaboração / Análise de Projetos de Engenharia
]

# ==============================================================================
# MAPEAMENTO DE MUNICÍPIOS IBGE (EXCLUSIVO ESTADO DE SÃO PAULO)
# ==============================================================================
MUNICIPIOS_IBGE = {
    # --------------------------------------------------------------------------
    # SÃO PAULO (VALE DO PARAÍBA, LITORAL NORTE, ALTO TIETÊ, GRANDE SP & SANTOS)
    # --------------------------------------------------------------------------
    "3549904": "SAO JOSE DOS CAMPOS", "3554102": "TAUBATE", "3524402": "JACAREI",
    "3538006": "PINDAMONHANGABA", "3518404": "GUARATINGUETA", "3555406": "UBATUBA",
    "3550704": "SAO SEBASTIAO", "3520400": "ILHABELA", "3510500": "CARAGUATATUBA",
    "3508504": "CACAPAVA", "3527207": "LORENA", "3513405": "CRUZEIRO",
    "3502507": "APARECIDA", "3554805": "TREMEMBE", "3550007": "SAO LUIZ DO PARAITINGA",
    "3510906": "CAMPOS DO JORDAO", "3549706": "SANTO ANTONIO DO PINHAL", "3548609": "SAO BENTO DO SAPUCAI",
    "3546306": "SANTA BRANCA", "3520202": "IGARATA", "3535606": "PARAIBUNA",
    "3524907": "JAMBEIRO", "3542404": "REDENCAO DA SERRA", "3532306": "NATIVIDADE DA SERRA",
    "3551900": "SILVEIRAS", "3513603": "CUNHA", "3508603": "CACHOEIRA PAULISTA",
    "3509700": "CANAS", "3540754": "POTIM", "3544301": "ROSEIRA",
    "3526308": "LAGOINHA", "3526605": "LAVRINHAS", "3541901": "QUELUZ",
    "3504909": "BANANAL", "3503158": "ARAAPEI", "3549607": "SAO JOSE DO BARREIRO",
    "3550308": "SAO PAULO", "3548500": "SANTOS", "3530607": "MOGI DAS CRUZES",
    "3552502": "SUZANO", "3518800": "ARUJA", "3546801": "SANTA ISABEL",
    "3539806": "POA", "3515707": "FERRAZ DE VASCONCELOS", "3523107": "ITAQUAQUECETUBA",
    "3545001": "SALESOPOLIS", "3518305": "GUARULHOS"
}

NOMES_CIDADES_VALIDAS = list(MUNICIPIOS_IBGE.values())
MODALIDADES_PNCP = [6, 8, 4, 1, 2, 3, 5, 7]

# ==============================================================================
# RADICAIS COMBINADOS - FOCO 100% EM SST / LAUDOS / AVCB / NR (FILÊ MIGNON)
# ==============================================================================
TERMOS_PERMITIDOS = [
    # --- INCÊNDIO / BOMBEIROS / AVCB / CLCB / BRIGADA ---
    r"\bAVCB\b", r"\bCLCB\b", r"LAUDO.*INCENDIO", r"PROJETO.*INCENDIO", r"BRIGADA.*INCENDIO", 
    r"SISTEMA.*COMBATE.*INCENDIO", r"RENOVACAO.*AVCB", r"INSPECAO.*BOMBEIRO",
    
    # --- SEGURANÇA DO TRABALHO / SST / DOCUMENTAÇÕES ---
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
    r"SEGURANCA.*TRABALHO", r"SAUDE.*TRABALHO", r"SAUDE.*OCUPACIONAL",
    r"LAUDO.*INSALUBRIDADE", r"LAUDO.*PERICULOSIDADE", r"ANALISE.*ERGONOMIC",
    r"ESOCIAL", r"S-22\d{2}", r"GESTÃO.*SST", r"CONSULTORIA.*SST",
    
    # --- REGRAS REGULAMENTARES (NRs ESPECÍFICAS) ---
    r"NR-?10\b", r"NR-?12\b", r"NR-?13\b", r"NR-?18\b", r"NR-?33\b", r"NR-?35\b",
    r"TREINAMENTO.*NR", r"CURSO.*NR", r"ADEQUACAO.*NR",
    
    # --- ENGENHARIA DE SEGURANÇA / LAUDOS / VISTORIAS ---
    r"LINHA.*VIDA", r"PONTO.*ANCORAGEM", r"TESTE.*ANCORAGEM",
    r"LAUDO.*ESTRUTURAL", r"LAUDO.*ENG", r"LAUDO.*TECNICO.*SEGURANCA",
    r"PERICIA.*ENG", r"VISTORIA.*TECNIC", r"INSPECAO.*SAFETY",
    r"ART.*SEGURANCA", r"ART.*ENG"
]

# ==============================================================================
# BLACKLIST AMPLIADA - CORTE TOTAL DE RUÍDO E LIXO DE COMPRAS
# ==============================================================================
TERMOS_PROIBIDOS = [
    # --- VESTUÁRIO / CALÇADOS / EPI ISOLADO ---
    r"TENIS", r"SAPATO", r"BOTINA", r"BOOT", r"UNIFORME", r"CAMISA", r"CALCA", r"VESTUARIO",
    
    # --- GÊNEROS ALIMENTÍCIOS / COPA / RESTAURANTE / CHICLETE / DOCES ---
    r"CAFÉ", r"CAFE", r"ACUCAR", r"AÇÚCAR", r"PAO", r"PÃO", r"ALIMENTIC", r"GENEROS", 
    r"BISCOITO", r"LEITE", r"ALIMENTACAO", r"REFEICAO", r"HORTIFRUTI", r"CARNE", r"MANTIMENTOS",
    r"CESTA BASICA", r"PANIFICAC", r"MARMITA", r"LANCHE", r"AGUA", r"BEBIDA", r"DOCE", r"CHICLETE", r"BALA",

    # --- SAÚDE / HOSPITALAR / ODONTO / ESTÉTICA / CABELO ---
    r"RADIOGRAF", r"RAIO-X", r"RAIO X", r"MEDICO", r"MEDICAMENTO", r"EXAME", r"HOSPITALAR",
    r"GEL CONDUTOR", r"DERMATOLOGIC", r"ODONTOLOG", r"CADEIRA ODONTOLOGICA", r"VACINA",
    r"PACIENTE", r"FARMAC", r"INSUMOS HOSPITALARES", r"CURATIVO", r"SERINGA", r"AMBULATORIO",
    r"CABELO", r"SHAMPOO", r"ESTETICA", r"SALÃO",

    # --- INFORMÁTICA / TI / ELETRÔNICOS / ESCRITÓRIO ---
    r"IMPRESSORA", r"DRONE", r"DISPLAY", r"CAPACITOR", r"PLACA ELETRONICA", r"COMPUTADOR", 
    r"INFORMATICA", r"AQUISICAO DE PECA", r"PECA DE REPOSICAO", r"AUTOMOTIV", r"VEICULO", 
    r"CADEIRA ERGONOMIC", r"CADEIRA DE ESCRITORIO", r"CADEIRA COM APOIO", r"MOBILES",
    r"CARTUCHO", r"TONER", r"TECLADO", r"MOUSE", r"MONITOR", r"NOBREAK", r"CABO", r"FONTE",

    # --- SERVIÇOS DIVERSOS / OPERACIONAIS / MANUTENÇÃO COMUM ---
    r"CAES", r"GATOS", r"VETERINAR", r"ANIMAL", r"PISCINA", r"LIMPEZA", r"ZELADORIA", 
    r"JARDINAGEM", r"VIGILANCIA", r"SEGURANCA ARMADA", r"TRANSPORTE", 
    r"LOCACAO", r"GELADEIRA", r"TOPOGRAFIA", r"OFICINA", r"ARGILA", 
    r"MODELAGEM", r"OBRA CIVIL", r"PAVIMENTACAO", r"ASFALTO",
    r"SHOW", r"EVENTO", r"ARTISTICO", r"PNEU", r"COMBUSTIVEL", r"GASOLINA", r"DIESEL",
    r"AR CONDICIONADO", r"COMPRESSOR", r"MECANICA PESADA"
]

def remover_acentos(texto: str) -> str:
    if not texto: return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

def validar_objeto_licitacao(objeto_texto: str) -> bool:
    texto_tratado = remover_acentos(objeto_texto)
    if any(re.search(re.compile(termo, re.IGNORECASE), texto_tratado) for termo in TERMOS_PROIBIDOS):
        return False
    if any(re.search(re.compile(termo, re.IGNORECASE), texto_tratado) for termo in TERMOS_PERMITIDOS):
        return True
    return False

def validar_data_hora_futura(data_fim_raw: str) -> bool:
    if not data_fim_raw:
        return True
    try:
        data_limite_str = str(data_fim_raw).replace("Z", "").split(".")[0]
        if "T" in data_limite_str:
            dt_limite = datetime.strptime(data_limite_str, "%Y-%m-%dT%H:%M:%S")
        else:
            dt_limite = datetime.strptime(data_limite_str, "%Y-%m-%d %H:%M:%S")
        
        return dt_limite > datetime.now()
    except Exception:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return str(data_fim_raw).split("T")[0] >= today_str

def extrair_detalhes_e_itens_pncp(cnpj, ano, sequencial, objeto_fallback=""):
    link_tr = ""
    itens_extraidos = []
    if not (cnpj and ano and sequencial):
        return link_tr, itens_extraidos

    try:
        url_arquivos = f"{URL_PNCP}/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"
        res_arq = requests.get(url_arquivos, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res_arq.status_code == 200:
            arquivos = res_arq.json()
            if isinstance(arquivos, list):
                for arq in arquivos:
                    titulo = str(arq.get("titulo") or arq.get("nomeDocumento") or "").upper()
                    if any(t in titulo for t in ["TR", "TERMO DE REFERENCIA", "REFERENCIA", "ESPECIFICACAO"]):
                        link_tr = arq.get("url") or arq.get("uri") or ""
                        break
                if not link_tr and len(arquivos) > 0:
                    link_tr = arquivos[0].get("url") or arquivos[0].get("uri") or ""
    except Exception:
        pass

    try:
        url_itens = f"{URL_PNCP}/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens?pagina=1&tamanhoPagina=50"
        res_itens = requests.get(url_itens, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res_itens.status_code == 200:
            dados_itens = res_itens.json()
            lista_raw = dados_itens if isinstance(dados_itens, list) else (dados_itens.get("data") or dados_itens.get("resultado") or [])
            for item in lista_raw:
                desc = item.get("descricao") or item.get("descricaoResumida") or item.get("especificacao") or ""
                qtd = item.get("quantidade") or item.get("qtd") or 1
                valor_unit = item.get("valorUnitarioEstimado") or item.get("unitario") or 0.0
                valor_tot = item.get("valorTotalEstimado") or item.get("total") or (float(qtd) * float(valor_unit))
                
                if desc:
                    itens_extraidos.append({
                        "descricao": desc,
                        "quantidade": float(qtd),
                        "valorUnitarioEstimado": float(valor_unit),
                        "valorTotalEstimado": float(valor_tot)
                    })
    except Exception:
        pass

    if not itens_extraidos and objeto_fallback:
        itens_extraidos.append({
            "descricao": objeto_fallback,
            "quantidade": 1.0,
            "valorUnitarioEstimado": 0.0,
            "valorTotalEstimado": 0.0
        })

    return link_tr, itens_extraidos

def enviar_oportunidade_para_planilha(orgao, valor_estimado, objeto, link_edital=""):
    params = {
        "tipo": "sheet",
        "orgao": orgao,
        "valor": str(valor_estimado),
        "objeto": objeto,
        "escopo": objeto,
        "pncp": link_edital
    }
    try:
        requests.get(URL_PLANILHA_TM, params=params, timeout=10)
    except Exception:
        pass

def executar_mapeamento_pncp():
    print("==================================================================")
    print("🚀 INICIANDO MONITORAMENTO MAXIMIZADO (SP) - TM ENGENHARIA")
    print("==================================================================")
    
    stop_loss = StopLossManager() if StopLossManager else None
    
    data_hoje_dt = datetime.now()
    data_ini = data_hoje_dt - timedelta(days=90)
    data_inicial_str = data_ini.strftime("%Y%m%d")
    data_final_str = data_hoje_dt.strftime("%Y%m%d")
    
    total_varridas = 0
    total_oportunidades_tm = 0
    total_bloqueadas_stop_loss = 0
    total_ignoradas_vencidas = 0

    oportunidades_json = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # ETAPA 1: MUNICÍPIOS DE SÃO PAULO
    for codigo_ibge, nome_cidade in MUNICIPIOS_IBGE.items():
        uf_codigo = "SP"
        print(f"\n🔍 Varrendo Cidade: {nome_cidade} ({uf_codigo})...")
        achados_cidade = 0
        
        for modalidade in MODALIDADES_PNCP:
            pagina = 1
            while True:
                url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
                params = {
                    "dataInicial": data_inicial_str,
                    "dataFinal": data_final_str,
                    "codigoModalidadeContratacao": modalidade,
                    "uf": uf_codigo,
                    "codigoMunicipioIbge": codigo_ibge,
                    "pagina": pagina,
                    "tamanhoPagina": 50
                }
                
                try:
                    resposta = requests.get(url, params=params, headers=headers, timeout=15)
                    if resposta.status_code in [429, 500, 502, 503]:
                        time.sleep(2.0)
                        continue
                    if resposta.status_code != 200:
                        break

                    dados = resposta.json()
                    lista_editais = dados.get("data", []) if isinstance(dados, dict) else []
                    if not lista_editais:
                        break

                    total_varridas += len(lista_editais)

                    for edital in lista_editais:
                        data_fim_raw = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or ""
                        if not validar_data_hora_futura(data_fim_raw):
                            total_ignoradas_vencidas += 1
                            continue

                        orgao_info = edital.get("orgaoEntidade", {})
                        uf_orgao = str(orgao_info.get("ufSigla") or edital.get("uf") or "").upper()
                        orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                        municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "").upper()
                        
                        if uf_orgao and uf_orgao != uf_codigo:
                            continue
                            
                        objeto_descricao = (edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or "")
                        
                        if validar_objeto_licitacao(objeto_descricao):
                            valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                            
                            if stop_loss and hasattr(stop_loss, 'validar_lance'):
                                if not stop_loss.validar_lance(valor_estimado):
                                    total_bloqueadas_stop_loss += 1
                                    continue

                            total_oportunidades_tm += 1
                            achados_cidade += 1
                            cnpj_orgao = re.sub(r"\D", "", str(orgao_info.get("cnpj", "") or edital.get("cnpjOrgao", "")))
                            ano_contrato = edital.get("anoCompra") or edital.get("anoContratacao")
                            seq_contrato = edital.get("sequencialCompra") or edital.get("sequencialContratacao")
                            
                            if cnpj_orgao and ano_contrato and seq_contrato:
                                cnpj_limpo, ano_limpo, seq_limpo = str(cnpj_orgao).strip(), str(ano_contrato).strip(), str(seq_contrato).strip()
                                link_painel_pncp = f"https://pncp.gov.br/app/editais/{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                                pncp_id_str = f"{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                                link_tr_pdf, lista_itens = extrair_detalhes_e_itens_pncp(cnpj_limpo, ano_limpo, seq_limpo, objeto_descricao)
                            else:
                                link_painel_pncp = edital.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais"
                                pncp_id_str = str(edital.get("id", ""))
                                link_tr_pdf, lista_itens = "", [{"descricao": objeto_descricao, "quantidade": 1.0, "valorUnitarioEstimado": 0.0, "valorTotalEstimado": 0.0}]
                            
                            cidade_efetiva = municipio_orgao if municipio_orgao else nome_cidade
                            print(f"   🎯 FOCADO ({cidade_efetiva}): {orgao_nome[:35]} | Valor: R$ {valor_estimado:,.2f} | Itens: {len(lista_itens)}")

                            enviar_oportunidade_para_planilha(orgao_nome, valor_estimado, objeto_descricao, link_painel_pncp)

                            oportunidades_json.append({
                                "orgao": orgao_nome,
                                "valor": valor_estimado,
                                "objeto": objeto_descricao,
                                "cidade": cidade_efetiva,
                                "link_edital": link_painel_pncp,
                                "url_direta": link_painel_pncp,
                                "url_tr": link_tr_pdf if link_tr_pdf else link_painel_pncp,
                                "pncp_id": pncp_id_str,
                                "itens": lista_itens
                            })

                    paginas_restantes = dados.get("paginasRestantes", 0) if isinstance(dados, dict) else 0
                    if paginas_restantes == 0 or pagina >= 5:
                        break
                    pagina += 1
                    time.sleep(0.3)
                except Exception:
                    break

    # ETAPA 2: CATSER (VARREDURA POR CÓDIGOS DE SERVIÇOS DO GOVERNO EM SP)
    print("\n🔍 INICIANDO ETAPA 2: VARREDURA POR CÓDIGOS CATSER (SP)...")
    for catser in CODIGOS_CATSER_TM:
        pagina = 1
        while True:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
            params = {
                "dataInicial": data_inicial_str, "dataFinal": data_final_str,
                "codigoItemCatalogo": catser, "uf": "SP",
                "pagina": pagina, "tamanhoPagina": 50
            }
            try:
                resposta = requests.get(url, params=params, headers=headers, timeout=15)
                if resposta.status_code in [429, 500, 502, 503]:
                    time.sleep(2.0)
                    continue
                if resposta.status_code != 200:
                    break

                dados = resposta.json()
                lista_editais = dados.get("data", []) if isinstance(dados, dict) else []
                if not lista_editais:
                    break

                for edital in lista_editais:
                    data_fim_raw = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or ""
                    if not validar_data_hora_futura(data_fim_raw):
                        total_ignoradas_vencidas += 1
                        continue

                    orgao_info = edital.get("orgaoEntidade", {})
                    orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                    municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "SÃO PAULO").upper()
                    objeto_descricao = (edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or "")
                    valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                    
                    if not validar_objeto_licitacao(objeto_descricao):
                        continue

                    cnpj_orgao = re.sub(r"\D", "", str(orgao_info.get("cnpj", "") or edital.get("cnpjOrgao", "")))
                    ano_contrato = edital.get("anoCompra") or edital.get("anoContratacao")
                    seq_contrato = edital.get("sequencialCompra") or edital.get("sequencialContratacao")
                    
                    if cnpj_orgao and ano_contrato and seq_contrato:
                        cnpj_limpo, ano_limpo, seq_limpo = str(cnpj_orgao).strip(), str(ano_contrato).strip(), str(seq_contrato).strip()
                        link_painel_pncp = f"https://pncp.gov.br/app/editais/{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                        pncp_id_str = f"{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                        link_tr_pdf, lista_itens = extrair_detalhes_e_itens_pncp(cnpj_limpo, ano_limpo, seq_limpo, objeto_descricao)
                    else:
                        link_painel_pncp = edital.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais"
                        pncp_id_str = str(edital.get("id", ""))
                        link_tr_pdf, lista_itens = "", [{"descricao": objeto_descricao, "quantidade": 1.0, "valorUnitarioEstimado": 0.0, "valorTotalEstimado": 0.0}]

                    if not any(item.get("pncp_id") == pncp_id_str for item in oportunidades_json):
                        total_oportunidades_tm += 1
                        print(f"   🎯 FOCADO (CATSER {catser}): {orgao_nome[:35]} | Valor: R$ {valor_estimado:,.2f}")
                        enviar_oportunidade_para_planilha(orgao_nome, valor_estimado, objeto_descricao, link_painel_pncp)

                        oportunidades_json.append({
                            "orgao": orgao_nome,
                            "valor": valor_estimado,
                            "objeto": objeto_descricao,
                            "cidade": municipio_orgao,
                            "link_edital": link_painel_pncp,
                            "url_direta": link_painel_pncp,
                            "url_tr": link_tr_pdf if link_tr_pdf else link_painel_pncp,
                            "pncp_id": pncp_id_str,
                            "itens": lista_itens
                        })

                paginas_restantes = dados.get("paginasRestantes", 0) if isinstance(dados, dict) else 0
                if paginas_restantes == 0 or pagina >= 3:
                    break
                pagina += 1
                time.sleep(0.3)
            except Exception:
                break

    with open("licitacoes.json", "w", encoding="utf-8") as f:
        json.dump(oportunidades_json, f, ensure_ascii=False, indent=4)
    print(f"\n [OK] Finalizado! Total de Oportunidades Válidas Encontradas: {total_oportunidades_tm}")
    print(" [OK] Arquivo 'licitacoes.json' e planilha atualizados com sucesso!")

if __name__ == "__main__":
    executar_mapeamento_pncp()
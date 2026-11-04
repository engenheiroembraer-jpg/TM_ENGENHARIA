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

CODIGOS_CATSER_TM = [
    "8818", "25550", "13412", "2135", "16438"
]

MUNICIPIOS_IBGE = {
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
# MAPEAMENTO DEFINITIVO DE PALAVRAS-CHAVE PERMITIDAS (FILÉ MIGNON TM ENGENHARIA)
# ==============================================================================
TERMOS_PERMITIDOS = [
    # --------------------------------------------------------------------------
    # FRENTE A: SST, LAUDOS, TREINAMENTOS & BOMBEIRO CIVIL (CREA + COPS)
    # --------------------------------------------------------------------------
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b",
    r"\bSEGURANCA DO TRABALHO\b", r"\bLAUDO DE INSALUBRIDADE\b", r"\bLAUDO DE PERICULOSIDADE\b",
    r"\bANALISE ERGONOMICA\b", r"\bAET\b", r"\bELABORACAO DE LAUDO DE SEGURANCA\b",
    r"\bLAUDO\b", r"\bLAUDOS\b", r"\bPERICIA\b", r"\bVISTORIA\b", r"\bINSPECAO\b",
    r"\bTREINAMENTO NR\b", r"\bTREINAMENTO NR-35\b", r"\bCAPACITACAO NR-33\b", r"\bTREINAMENTO NR-20\b",
    r"\bNR-10\b", r"\bNR10\b", r"\bNR-12\b", r"\bNR12\b", r"\bNR-13\b", r"\bNR13\b",
    r"\bNR-33\b", r"\bNR33\b", r"\bNR-35\b", r"\bNR35\b", r"\bNR-20\b", r"\bNR20\b",
    r"\bTREINAMENTO DE BRIGADA DE INCENDIO\b", r"\bBRIGADA DE INCENDIO\b", r"\bTREINAMENTO DE PRIMEIROS SOCORROS\b",
    r"\bAPH\b", r"\bDEA\b", r"\bBOMBEIRO CIVIL\b", r"\bPOSTO DE BOMBEIRO PROFISSIONAL\b",
    r"\bPRESTACAO DE SERVICO DE BRIGADA\b", r"\bAVCB\b", r"\bCLCB\b", r"\bCOMBATE A INCENDIO\b", r"\bCORPO DE BOMBEIROS\b",
    
    # --------------------------------------------------------------------------
    # FRENTE B: ENGENHARIA MECÂNICA, PMOC, ESTRUTURAS & MANUTENÇÃO (CREA MECÂNICA)
    # --------------------------------------------------------------------------
    r"\bPMOC\b", r"\bPLANO DE MANUTENCAO DE AR CONDICIONADO\b", r"\bAR CONDICIONADO\b",
    r"\bHIGIENIZACAO DE DUTOS\b", r"\bSISTEMA DE EXAUSTAO\b", r"\bMANUTENCAO DE CLIMATIZACAO\b",
    r"\bMANUTENCAO PREVENTIVA E CORRETIVA DE AR CONDICIONADO\b", r"\bMANUTENCAO DE SISTEMA DE EXAUSTAO\b",
    r"\bADEQUACAO DE MAQUINAS\b", r"\bPROTECAO DE PARTES MOVEIS\b", r"\bLAUDO DE CONFORMIDADE MECANICA\b",
    r"\bART MECANICA\b", r"\bLAUDO DE LINHA DE VIDA\b", r"\bLINHA DE VIDA\b", r"\bINSPECAO DE ESTRUTURA METÁLICA\b",
    r"\bTESTE DE CARGA\b", r"\bPONTE ROLANTE\b", r"\bPONTES ROLANTES\b", r"\bELEVACAO DE CARGA\b",
    r"\bCALDEIRA\b", r"\bVASO DE PRESSAO\b", r"\bMANUTENCAO DE CALDEIRA\b", r"\bENGENHARIA MECANICA\b",
    r"\bLAUDO TECNICO DE ENGENHARIA\b",
    
    # Eletrificação e Mobilidade
    r"\bCARREGADOR ELETRICO\b", r"\bPONTO DE RECARGA\b", r"\bESTACAO DE RECARGA\b",
    r"\bIT 43\b", r"\bIT-43\b", r"\bCARRO ELETRICO\b", r"\bVEICULO ELETRICO\b", r"\bELETROPOSTO\b"
]

# ==============================================================================
# FRENTE C: BLACKLIST (FILTRO DE EXCLUSÃO RIGOROSO)
# ==============================================================================
TERMOS_PROIBIDOS = [
    r"PISCINA", r"LIMPEZA", r"ZELADORIA", r"JARDINAGEM", r"REFEICAO", r"ALIMENTACAO",
    r"UNIFORME", r"VIGILANCIA", r"SEGURANCA ARMADA", r"TRANSPORTE ESCOLAR", r"LOCACAO DE VEICULO",
    r"LOCACAO DE VEICULOS LEVES", r"GELADEIRA", r"ODONTOLOG", r"MEDICO", r"TOPOGRAFIA", 
    r"AQUISICAO DE PECA", r"PECA DE REPOSICAO", r"AUTOMOTIV", r"VEICULO", r"INFORMATICA", 
    r"COMPUTADOR", r"CADEIRA ODONTOLOGICA", r"OFICINA MECANICA", r"OBRA CIVIL PESADA",
    r"PAVIMENTACAO ASFALTICA", r"PAVIMENTACAO", r"FORNECIMENTO DE ALIMENTACAO"
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

def enviar_alerta_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}, timeout=5)
    except Exception: 
        pass

def executar_mapeamento_pncp():
    print("==================================================================")
    print("🚀 INICIANDO MONITORAMENTO REFINADO (SST + MECÂNICA + COPS) - TM ENGENHARIA")
    print("==================================================================")
    
    stop_loss = StopLossManager() if StopLossManager else None
    
    data_hoje_dt = datetime.now()
    hoje_str = data_hoje_dt.strftime("%Y-%m-%d")
    
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

    # ETAPA 1: MUNICÍPIOS
    for codigo_ibge, nome_cidade in MUNICIPIOS_IBGE.items():
        print(f"\n🔍 Varrendo Cidade: {nome_cidade}...")
        
        for modalidade in MODALIDADES_PNCP:
            pagina = 1
            while True:
                url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
                params = {
                    "dataInicial": data_inicial_str,
                    "dataFinal": data_final_str,
                    "codigoModalidadeContratacao": modalidade,
                    "uf": "SP",
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
                        if data_fim_raw:
                            if str(data_fim_raw).split("T")[0] < hoje_str:
                                total_ignoradas_vencidas += 1
                                continue

                        orgao_info = edital.get("orgaoEntidade", {})
                        uf_orgao = str(orgao_info.get("ufSigla") or edital.get("uf") or "").upper()
                        orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                        municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "").upper()
                        
                        if uf_orgao and uf_orgao != "SP":
                            continue
                            
                        orgao_nome_limpo = remover_acentos(orgao_nome)
                        municipio_orgao_limpo = remover_acentos(municipio_orgao)
                        nome_cidade_limpo = remover_acentos(nome_cidade)

                        cidade_valida = any(
                            cidade in orgao_nome_limpo or 
                            cidade in municipio_orgao_limpo or 
                            cidade == nome_cidade_limpo 
                            for cidade in NOMES_CIDADES_VALIDAS
                        )
                        if not cidade_valida:
                            continue

                        cidade_efetiva = municipio_orgao if municipio_orgao else nome_cidade
                        objeto_descricao = (edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or "")
                        
                        if validar_objeto_licitacao(objeto_descricao):
                            valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                            
                            if stop_loss and hasattr(stop_loss, 'validar_lance'):
                                if not stop_loss.validar_lance(valor_estimado):
                                    total_bloqueadas_stop_loss += 1
                                    continue

                            total_oportunidades_tm += 1
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
                            
                            print(f"   🎯 FOCADO ({cidade_efetiva}): {orgao_nome[:35]} | Itens: {len(lista_itens)}")
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

    # ETAPA 2: CATSER
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
                    if data_fim_raw and str(data_fim_raw).split("T")[0] < hoje_str:
                        total_ignoradas_vencidas += 1
                        continue

                    orgao_info = edital.get("orgaoEntidade", {})
                    orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                    municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "SÃO PAULO").upper()
                    objeto_descricao = (edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or "")
                    valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                    
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
    print(" [OK] Arquivo 'licitacoes.json' atualizado com sucesso com todos os novos termos de SST, Mecânica e COPS!")

if __name__ == "__main__":
    executar_mapeamento_pncp()
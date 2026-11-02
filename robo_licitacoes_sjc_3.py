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

TELEGRAM_TOKEN = "8269224927:AAHb26HEwbFWBeRtQpkOFHGVZLrEYlbuW4s"
TELEGRAM_CHAT_ID = "7193404104"

# ==============================================================================
# 47 Cidades Mapeadas do Vale do Paraíba, Litoral Norte, Alto Tietê e SP
# ==============================================================================
MUNICIPIOS_IBGE = {
    # Vale do Paraíba & Litoral Norte (36 Municípios)
    "3549904": "SAO JOSE DOS CAMPOS",
    "3554102": "TAUBATE",
    "3524402": "JACAREI",
    "3538006": "PINDAMONHANGABA",
    "3518404": "GUARATINGUETA",
    "3555406": "UBATUBA",
    "3550704": "SAO SEBASTIAO",
    "3520400": "ILHABELA",
    "3510500": "CARAGUATATUBA",
    "3508504": "CACAPAVA",
    "3527207": "LORENA",
    "3513405": "CRUZEIRO",
    "3502507": "APARECIDA",
    "3554805": "TREMEMBE",
    "3550007": "SAO LUIZ DO PARAITINGA",
    "3510906": "CAMPOS DO JORDAO",
    "3549706": "SANTO ANTONIO DO PINHAL",
    "3548609": "SAO BENTO DO SAPUCAI",
    "3546306": "SANTA BRANCA",
    "3520202": "IGARATA",
    "3535606": "PARAIBUNA",
    "3524907": "JAMBEIRO",
    "3542404": "REDENCAO DA SERRA",
    "3532306": "NATIVIDADE DA SERRA",
    "3551900": "SILVEIRAS",
    "3513603": "CUNHA",
    "3508603": "CACHOEIRA PAULISTA",
    "3509700": "CANAS",
    "3540754": "POTIM",
    "3544301": "ROSEIRA",
    "3526308": "LAGOINHA",
    "3526605": "LAVRINHAS",
    "3541901": "QUELUZ",
    "3504909": "BANANAL",
    "3503158": "ARAAPEI",
    "3549607": "SAO JOSE DO BARREIRO",

    # Grande SP, Baixada & Alto Tietê Estratégico (11 Municípios)
    "3550308": "SAO PAULO",
    "3548500": "SANTOS",
    "3530607": "MOGI DAS CRUZES",
    "3552502": "SUZANO",
    "3518800": "ARUJA",
    "3546801": "SANTA ISABEL",
    "3539806": "POA",
    "3515707": "FERRAZ DE VASCONCELOS",
    "3523107": "ITAQUAQUECETUBA",
    "3545001": "SALESOPOLIS",
    "3518305": "GUARULHOS"
}

NOMES_CIDADES_VALIDAS = list(MUNICIPIOS_IBGE.values())

MODALIDADES_PNCP = [6, 8, 4, 1, 2, 3, 5, 7]

TERMOS_PERMITIDOS = [
    r"\bPGR\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bSEGURANCA DO TRABALHO\b",
    r"\bLAUDO DE INSALUBRIDADE\b", r"\bLAUDO DE PERICULOSIDADE\b",
    r"\bANALISE ERGONOMICA\b", r"\bAET\b", r"\bLAUDO\b", r"\bLAUDOS\b",
    r"\bNR-10\b", r"\bNR10\b", r"\bNR-12\b", r"\bNR12\b", r"\bNR-13\b", r"\bNR13\b",
    r"\bNR-33\b", r"\bNR33\b", r"\bNR-35\b", r"\bNR35\b", r"\bTREINAMENTO NR\b",
    r"\bBRIGADA DE INCENDIO\b", r"\bPMOC\b", r"\bAR CONDICIONADO\b",
    r"\bADEQUACAO DE MAQUINAS\b", r"\bCALDEIRA\b", r"\bVASO DE PRESSAO\b",
    r"\bENGENHARIA MECANICA\b", r"\bSISTEMA DE EXAUSTAO\b", r"\bMANUTENCAO\b",
    r"\bAVCB\b", r"\bCLCB\b", r"\bCOMBATE A INCENDIO\b", r"\bCORPO DE BOMBEIROS\b",
    r"\bLAUDO TECNICO DE ENGENHARIA\b", r"\bPERICIA\b", r"\bVISTORIA\b", r"\bINSPECAO\b",
    r"\bCARREGADOR ELETRICO\b", r"\bPONTO DE RECARGA\b", r"\bESTACAO DE RECARGA\b",
    r"\bIT 43\b", r"\bIT-43\b", r"\bCARRO ELETRICO\b", r"\bVEICULO ELETRICO\b", r"\bELETROPOSTO\b"
]

TERMOS_PROIBIDOS = [
    r"PISCINA", r"LIMPEZA", r"ZELADORIA", r"JARDINAGEM", r"REFEICAO", r"ALIMENTACAO",
    r"UNIFORME", r"VIGILANCIA", r"SEGURANCA ARMADA", r"TRANSPORTE ESCOLAR", r"LOCACAO DE VEICULO"
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

def enviar_oportunidade_para_planilha(orgao, valor_estimado, objeto, link_edital=""):
    params = {
        "tipo": "sheet",
        "orgao": orgao,
        "valor": str(valor_estimado),
        "objeto": objeto,
        "escopo": objeto,
        "link_edital": link_edital
    }
    try:
        response = requests.get(URL_PLANILHA_TM, params=params, timeout=10)
        if response.status_code == 200:
            print("   📊 [PLANILHA] Oportunidade enviada para o Google Sheets com sucesso!")
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
    print("🚀 INICIANDO MONITORAMENTO - TM ENGENHARIA CONSULTORIA")
    print("==================================================================")
    
    stop_loss = StopLossManager() if StopLossManager else None
    
    data_fim = datetime.now()
    data_ini = data_fim - timedelta(days=90)
    
    data_inicial_str = data_ini.strftime("%Y%m%d")
    data_final_str = data_fim.strftime("%Y%m%d")
    
    total_varridas = 0
    total_oportunidades_tm = 0
    total_bloqueadas_stop_loss = 0

    oportunidades_json = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

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
                    if resposta.status_code != 200:
                        break

                    dados = resposta.json()
                    lista_editais = dados.get("data", []) if isinstance(dados, dict) else []
                    
                    if not lista_editais:
                        break

                    total_varridas += len(lista_editais)

                    for edital in lista_editais:
                        orgao_info = edital.get("orgaoEntidade", {})
                        uf_orgao = str(orgao_info.get("ufSigla") or edital.get("uf") or "").upper()
                        orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                        municipio_orgao = str(orgao_info.get("municipioNome") or "").upper()
                        
                        if uf_orgao and uf_orgao != "SP":
                            continue
                            
                        cidade_valida = any(cidade in orgao_nome or cidade in municipio_orgao or cidade == nome_cidade for cidade in NOMES_CIDADES_VALIDAS)
                        if not cidade_valida:
                            continue

                        objeto_descricao = (
                            edital.get("objetoCompra") or 
                            edital.get("objetoContratacao") or 
                            edital.get("objeto") or ""
                        )
                        
                        if validar_objeto_licitacao(objeto_descricao):
                            valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                            
                            if stop_loss and hasattr(stop_loss, 'validar_lance'):
                                if not stop_loss.validar_lance(valor_estimado):
                                    total_bloqueadas_stop_loss += 1
                                    print(f"   🛑 [STOP LOSS] Oportunidade ignorada devido ao valor: R$ {valor_estimado:,.2f}")
                                    continue

                            total_oportunidades_tm += 1
                            
                            # MONTAGEM DA URL DO EDITAL (CORRIGIDA E INDENTADA)
                            cnpj_orgao = re.sub(r"\D", "", str(orgao_info.get("cnpj", "") or edital.get("cnpjOrgao", "")))
                            ano_contrato = edital.get("anoCompra") or edital.get("anoContratacao")
                            seq_contrato = edital.get("sequencialCompra") or edital.get("sequencialContratacao")
                            
                            if cnpj_orgao and ano_contrato and seq_contrato:
                                cnpj_limpo = str(cnpj_orgao).strip()
                                ano_limpo = str(ano_contrato).strip()
                                seq_limpo = str(seq_contrato).strip()
                                link_painel_pncp = f"https://pncp.gov.br/app/editais/{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                                pncp_id_str = f"{cnpj_limpo}/{ano_limpo}/{seq_limpo}"
                            else:
                                link_painel_pncp = edital.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais"
                                pncp_id_str = str(edital.get("id", ""))
                            
                            print(f"   🎯 FOCADO ({nome_cidade}): {orgao_nome[:35]} | Link: {link_painel_pncp}")
                            
                            enviar_oportunidade_para_planilha(orgao_nome, valor_estimado, objeto_descricao, link_painel_pncp)
                            
                            msg_telegram = (
                                f"🎯 *NOVA OPORTUNIDADE FILTRADA!*\n\n"
                                f"🏢 *Órgão:* {orgao_nome}\n"
                                f"📍 *Cidade:* {nome_cidade} (SP)\n"
                                f"💰 *Valor Estimado:* R$ {valor_estimado:,.2f}\n"
                                f"📋 *Objeto:* {objeto_descricao[:180]}...\n\n"
                                f"🔗 [Abrir Painel Oficial do Edital]({link_painel_pncp})"
                            )
                            enviar_alerta_telegram(msg_telegram)

                            oportunidades_json.append({
                                "orgao": orgao_nome,
                                "valor": valor_estimado,
                                "objeto": objeto_descricao,
                                "cidade": nome_cidade,
                                "link_edital": link_painel_pncp,
                                "url_direta": link_painel_pncp,
                                "pncp_id": pncp_id_str
                            })

                    paginas_restantes = dados.get("paginasRestantes", 0) if isinstance(dados, dict) else 0
                    if paginas_restantes == 0 or pagina >= 5:
                        break
                    pagina += 1
                    time.sleep(0.1)

                except Exception:
                    break

    print("\n==================================================")
    print(f"📋 FIM DA VARREDURA! Analisados: {total_varridas} | Injetados: {total_oportunidades_tm} | Bloqueados (Stop Loss): {total_bloqueadas_stop_loss}")
    print("==================================================")

    with open("licitacoes.json", "w", encoding="utf-8") as f:
        json.dump(oportunidades_json, f, ensure_ascii=False, indent=4)
    print(" [OK] Arquivo 'licitacoes.json' gerado com sucesso com os Links Diretos!")

if __name__ == "__main__":
    executar_mapeamento_pncp()
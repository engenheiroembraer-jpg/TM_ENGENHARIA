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
# CONFIGURAÇÕES E APIS OFICIAIS (COMPRAS.GOV.BR V3)
# ==============================================================================
BASE_URL = "https://dadosabertos.compras.gov.br"
ENDPOINT_SERVICO = "/modulo-pesquisa-preco/3_consultarServico"
URL_PLANILHA_TM = "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"

TELEGRAM_TOKEN = "8269224927:AAGzNVzbb4b8-JDaroQfyWklQh1ISxZPWFw"
TELEGRAM_CHAT_ID = "7193404104"

# ==============================================================================
# FUNÇÕES DE TRATAMENTO E EXTRAÇÃO AVANÇADA DE VALORES
# ==============================================================================
def remover_acentos(texto: str) -> str:
    if not texto: return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

def extrair_valor_real(item: dict) -> float:
    """Extrai o valor numérico de qualquer campo retornado pela API OpenAPI do Compras.gov.br."""
    chaves = [
        "precoPraticado", "valorUnitario", "valorEstimado", "valorTotal", 
        "valorTotalEstimado", "valorHomologado", "precoUnitario", "valorItem",
        "valor_unitario", "valor_total", "preco_praticado", "valor"
    ]
    for ch in chaves:
        val = item.get(ch)
        if val is not None:
            try:
                v = float(str(val).replace(",", "."))
                if v > 0:
                    return v
            except (ValueError, TypeError):
                continue
    return 0.0

# ==============================================================================
# CÓDIGOS CATSER DE INTERESSE - TM ENGENHARIA
# ==============================================================================
CODIGOS_CATSER_TM = [
    8818,    # Serviços de Engenharia de Segurança do Trabalho
    25550,   # Consultoria e Assessoria - Engenharia
    13412,   # Manutenção / Instalação de Sistema de Combate a Incêndio
    16438,   # Treinamento e Capacitação Profissional (NRs, Brigada)
    25470,   # Vistoria, Validação e Certificação (AVCB / CLCB)
    242497,  # Serviço de Vistoria e Emissão de Laudos de Segurança
    25518,   # Inspeção e Ensaio Não Destrutivo
    25496,   # Laudos Técnicos de Engenharia
    23639    # Elaboração / Análise de Projetos de Engenharia
]

# ==============================================================================
# SUAS CIDADES PRIORITÁRIAS (VALE DO PARAÍBA / REGIONAL)
# ==============================================================================
CIDADES_PRIORITARIAS = [
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

NOMES_CIDADES_CLEAN = [remover_acentos(c) for c in CIDADES_PRIORITARIAS]

TERMOS_PERMITIDOS = [
    r"\bAVCB\b", r"\bCLCB\b", r"INCENDIO", r"BRIGADA", r"BOMBEIRO",
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
    r"SEGURANCA.*TRABALHO", r"SAUDE.*TRABALHO", r"SAUDE.*OCUPACIONAL",
    r"INSALUBRIDADE", r"PERICULOSIDADE", r"ERGONOMIC", r"SST",
    r"NR-?10\b", r"NR-?12\b", r"NR-?13\b", r"NR-?18\b", r"NR-?33\b", r"NR-?35\b",
    r"TREINAMENTO", r"CURSO", r"ADEQUACAO", r"LAUDO", r"ENG", r"VISTORIA", r"ART"
]

TERMOS_PROIBIDOS = [
    r"\bTENIS\b", r"\bSAPATO\b", r"\bBOTINA\b", r"\bUNIFORME\b", r"\bCAMISA\b", r"\bCALCA\b",
    r"\bCAFÉ\b", r"\bCAFE\b", r"\bACUCAR\b", r"\bPAO\b", r"\bALIMENTIC\b", r"\bGENEROS\b",
    r"\bMEDICAMENTO\b", r"\bHOSPITALAR\b", r"\bVACINA\b", r"\bIMPRESSORA\b", r"\bCOMPUTADOR\b",
    r"\bLIMPEZA\b", r"\bZELADORIA\b", r"\bJARDINAGEM\b", r"\bGASOLINA\b", r"\bDIESEL\b"
]

def validar_regiao(cidade_nome: str, orgao_nome: str) -> bool:
    texto_busca = remover_acentos(f"{cidade_nome} {orgao_nome}")
    return any(cid in texto_busca for cid in NOMES_CIDADES_CLEAN)

def validar_objeto(objeto_texto: str) -> bool:
    texto_tratado = remover_acentos(objeto_texto)
    if any(re.search(re.compile(termo, re.IGNORECASE), texto_tratado) for termo in TERMOS_PROIBIDOS):
        return False
    if any(re.search(re.compile(termo, re.IGNORECASE), texto_tratado) for termo in TERMOS_PERMITIDOS):
        return True
    return True

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

def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass

def executar_mapeamento_compras_gov():
    print("==================================================================")
    print("🚀 MONITORAMENTO DIRETO COMPRAS.GOV.BR (REGIONAL COM VALORES REALISTA)")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    
    hoje = datetime.now()
    dt_inicio = (hoje - timedelta(days=90)).strftime("%Y-%m-%d")
    dt_fim = hoje.strftime("%Y-%m-%d")

    total_oportunidades_tm = 0
    oportunidades_json = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "accept": "*/*"
    }

    url_consulta = f"{BASE_URL}{ENDPOINT_SERVICO}"

    for catser in CODIGOS_CATSER_TM:
        pagina = 1
        print(f"\n📌 Pesquisando CATSER: {catser} (Filtro Regional | {dt_inicio} a {dt_fim})...")

        while pagina <= 5:
            params = {
                "pagina": pagina,
                "tamanhoPagina": 50,
                "codigoItemCatalogo": catser,
                "estado": "SP",
                "dataCompraInicio": dt_inicio,
                "dataCompraFim": dt_fim
            }

            try:
                resposta = requests.get(url_consulta, params=params, headers=headers, timeout=15)
                if resposta.status_code != 200:
                    break

                dados = resposta.json()
                lista_compras = dados.get("resultado") or dados.get("data") or dados.get("itens") or [] if isinstance(dados, dict) else (dados if isinstance(dados, list) else [])

                if not lista_compras:
                    break

                for item in lista_compras:
                    cidade = str(item.get("nomeMunicipio") or item.get("municipio") or item.get("cidade") or "").upper()
                    orgao_nome = str(item.get("nomeOrgao") or item.get("orgaoRazaoSocial") or item.get("nomeUasg") or "ÓRGÃO PÚBLICO").upper()

                    # Trava de Região: filtra Brodowski e outras cidades fora do escopo
                    if not validar_regiao(cidade, orgao_nome):
                        continue

                    objeto = item.get("descricaoItem") or item.get("objetoCompra") or item.get("nomeServico") or item.get("objeto") or ""
                    
                    if validar_objeto(objeto):
                        valor_real = extrair_valor_real(item)

                        if stop_loss and hasattr(stop_loss, 'validar_lance') and valor_real > 0:
                            if not stop_loss.validar_lance(valor_real):
                                continue

                        uasg = str(item.get("codigoUasg") or item.get("uasg") or "")
                        id_compra = str(item.get("idCompra") or item.get("id") or f"{catser}_{uasg}_{hash(objeto)}")

                        if not any(op.get("id") == id_compra for op in oportunidades_json):
                            total_oportunidades_tm += 1
                            link_direto = f"https://www.comprasnet.gov.br/consultalicitacoes/ConsLicitacao_Frame.asp?coduasg={uasg}" if uasg else "https://compras.gov.br"

                            txt_val = f"R$ {valor_real:,.2f}" if valor_real > 0 else "Sob Consulta (Edital)"
                            cid_exibid = cidade if cidade and cidade != "SP" else "REGIONAL SP"

                            print(f"   🎯 OPORTUNIDADE ({cid_exibid}): {orgao_nome[:35]} | Valor: {txt_val}")

                            enviar_oportunidade_para_planilha(orgao_nome, valor_real, objeto, link_direto)

                            enviar_telegram(
                                f"🏛️ *OPORTUNIDADE ENCONTRADA (COMPRAS.GOV.BR)!*\n\n"
                                f"🏢 *Órgão:* {orgao_nome}\n"
                                f"📍 *Cidade:* {cid_exibid}\n"
                                f"💰 *Valor:* {txt_val}\n"
                                f"📝 *Objeto:* _{objeto[:200]}_\n\n"
                                f"🔗 [Ver no Compras.gov.br]({link_direto})"
                            )

                            oportunidades_json.append({
                                "id": id_compra,
                                "orgao": orgao_nome,
                                "valor": valor_real,
                                "objeto": objeto,
                                "cidade": cid_exibid,
                                "link_edital": link_direto,
                                "catser": catser
                            })

                if len(lista_compras) < 50:
                    break

                pagina += 1
                time.sleep(0.4)

            except Exception as e:
                print(f"  ⚠️ Aviso na consulta do CATSER {catser}: {e}")
                break

    with open("licitacoes.json", "w", encoding="utf-8") as f:
        json.dump(oportunidades_json, f, ensure_ascii=False, indent=4)

    print("\n==================================================================")
    print(f"✅ FINALIZADO! Total de Oportunidades Encontradas: {total_oportunidades_tm}")
    print("✅ Planilha Google, Telegram e 'licitacoes.json' sincronizados!")
    print("==================================================================")

if __name__ == "__main__":
    executar_mapeamento_compras_gov()
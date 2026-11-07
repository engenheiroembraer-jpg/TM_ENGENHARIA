import os
import re
import time
import json
import unicodedata
import requests
from datetime import datetime, timedelta

# ==============================================================================
# MÓDULO STOP LOSS (OPCIONAL)
# ==============================================================================
try:
    from stoplossmanager import StopLossManager
except ImportError:
    StopLossManager = None

# ==============================================================================
# CONFIGURAÇÕES E ENDPOINTS (PNCP LEI 14.133/2021)
# ==============================================================================
URL_PNCP = "https://pncp.gov.br"
URL_PLANILHA_TM = "https://script.google.com/macros/s/AKfycbxBhdjr_mhGsfNhLyT3Trx6aQZgjkoRsMCfeZK01HMTn85Gg5qAsK_Kfzcl_FT0a03f/exec"

TELEGRAM_TOKEN = "8269224927:AAGzNVzbb4b8-JDaroQfyWklQh1ISxZPWFw"
TELEGRAM_CHAT_ID = "7193404104"

# ==============================================================================
# CÓDIGOS CATSER DE INTERESSE - TM ENGENHARIA
# ==============================================================================
CODIGOS_CATSER_TM = [
    8818,    # Engenharia de Segurança do Trabalho
    25550,   # Consultoria/Assessoria Engenharia
    13412,   # Combate a Incêndio / AVCB
    16438,   # Treinamentos / NRs / Brigada
    25470,   # Vistoria e Laudos AVCB/CLCB
    242497,  # Laudos de Segurança
    25518,   # Inspeções / Ensaios
    25496,   # Laudos Técnicos Engenharia
    23639    # Projetos de Engenharia
]

# ==============================================================================
# SUAS 47 CIDADES AUTORIZADAS (VALE, LITORAL, ALTO TIETÊ, SP, SANTOS)
# ==============================================================================
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

TERMOS_PERMITIDOS_AMPLOS = [
    "AVCB", "CLCB", "INCENDIO", "BRIGADA DE INCENDIO", "PGR", "GRO", "LTCAT", 
    "PCMSO", "PPP", "AET", "SEGURANCA DO TRABALHO", "SAUDE DO TRABALHO", 
    "INSALUBRIDADE", "PERICULOSIDADE", "ERGONOMIA", "ERGONOMICO", "SST",
    "NR-10", "NR-12", "NR-13", "NR-18", "NR-33", "NR-35", "NR10", "NR12", "NR13",
    "NR18", "NR33", "NR35", "LINHA DE VIDA", "ANCORAGEM", "PMOC", "AR CONDICIONADO",
    "LAUDO TECNICO DE ENGENHARIA", "LAUDO ERGONOMICO", "LAUDO DE SPDA", "PARA-RAIOS",
    "PROJETO DE INCENDIO", "PROJETO EXECUTIVO DE INCENDIO", "VISTORIA DE INCENDIO",
    "TREINAMENTO DE BRIGADA", "TREINAMENTO NR"
]

TERMOS_PROIBIDOS = [
    # --- GÊNEROS ALIMENTÍCIOS / COPA / FESTAS / RESTAURANTE ---
    r"CAFÉ", r"CAFE", r"ACUCAR", r"AÇÚCAR", r"PAO", r"PÃO", r"ALIMENTIC", r"GENEROS", 
    r"BISCOITO", r"LEITE", r"ALIMENTACAO", r"REFEICAO", r"HORTIFRUTI", r"CARNE", r"MANTIMENTOS",
    r"CESTA BASICA", r"PANIFICAC", r"MARMITA", r"LANCHE", r"AGUA MINISTERIAL", r"BEBIDA",

    # --- SAÚDE / MATERIAL HOSPITALAR / FARMÁCIA / ESTÉTICA ---
    r"RADIOGRAF", r"RAIO-X", r"RAIO X", r"MEDICO", r"MEDICAMENTO", r"EXAME", r"HOSPITALAR",
    r"GEL CONDUTOR", r"DERMATOLOGIC", r"ODONTOLOG", r"CADEIRA ODONTOLOGICA", r"VACINA",
    r"PACIENTE", r"FARMAC", r"INSUMOS HOSPITALARES", r"CURATIVO", r"SERINGA", r"AMBULATORIO",

    # --- PEÇAS SOLTAS / ELETRÔNICOS / TI / ESCRITÓRIO / MÓVEIS ---
    r"IMPRESSORA", r"DRONE", r"DISPLAY", r"CAPACITOR", r"PLACA ELETRONICA", r"COMPUTADOR", 
    r"INFORMATICA", r"AQUISICAO DE PECA", r"PECA DE REPOSICAO", r"AUTOMOTIV", r"VEICULO", 
    r"CADEIRA ERGONOMIC", r"CADEIRA DE ESCRITORIO", r"CADEIRA COM APOIO", r"MOBILES",
    r"CARTUCHO", r"TONER", r"TECLADO", r"MOUSE", r"MONITOR", r"NOBREAK",

    # --- SERVIÇOS DIVERSOS E MATERIAIS FORA DO ESCOPO DE ENGENHARIA ---
    r"CAES", r"GATOS", r"VETERINAR", r"ANIMAL", r"PISCINA", r"LIMPEZA", r"ZELADORIA", 
    r"JARDINAGEM", r"UNIFORME", r"VIGILANCIA", r"SEGURANCA ARMADA", r"TRANSPORTE ESCOLAR", 
    r"LOCACAO DE VEICULO", r"GELADEIRA", r"TOPOGRAFIA", r"OFICINA MECANICA", r"ARGILA", 
    r"MODELAGEM", r"OBRA CIVIL PESADA", r"PAVIMENTACAO ASFALTICA", r"PAVIMENTACAO",
    r"SHOW", r"EVENTO", r"ARTISTICO", r"PNEU", r"COMBUSTIVEL", r"GASOLINA", r"DIESEL"
]

def validar_regiao(cidade_orgao: str, nome_orgao: str) -> tuple[bool, str]:
    texto = remover_acentos(f"{cidade_orgao} {nome_orgao}")
    for cid in CIDADES_CLEAN:
        if cid in texto:
            return True, cid
    return True, cidade_orgao if cidade_orgao else "SP REGIONAL"

def validar_objeto(objeto_texto: str) -> bool:
    texto = remover_acentos(objeto_texto)
    if any(p in texto for p in TERMOS_PROIBIDOS):
        return False
    if any(p in texto for p in TERMOS_PERMITIDOS_AMPLOS):
        return True
    return True

def validar_data_futura(data_fim_raw: str) -> bool:
    if not data_fim_raw:
        return True
    try:
        data_str = str(data_fim_raw).replace("Z", "").split(".")[0]
        if "T" in data_str:
            dt_limite = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S")
        else:
            dt_limite = datetime.strptime(data_str[:10], "%Y-%m-%d")
        return dt_limite >= datetime.now().replace(hour=0, minute=0, second=0)
    except Exception:
        return True

def enviar_planilha(orgao, valor, objeto, link):
    try:
        requests.get(URL_PLANILHA_TM, params={
            "tipo": "sheet", "orgao": orgao, "valor": str(valor),
            "objeto": objeto, "escopo": objeto, "pncp": link
        }, timeout=5)
    except Exception:
        pass

def enviar_telegram(mensagem: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass

def executar():
    print("==================================================================")
    print("🚀 BUSCA EXPANDIDA DE EDITAIS EM ABERTO (ESTADO DE SP / SUAS CIDADES)")
    print("==================================================================")

    stop_loss = StopLossManager() if StopLossManager else None
    
    hoje = datetime.now()
    dt_inicio = (hoje - timedelta(days=60)).strftime("%Y%m%d")
    dt_fim = hoje.strftime("%Y%m%d")

    total_oportunidades = 0
    oportunidades_json = []

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # BUSCA GLOBAL NO ESTADO DE SP VIA MODALIDADES ATIVAS (DISPENSAS E LICITAÇÕES)
    for modalidade in [6, 8, 4, 1, 2, 3, 5, 7]:
        pagina = 1
        print(f"\n📌 Buscando Modalidade PNCP [{modalidade}] no Estado de SP...")
        
        while pagina <= 5:
            url = f"{URL_PNCP}/api/consulta/v1/contratacoes/publicacao"
            params = {
                "dataInicial": dt_inicio,
                "dataFinal": dt_fim,
                "codigoModalidadeContratacao": modalidade,
                "uf": "SP",
                "pagina": pagina,
                "tamanhoPagina": 50
            }

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=10)
                if resp.status_code != 200:
                    break

                dados = resp.json()
                lista = dados.get("data", []) if isinstance(dados, dict) else []
                if not lista:
                    break

                for edital in lista:
                    # 1. Valida se a data limite de proposta está no futuro
                    data_fim_raw = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or ""
                    if not validar_data_futura(data_fim_raw):
                        continue

                    objeto = edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or ""
                    if not validar_objeto(objeto):
                        continue

                    orgao_info = edital.get("orgaoEntidade", {})
                    orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "ÓRGÃO PÚBLICO").upper()
                    municipio_orgao = str(orgao_info.get("municipioNome") or edital.get("municipioNome") or "SÃO PAULO").upper()

                    # 2. Valida regionalização
                    eh_da_regiao, cidade_identificada = validar_regiao(municipio_orgao, orgao_nome)
                    if not eh_da_regiao:
                        continue

                    valor_estimado = float(edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0)

                    if stop_loss and hasattr(stop_loss, 'validar_lance') and valor_estimado > 0:
                        if not stop_loss.validar_lance(valor_estimado):
                            continue

                    cnpj = re.sub(r"\D", "", str(orgao_info.get("cnpj") or edital.get("cnpjOrgao") or ""))
                    ano = edital.get("anoCompra") or edital.get("anoContratacao")
                    seq = edital.get("sequencialCompra") or edital.get("sequencialContratacao")

                    id_unico = f"{cnpj}_{ano}_{seq}" if (cnpj and ano and seq) else f"{modalidade}_{hash(objeto)}"
                    
                    if not any(op.get("id") == id_unico for op in oportunidades_json):
                        total_oportunidades += 1
                        link_direto = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else "https://pncp.gov.br"

                        txt_valor = f"R$ {valor_estimado:,.2f}" if valor_estimado > 0 else "Sob Consulta em Edital"
                        print(f"   🎯 EDITAL EM ABERTO ({cidade_identificada}): {orgao_nome[:35]} | Valor: {txt_valor}")

                        enviar_planilha(orgao_nome, valor_estimado, objeto, link_direto)
                        enviar_telegram(
                            f"🔥 *OPORTUNIDADE EM ABERTO (PNCP)!*\n\n"
                            f"🏢 *Órgão:* {orgao_nome}\n"
                            f"📍 *Cidade:* {cidade_identificada}\n"
                            f"💰 *Valor Estimado:* {txt_valor}\n"
                            f"📝 *Objeto:* _{objeto[:200]}_\n\n"
                            f"🔗 [Acessar Edital PNCP]({link_direto})"
                        )

                        oportunidades_json.append({
                            "id": id_unico,
                            "orgao": orgao_nome,
                            "valor": valor_estimado,
                            "objeto": objeto,
                            "cidade": cidade_identificada,
                            "link_edital": link_direto
                        })

                pagina += 1
                time.sleep(0.1)

            except Exception:
                break

    with open("licitacoes.json", "w", encoding="utf-8") as f:
        json.dump(oportunidades_json, f, ensure_ascii=False, indent=4)

    print("\n==================================================================")
    print(f"✅ FINALIZADO! Total Real de Oportunidades em Aberto Encontradas: {total_oportunidades}")
    print("==================================================================")

if __name__ == "__main__":
    executar()
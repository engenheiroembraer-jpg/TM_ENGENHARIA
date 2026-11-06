import os
import re
import time
import json
import unicodedata
import requests
from datetime import datetime, timedelta

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
    "2135",    # Manutenção Preventiva e Corretiva de Ar Condicionado / PMOC
    "16438",   # Treinamento e Capacitação Profissional (NRs, Brigada)
    "25470",   # Vistoria, Validação e Certificação (AVCB / CLCB)
    "242497",  # Serviço de Vistoria e Emissão de Laudos de Segurança
    "25518",   # Inspeção e Ensaio Não Destrutivo (Vasos, Caldeiras, Estruturas)
    "25496",   # Laudos Técnicos de Engenharia Mecânica / Estrutural
    "23639"    # Elaboração / Análise de Projetos de Engenharia
]

# ==============================================================================
# MAPEAMENTO DE MUNICÍPIOS IBGE (APENAS ESTADO DE SÃO PAULO)
# ==============================================================================
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

MODALIDADES_PNCP = [6, 8, 4, 1, 2, 3, 5, 7]

# ==============================================================================
# RADICAIS COMBINADOS (FILÊ MIGNON / ENGENHARIA / SST / AVCB / PMOC)
# ==============================================================================
TERMOS_PERMITIDOS = [
    r"AVCB", r"CLCB", r"INCENDIO", r"BOMBEIR", r"BRIGADA", r"SPRINKLER", r"HIDRANTE",
    r"EXTINTOR", r"PRESSURIZAC", r"ALARME.*INCENDIO", r"DETECCAO.*INCENDIO", r"SISTEMA.*INCENDIO",
    r"\bPGR\b", r"\bGRO\b", r"\bLTCAT\b", r"\bPCMSO\b", r"\bPPP\b", r"\bAET\b",
    r"SEGURANCA.*TRABALHO", r"INSALUBRIDADE", r"PERICULOSIDADE", r"ERGONOMIC",
    r"NR-?\d{1,2}\b", r"ESOCIAL", r"S-22\d{2}", r"SAUDE.*OCUPACIONAL",
    r"PMOC", r"CLIMATIZAC", r"EXAUSTAO", r"DUTO",
    r"MANUTENCAO.*AR", r"INSTALACAO.*AR", r"HIGIENIZACAO.*AR",
    r"LINHA.*VIDA", r"PONTE.*ROLANTE", r"CALDEIRA", r"VASO.*PRESSAO",
    r"ESTRUTURA.*MET", r"ART.*MECANIC", r"ADEQUACAO.*MAQUINA", r"PROTECAO.*MAQUINA", r"PARTES.*MOVEIS",
    r"CARREGADOR.*ELETRIC", r"RECARGA.*ELETRIC", r"IT-?43", r"ELETROPOSTO",
    r"LAUDO.*ENGENHARIA", r"LAUDO.*TECNICO", r"PERICIA.*ENGENHARIA", r"VISTORIA.*ENGENHARIA",
    r"LAUDO.*CONFORMIDADE", r"LAUDO.*ESTRUTURAL", r"INSPECAO.*TECNICA", r"ANALISE.*TECNICA"
]

TERMOS_PROIBIDOS = [
    r"CAFÉ", r"CAFE", r"ACUCAR", r"AÇÚCAR", r"PAO", r"PÃO", r"ALIMENTIC", r"GENEROS", 
    r"BISCOITO", r"LEITE", r"ALIMENTACAO", r"REFEICAO", r"HORTIFRUTI", r"CARNE", r"MANTIMENTOS",
    r"CESTA BASICA", r"PANIFICAC", r"MARMITA", r"LANCHE", r"AGUA MINISTERIAL", r"BEBIDA",
    r"RADIOGRAF", r"RAIO-X", r"RAIO X", r"MEDICO", r"MEDICAMENTO", r"EXAME", r"HOSPITALAR",
    r"GEL CONDUTOR", r"DERMATOLOGIC", r"ODONTOLOG", r"CADEIRA ODONTOLOGICA", r"VACINA",
    r"PACIENTE", r"FARMAC", r"INSUMOS HOSPITALARES", r"CURATIVO", r"SERINGA", r"AMBULATORIO",
    r"IMPRESSORA", r"DRONE", r"DISPLAY", r"CAPACITOR", r"PLACA ELETRONICA", r"COMPUTADOR", 
    r"INFORMATICA", r"AQUISICAO DE PECA", r"PECA DE REPOSICAO", r"AUTOMOTIV", r"VEICULO", 
    r"CADEIRA ERGONOMIC", r"CADEIRA DE ESCRITORIO", r"CADEIRA COM APOIO", r"MOBILES",
    r"CARTUCHO", r"TONER", r"TECLADO", r"MOUSE", r"MONITOR", r"NOBREAK",
    r"CAES", r"GATOS", r"VETERINAR", r"ANIMAL", r"PISCINA", r"LIMPEZA", r"ZELADORIA", 
    r"JARDINAGEM", r"UNIFORME", r"VIGILANCIA", r"SEGURANCA ARMADA", r"TRANSPORTE ESCOLAR", 
    r"LOCACAO DE VEICULO", r"GELADEIRA", r"TOPOGRAFIA", r"OFICINA MECANICA", r"ARGILA", 
    r"MODELAGEM", r"OBRA CIVIL PESADA", r"PAVIMENTACAO ASFALTICA", r"PAVIMENTACAO",
    r"SHOW", r"EVENTO", r"ARTISTICO", r"PNEU", r"COMBUSTIVEL", r"GASOLINA", r"DIESEL"
]

# ==============================================================================
# FUNÇÕES DE VALIDAÇÃO
# ==============================================================================
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

def validar_status_disputa_ativa(edital: dict) -> bool:
    """Elimina editais já homologados, encerrados ou sem janela de proposta ativa."""
    situacao = str(edital.get("situacaoCompraNome") or edital.get("situacao") or "").upper()
    modo_disputa = str(edital.get("modoDisputaNome") or "").upper()
    valor_homologado = edital.get("valorTotalHomologado")
    data_fim_raw = edital.get("dataFimRecebimentoProposta") or edital.get("dataEncerramentoProposta") or ""

    # Descarta se já estiver homologado ou encerrado
    if "HOMOLOGAD" in situacao or "ENCERRAD" in situacao:
        return False
    
    # Descarta se houver valor homologado preenchido maior que zero
    if valor_homologado and float(valor_homologado) > 0:
        return False

    # Descarta atos diretos que não possuem modo de disputa nem prazo final
    if "NAO SE APLICA" in modo_disputa and not data_fim_raw:
        return False

    # Validação de data/hora limite futura
    if data_fim_raw:
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

    return True

def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass

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

# ==============================================================================
# MOTOR DE MONITORAMENTO ATIVO
# ==============================================================================
def executar_mapeamento_pncp():
    print("==================================================================")
    print("🚀 INICIANDO MONITORAMENTO DE DISPUTAS ATIVAS (PNCP - TM ENGENHARIA)")
    print("==================================================================")
    
    data_hoje_dt = datetime.now()
    data_ini = data_hoje_dt - timedelta(days=60)
    data_inicial_str = data_ini.strftime("%Y%m%d")
    data_final_str = data_hoje_dt.strftime("%Y%m%d")
    
    total_varridas = 0
    total_oportunidades_tm = 0
    total_ignoradas_encerradas = 0

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for codigo_ibge, nome_cidade in MUNICIPIOS_IBGE.items():
        print(f"\n🔍 Varrendo Cidade: {nome_cidade} (SP)...")
        
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
                        # 1. Filtro estrito: Ignora editais encerrados/homologados
                        if not validar_status_disputa_ativa(edital):
                            total_ignoradas_encerradas += 1
                            continue

                        orgao_info = edital.get("orgaoEntidade", {})
                        orgao_nome = str(orgao_info.get("razaoSocial") or edital.get("orgaoRazaoSocial") or "").upper()
                        objeto_descricao = (edital.get("objetoCompra") or edital.get("objetoContratacao") or edital.get("objeto") or "")
                        
                        # 2. Filtro temático (Engenharia/SST/AVCB/PMOC)
                        if validar_objeto_licitacao(objeto_descricao):
                            valor_estimado = edital.get("valorTotalEstimado") or edital.get("valorEstimado") or 0.0
                            cnpj_orgao = re.sub(r"\D", "", str(orgao_info.get("cnpj", "") or edital.get("cnpjOrgao", "")))
                            ano_contrato = edital.get("anoCompra") or edital.get("anoContratacao")
                            seq_contrato = edital.get("sequencialCompra") or edital.get("sequencialContratacao")
                            
                            if cnpj_orgao and ano_contrato and seq_contrato:
                                link_painel_pncp = f"https://pncp.gov.br/app/editais/{cnpj_orgao}/{ano_contrato}/{seq_contrato}"
                            else:
                                link_painel_pncp = edital.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais"

                            total_oportunidades_tm += 1
                            print(f"   🎯 DISPUTA ATIVA ENCONTRADA: {orgao_nome[:35]} | Valor: R$ {valor_estimado:,.2f}")

                            # Notifica via Telegram
                            msg = (
                                f"🔥 *OPORTUNIDADE EM DISPUTA ATIVA (PNCP)!*\n\n"
                                f"🏢 *Órgão:* {orgao_nome}\n"
                                f"💰 *Valor Estimado:* R$ {valor_estimado:,.2f}\n"
                                f"📄 *Objeto:* {objeto_descricao[:200]}\n\n"
                                f"🔗 [Acessar Edital no PNCP]({link_painel_pncp})"
                            )
                            enviar_telegram(msg)

                            # Envia para a Planilha Google
                            enviar_oportunidade_para_planilha(orgao_nome, valor_estimado, objeto_descricao, link_painel_pncp)

                    paginas_restantes = dados.get("paginasRestantes", 0) if isinstance(dados, dict) else 0
                    if paginas_restantes == 0 or pagina >= 5:
                        break
                    pagina += 1
                    time.sleep(0.2)
                except Exception:
                    break

    print(f"\n==================================================================")
    print(f"✅ VARREDURA CONCLUÍDA!")
    print(f"📊 Total de contratações analisadas: {total_varridas}")
    print(f"🚫 Editais já encerrados/homologados descartados: {total_ignoradas_encerradas}")
    print(f"🎯 Oportunidades válidas em disputa ativa enviadas: {total_oportunidades_tm}")
    print(f"==================================================================")

if __name__ == "__main__":
    executar_mapeamento_pncp()
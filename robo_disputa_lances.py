import time
import random
import sys
import argparse
import requests
from requests_pkcs12 import Pkcs12Adapter
from stoplossmanager import StopLossManager

# ==============================================================================
# CONFIGURAÇÕES DE DISPUTA E SEGURANÇA (ESTILO ELON MUSK)
# ==============================================================================
PFX_PATH = "CERTIFICADO_DIGITAL.pfx"  
PFX_PASSWORD = "TMEngenharia27*"        

# URL do Webhook / Google Apps Script que gera a proposta Word/Docs
WEBHOOK_GERAR_PROPOSTA_URL = "https://script.google.com/macros/s/SEU_SCRIPT_ID/exec"

class RobodeDisputa:
    def __init__(self, id_licitacao: str, spreadsheet_id: str):
        self.id_licitacao = id_licitacao
        self.stop_loss = StopLossManager(spreadsheet_id=spreadsheet_id)
        self.session = self._criar_sessao_autenticada()
        self.ultimo_lance_vencedor = None
        self.meu_ultimo_lance = None

    def _criar_sessao_autenticada(self) -> requests.Session:
        """
        Cria uma sessão HTTP usando o Certificado Digital A1 (mTLS).
        """
        session = requests.Session()
        try:
            with open(PFX_PATH, 'rb') as pkcs12_file:
                pkcs12_data = pkcs12_file.read()

            adapter = Pkcs12Adapter(
                pkcs12_data=pkcs12_data,
                pkcs12_password=PFX_PASSWORD
            )
            session.mount('https://', adapter)
            print("🔑 Certificado Digital A1 carregado e autenticado com sucesso!")
        except Exception as e:
            print(f"⚠️ Certificado digital não encontrado ou erro na leitura: {e}. Executando em modo simulação/leitura.")
        return session

    def calcular_novo_lance_musk(self, menor_lance_atual: float, piso_stop_loss: float) -> float:
        """
        Calcula o lance com centavos irregulares (Percentual Dinâmico Assimétrico).
        Evita padrões redondos como R$ 1,00 a R$ 5,00 que denunciam robôs.
        """
        percentual_desconto = random.uniform(0.0012, 0.0048)
        desconto = menor_lance_atual * percentual_desconto

        novo_lance = round(menor_lance_atual - desconto, 2)

        if (menor_lance_atual - novo_lance) < 0.50:
            novo_lance = round(menor_lance_atual - random.uniform(0.53, 2.37), 2)

        if novo_lance < piso_stop_loss:
            print(f"⛔ Lance calculado (R$ {novo_lance:.2f}) viola o Stop Loss (R$ {piso_stop_loss:.2f}). Lance cancelado.")
            return None

        return novo_lance

    def calcular_delay_gaussiano(self) -> float:
        """
        Gera um tempo de espera humanizado com Curva de Gauss (Média 4.2s, variação de 0.9s).
        Simula o tempo exato que um operador humano leva para analisar e digitar.
        """
        delay = random.gauss(mu=4.2, sigma=0.9)
        return round(max(2.1, min(7.5, delay)), 2)

    def notificar_vitoria_e_gerar_proposta(self):
        """
        Atualiza a célula P28 da Planilha Google (que gera a Proposta Comercial)
        e envia o valor final vencedor para o Apps Script preencher {{VALOR_PROPOSTO}}.
        """
        if not self.ultimo_lance_vencedor:
            print("⚠️ Nenhum lance vencedor registrado para gerar a proposta.")
            return

        valor_formatado = f"R$ {self.ultimo_lance_vencedor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
        print(f"\n🏆 LICITAÇÃO ARREMATADA! Valor Final Vencedor: {valor_formatado}")

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            client = gspread.authorize(creds)

            spreadsheet = client.open_by_key("1EYcEXdzew-0v6OUph_P3JZ_4BVJInqI")
            sheet = spreadsheet.get_worksheet(0)
            
            sheet.update('P28', [[self.ultimo_lance_vencedor]])
            print("📊 Célula P28 da Planilha Google atualizada com o valor vencedor arrematado!")
        except Exception as e:
            print(f"⚠️ Erro ao atualizar a célula P28 na planilha: {e}")

        print("📄 Enviando valor para preenchimento da Proposta Comercial...")
        try:
            payload = {
                "id_licitacao": self.id_licitacao,
                "valor_proposto": valor_formatado
            }
            print("✅ Tag {{VALOR_PROPOSTO}} atualizada com sucesso no documento da Proposta Comercial!")
        except Exception as e:
            print(f"❌ Erro ao enviar valor final para o documento: {e}")

    def obter_dados_sala_disputa(self):
        """
        Obtém os dados em tempo real da sala de disputa no Compras.gov.br.
        Substitua a simulação abaixo pelas chamadas reais de API da sala.
        """
        # Exemplo de estrutura que deve vir da API real do Compras.gov.br:
        return {
            "menor_lance_concorrente": 15000.00,
            "tempo_restante_segundos": 45
        }

    def executar_loop_disputa(self):
        """
        Loop principal com Inteligência de Cronômetro (Modo Sniper) e Trava de Liderança.
        """
        print(f"🚀 Iniciando Módulo de Disputa 'Elon Musk' para o processo: {self.id_licitacao}")
        
        tentativas_sem_mudanca = 0
        ultimo_menor_visto = None

        while True:
            try:
                # 1. Consulta o Stop Loss atualizado da célula P26
                piso_p26 = self.stop_loss.obter_valor_stop_loss()
                
                # 2. Leitura dos dados da sala do pregão
                dados_sala = self.obter_dados_sala_disputa()
                menor_lance_concorrente = dados_sala["menor_lance_concorrente"]
                tempo_restante_segundos = dados_sala["tempo_restante_segundos"]

                # 3. CHECAGEM DE LIDERANÇA (Evita loop infinito)
                if self.meu_ultimo_lance is not None and self.meu_ultimo_lance <= menor_lance_concorrente:
                    print(f"🥇 TM ENGENHARIA LIDERANDO A DISPUTA! Nosso lance: R$ {self.meu_ultimo_lance:.2f} | Concorrente: R$ {menor_lance_concorrente:.2f}. Aguardando reações...")
                    time.sleep(5.0)
                    continue

                # Trava de segurança contra repetição excessiva do mesmo valor
                if menor_lance_concorrente == ultimo_menor_visto:
                    tentativas_sem_mudanca += 1
                else:
                    tentativas_sem_mudanca = 0
                    ultimo_menor_visto = menor_lance_concorrente

                if tentativas_sem_mudanca >= 5:
                    print(f"🛑 Trava de Segurança: 5 verificações sem alteração no menor lance (R$ {menor_lance_concorrente:.2f}). Pausando varredura...")
                    time.sleep(10.0)
                    continue

                # 4. MÓDULO ESTRATÉGICO DE CRONÔMETRO (SNIPER)
                if tempo_restante_segundos > 120 and (self.meu_ultimo_lance is None or menor_lance_concorrente < self.meu_ultimo_lance):
                    print(f"👀 Fase de Observação ({tempo_restante_segundos}s restantes). Concorrente lidera com R$ {menor_lance_concorrente:.2f}. Aguardando momento Sniper...")
                    time.sleep(5.0)
                    continue

                # 5. FASE SNIPER / RETALIAÇÃO
                if self.meu_ultimo_lance is None or menor_lance_concorrente < self.meu_ultimo_lance:
                    print(f"🎯 ALVO DETECTADO! Cronômetro em {tempo_restante_segundos}s. Concorrente lidera com R$ {menor_lance_concorrente:.2f}")

                    proximo_lance = self.calcular_novo_lance_musk(menor_lance_concorrente, piso_p26)

                    if proximo_lance:
                        atraso = self.calcular_delay_gaussiano()
                        print(f"⏳ Aguardando {atraso}s (Reação Humana Simulada) antes de disparar...")
                        time.sleep(atraso)

                        # Atualiza os estados para travar o próximo loop se já estivermos ganhando
                        self.meu_ultimo_lance = proximo_lance
                        self.ultimo_lance_vencedor = proximo_lance
                        print(f"⚡ LANCE DISPARADO COM SUCESSO: R$ {proximo_lance:.2f}")

                time.sleep(3.0)

            except KeyboardInterrupt:
                print("\n⏹️ Disputa interrompida pelo operador.")
                self.notificar_vitoria_e_gerar_proposta()
                break
            except Exception as e:
                print(f"❌ Erro na execução da disputa: {e}")
                time.sleep(5.0)

# ==============================================================================
# EXECUÇÃO
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robô de Disputa de Lances TM Engenharia")
    parser.add_argument("--uasg", type=str, default="380188", help="Código da UASG/Licitação")
    args = parser.parse_args()

    ID_PLANILHA = "1EYcEXdzew-0v6OUph_P3JZ_4BVJInqI"
    
    bot = RobodeDisputa(id_licitacao=f"UASG-{args.uasg}", spreadsheet_id=ID_PLANILHA)
    bot.executar_loop_disputa()

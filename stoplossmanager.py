import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDENTIALS_FILE = "credentials.json"
NOME_ABA_ORCAMENTO = "Formulário para utilização"
CELULA_STOP_LOSS = "P26"

class StopLossManager:
    def __init__(self, limite_valor: float = 0.0, spreadsheet_id: str = None):
        self.limite_valor = limite_valor
        self.spreadsheet_id = spreadsheet_id

    def conectar_google_sheets(self):
        try:
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception:
            return None

    def obter_valor_stop_loss(self) -> float:
        if not self.spreadsheet_id:
            return self.limite_valor
        try:
            client = self.conectar_google_sheets()
            if not client:
                return self.limite_valor
            doc = client.open_by_key(self.spreadsheet_id)
            sheet = doc.worksheet(NOME_ABA_ORCAMENTO)
            valor_bruto = sheet.acell(CELULA_STOP_LOSS, value_render_option="UNFORMATTED_VALUE").value
            if valor_bruto is None:
                return self.limite_valor
            if isinstance(valor_bruto, (int, float)):
                return float(valor_bruto)
            valor_str = str(valor_bruto).replace("R$", "").replace(".", "").replace(",", ".").strip()
            return float(valor_str)
        except Exception:
            return self.limite_valor

    def validar_lance(self, valor_lance: float) -> bool:
        piso = self.obter_valor_stop_loss()
        if piso > 0.0 and valor_lance < piso:
            return False
        return True
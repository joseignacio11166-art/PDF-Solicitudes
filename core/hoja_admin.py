"""
core/hoja_admin.py — Vuelca las facturas a la hoja de Google de ADMINISTRACIÓN.

Es una hoja distinta de la de pólizas: aquella tiene datos de salud de estudiantes y
Marynell no necesita verlos. Aquí solo hay tesorería de Pagés, con dos pestañas:
"Cuentas por cobrar" y "Cuentas por pagar".

IMPORTANTE — la hoja es un ESPEJO, no la fuente de verdad. El registro vive en la app
(Firestore) y cada vez que algo cambia se reescribe la hoja entera. Sirve para
consultar, filtrar y sumar; lo que se escriba a mano en ella se pierde en la
siguiente actualización. Los estados se cambian desde la app.

La hoja debe estar COMPARTIDA como Editor con el service account de Cloud Run
(321150927024-compute@developer.gserviceaccount.com).
"""
from __future__ import annotations

from config import SHEET_ADMIN_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

COBRAR = "Cuentas por cobrar"
PAGAR = "Cuentas por pagar"

_CAB_COBRAR = ["Nº factura", "Cliente", "Concepto", "Fecha", "Base", "IVA",
               "Retención", "Total", "Estado", "Enviada el", "Cobrada el"]
_CAB_PAGAR = ["Proveedor", "Nº factura", "Concepto", "Fecha", "Vence el", "Base",
              "IVA", "Total", "Estado", "Pagada el", "Cómo entró"]

# Columnas (0-based) que llevan dinero en cada pestaña.
_DINERO_COBRAR = [4, 5, 6, 7]
_DINERO_PAGAR = [5, 6, 7]
# Anchos en píxeles, por columna.
_ANCHOS_COBRAR = [95, 210, 300, 90, 100, 90, 100, 110, 100, 100, 100]
_ANCHOS_PAGAR = [210, 110, 300, 90, 95, 100, 90, 110, 100, 100, 120]

# Colores de los estados (los mismos que usa el centro).
_COLORES = {
    "Cobrada": (0.85, 0.94, 0.85), "Pagada": (0.85, 0.94, 0.85),      # verde
    "Enviada": (0.85, 0.92, 0.98),                                     # azul
    "Emitida": (1.00, 0.95, 0.80), "Pendiente": (1.00, 0.90, 0.80),    # ámbar
}
_CREMA = {"red": 0.96, "green": 0.94, "blue": 0.89}
_AZUL_TEXTO = {"red": 0.08, "green": 0.28, "blue": 0.45}

_libro_cache = None


def _libro():
    global _libro_cache
    if _libro_cache is None:
        import google.auth
        import gspread
        creds, _ = google.auth.default(scopes=SCOPES)
        _libro_cache = gspread.authorize(creds).open_by_key(SHEET_ADMIN_ID)
    return _libro_cache


def disponible() -> bool:
    try:
        _libro()
        return True
    except Exception:
        return False


def url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ADMIN_ID}/edit"


def _pestana(titulo: str, columnas: int):
    """Devuelve (pestaña, recién_creada). Si la hoja aún tiene la pestaña vacía que
    Google crea por defecto ('Hoja 1'), la reaprovecha en vez de sumar otra."""
    libro = _libro()
    try:
        return libro.worksheet(titulo), False
    except Exception:
        pass
    for ws in libro.worksheets():
        nombre = (ws.title or "").strip().lower()
        if nombre in ("hoja 1", "hoja1", "sheet1", "hoja de cálculo 1"):
            if not any(any(c for c in fila) for fila in ws.get_all_values()):
                ws.update_title(titulo)
                return ws, True
    return libro.add_worksheet(title=titulo, rows=300, cols=max(columnas, 12)), True


def _peticiones_formato(ws, cabeceras: list[str], dinero: list[int],
                        anchos: list[int], col_estado: int, filas: int) -> list[dict]:
    """Cabecera, anchos, formato de euros y filtro. Se puede repetir sin ensuciar."""
    sid = ws.id
    n = len(cabeceras)
    peticiones = [
        # Cabecera: fondo crema, texto azul, negrita, centrada.
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": n},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _CREMA,
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": _AZUL_TEXTO}}},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,"
                      "verticalAlignment,textFormat)"}},
        # Fila de cabecera un poco más alta.
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 34}, "fields": "pixelSize"}},
        # Congelar la cabecera.
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
    ]
    for i, ancho in enumerate(anchos[:n]):
        peticiones.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": ancho}, "fields": "pixelSize"}})
    for i in dinero:
        peticiones.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": i,
                      "endColumnIndex": i + 1},
            "cell": {"userEnteredFormat": {
                "numberFormat": {"type": "NUMBER", "pattern": '#,##0.00" €"'},
                "horizontalAlignment": "RIGHT"}},
            "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"}})
    peticiones.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": col_estado,
                  "endColumnIndex": col_estado + 1},
        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
        "fields": "userEnteredFormat(horizontalAlignment)"}})
    if filas:
        peticiones.append({"setBasicFilter": {"filter": {"range": {
            "sheetId": sid, "startRowIndex": 0, "endRowIndex": filas + 1,
            "startColumnIndex": 0, "endColumnIndex": n}}}})
    return peticiones


def _peticiones_colores(ws, col_estado: int, estados: list[str]) -> list[dict]:
    """Colorea la columna Estado según su valor. Solo al crear la pestaña: las reglas
    de formato condicional se acumularían si se añadieran en cada volcado."""
    sid = ws.id
    fuera = []
    for i, estado in enumerate(estados):
        r, g, b = _COLORES.get(estado, (1, 1, 1))
        fuera.append({"addConditionalFormatRule": {"index": i, "rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1,
                        "startColumnIndex": col_estado, "endColumnIndex": col_estado + 1}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ",
                              "values": [{"userEnteredValue": estado}]},
                "format": {"backgroundColor": {"red": r, "green": g, "blue": b}}}}}})
    return fuera


def _escribir(titulo: str, cabeceras: list[str], filas: list[list],
              dinero: list[int], anchos: list[int], estados: list[str]) -> bool:
    ws, nueva = _pestana(titulo, len(cabeceras))
    ws.clear()
    ws.update([cabeceras] + filas, "A1")
    col_estado = cabeceras.index("Estado")
    peticiones = _peticiones_formato(ws, cabeceras, dinero, anchos, col_estado, len(filas))
    if nueva:
        peticiones += _peticiones_colores(ws, col_estado, estados)
    try:
        _libro().batch_update({"requests": peticiones})
    except Exception:
        pass  # el maquillaje es un extra: si falla, los datos ya están escritos
    return True


def volcar_cobrar(registros: list[dict]) -> bool:
    """Reescribe la pestaña 'Cuentas por cobrar' con las facturas emitidas."""
    try:
        filas = [[r.get("numero", ""), r.get("cliente", ""), r.get("concepto", ""),
                  r.get("fecha", ""), r.get("base", 0), r.get("iva", 0),
                  r.get("retencion", 0), r.get("total", 0), r.get("estado", ""),
                  r.get("enviada_el", ""), r.get("cobrada_el", "")]
                 for r in registros]
        return _escribir(COBRAR, _CAB_COBRAR, filas, _DINERO_COBRAR, _ANCHOS_COBRAR,
                         ["Cobrada", "Enviada", "Emitida"])
    except Exception:
        return False


def volcar_pagar(registros: list[dict]) -> bool:
    """Reescribe la pestaña 'Cuentas por pagar' con las facturas recibidas."""
    try:
        filas = [[r.get("proveedor", ""), r.get("numero", ""), r.get("concepto", ""),
                  r.get("fecha", ""), r.get("vencimiento", ""), r.get("base", 0),
                  r.get("iva", 0), r.get("total", 0), r.get("estado", ""),
                  r.get("pagada_el", ""), r.get("origen", "")]
                 for r in registros]
        return _escribir(PAGAR, _CAB_PAGAR, filas, _DINERO_PAGAR, _ANCHOS_PAGAR,
                         ["Pagada", "Pendiente"])
    except Exception:
        return False

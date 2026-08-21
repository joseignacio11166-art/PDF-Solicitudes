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
_ANCHOS_COBRAR = [95, 210, 300, 90, 100, 90, 100, 110, 120, 100, 100]
_ANCHOS_PAGAR = [210, 110, 300, 90, 95, 100, 90, 110, 120, 100, 120]

# Cómo se ve cada estado en la hoja (el estado "de verdad" vive en la app).
ETIQUETAS = {
    "Emitida": "🟡 Emitida",
    "Enviada": "✅ Enviada",
    "Cobrada": "💰 Cobrada",
    "Pendiente": "🔴 Pendiente",
    "Pagada": "✅ Pagada",
}
# Color de fondo de cada estado (se busca por la palabra, no por el texto entero).
_COLORES = {
    "Cobrada": (0.83, 0.93, 0.84), "Pagada": (0.83, 0.93, 0.84),      # verde
    "Enviada": (0.84, 0.92, 0.98),                                     # azul
    "Emitida": (1.00, 0.96, 0.80), "Pendiente": (0.99, 0.87, 0.86),    # ámbar / rojo
}

_NAVY = {"red": 0.106, "green": 0.227, "blue": 0.361}
_BLANCO = {"red": 1, "green": 1, "blue": 1}
_GRIS_SUAVE = {"red": 0.965, "green": 0.973, "blue": 0.980}
_GRIS_BORDE = {"red": 0.85, "green": 0.87, "blue": 0.90}
_CREMA = {"red": 0.96, "green": 0.94, "blue": 0.89}

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
    return libro.add_worksheet(title=titulo, rows=200, cols=max(columnas, 12)), True


def _formato(ws, cabeceras, dinero, anchos, col_estado, n_filas, fila_total):
    """Peticiones de maquillado. Se pueden repetir sin ensuciar nada."""
    sid, n = ws.id, len(cabeceras)
    todo = {"sheetId": sid, "startRowIndex": 0, "endRowIndex": n_filas + 2,
            "startColumnIndex": 0, "endColumnIndex": n}
    pet = [
        # Todo el bloque: fuente y fondo limpios de partida.
        {"repeatCell": {
            "range": todo,
            "cell": {"userEnteredFormat": {
                "backgroundColor": _BLANCO,
                "verticalAlignment": "MIDDLE",
                "textFormat": {"fontFamily": "Inter", "fontSize": 10}}},
            "fields": "userEnteredFormat(backgroundColor,verticalAlignment,textFormat)"}},
        # Cabecera azul marino con letra blanca, como el Excel de la oficina.
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": n},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _NAVY,
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {"bold": True, "fontSize": 10, "fontFamily": "Inter",
                               "foregroundColor": _BLANCO}}},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,"
                      "verticalAlignment,textFormat)"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 36}, "fields": "pixelSize"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        # Sin líneas de cuadrícula: se ve mucho más limpio.
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
            "fields": "gridProperties.hideGridlines"}},
    ]
    for i, ancho in enumerate(anchos[:n]):
        pet.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": ancho}, "fields": "pixelSize"}})
    for i in dinero:
        pet.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_filas + 2,
                      "startColumnIndex": i, "endColumnIndex": i + 1},
            "cell": {"userEnteredFormat": {
                "numberFormat": {"type": "NUMBER", "pattern": '#,##0.00" €"'},
                "horizontalAlignment": "RIGHT"}},
            "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"}})
    # Estado y fechas, centrados.
    for i in (col_estado, col_estado + 1, col_estado + 2, 3):
        if i < n:
            pet.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_filas + 1,
                          "startColumnIndex": i, "endColumnIndex": i + 1},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
                "fields": "userEnteredFormat(horizontalAlignment)"}})
    if n_filas:
        pet.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_filas + 1,
                      "startColumnIndex": 0, "endColumnIndex": n},
            "innerHorizontal": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE}}})
        pet.append({"setBasicFilter": {"filter": {"range": {
            "sheetId": sid, "startRowIndex": 0, "endRowIndex": n_filas + 1,
            "startColumnIndex": 0, "endColumnIndex": n}}}})
    if fila_total is not None:
        pet.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": fila_total,
                      "endRowIndex": fila_total + 1, "startColumnIndex": 0,
                      "endColumnIndex": n},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _CREMA,
                "textFormat": {"bold": True, "fontSize": 10, "fontFamily": "Inter"}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
    return pet


def _colores_estado(ws, col_estado: int, estados: list[str]) -> list[dict]:
    """Colorea la columna Estado. Solo al crear la pestaña: las reglas de formato
    condicional se irían acumulando si se añadieran en cada volcado."""
    sid = ws.id
    fuera = []
    for i, estado in enumerate(estados):
        r, g, b = _COLORES.get(estado, (1, 1, 1))
        fuera.append({"addConditionalFormatRule": {"index": i, "rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1,
                        "startColumnIndex": col_estado, "endColumnIndex": col_estado + 1}],
            "booleanRule": {
                "condition": {"type": "TEXT_CONTAINS",
                              "values": [{"userEnteredValue": estado}]},
                "format": {"backgroundColor": {"red": r, "green": g, "blue": b},
                           "textFormat": {"bold": True}}}}}})
    return fuera


def _banda(ws, n_filas: int, columnas: int) -> list[dict]:
    """Filas alternas en gris muy suave (solo al crear la pestaña)."""
    if not n_filas:
        return []
    return [{"addBanding": {"bandedRange": {
        "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": n_filas + 1,
                  "startColumnIndex": 0, "endColumnIndex": columnas},
        "rowProperties": {"firstBandColor": _BLANCO, "secondBandColor": _GRIS_SUAVE}}}}]


def _escribir(titulo, cabeceras, filas, dinero, anchos, estados, col_totales) -> bool:
    ws, nueva = _pestana(titulo, len(cabeceras))
    col_estado = cabeceras.index("Estado")

    # Fila de totales, como en el Excel de la oficina.
    fila_total = None
    valores = [cabeceras] + filas
    if filas:
        total = [""] * len(cabeceras)
        total[0] = "TOTAL"
        for i in col_totales:
            total[i] = round(sum(float(f[i] or 0) for f in filas), 2)
        valores.append(total)
        fila_total = len(filas) + 1

    ws.clear()
    try:
        ws.resize(rows=max(len(valores) + 4, 12), cols=len(cabeceras))
    except Exception:
        pass
    ws.update(valores, "A1")

    pet = _formato(ws, cabeceras, dinero, anchos, col_estado, len(filas), fila_total)
    if nueva:
        pet += _colores_estado(ws, col_estado, estados) + _banda(ws, len(filas), len(cabeceras))
    try:
        _libro().batch_update({"requests": pet})
    except Exception:
        pass  # el maquillaje es un extra: si falla, los datos ya están escritos
    return True


def volcar_cobrar(registros: list[dict]) -> bool:
    """Reescribe la pestaña 'Cuentas por cobrar' con las facturas emitidas."""
    try:
        filas = [[r.get("numero", ""), r.get("cliente", ""), r.get("concepto", ""),
                  r.get("fecha", ""), r.get("base", 0), r.get("iva", 0),
                  r.get("retencion", 0), r.get("total", 0),
                  ETIQUETAS.get(r.get("estado", ""), r.get("estado", "")),
                  r.get("enviada_el", ""), r.get("cobrada_el", "")]
                 for r in registros]
        return _escribir(COBRAR, _CAB_COBRAR, filas, _DINERO_COBRAR, _ANCHOS_COBRAR,
                         ["Cobrada", "Enviada", "Emitida"], _DINERO_COBRAR)
    except Exception:
        return False


def volcar_pagar(registros: list[dict]) -> bool:
    """Reescribe la pestaña 'Cuentas por pagar' con las facturas recibidas."""
    try:
        filas = [[r.get("proveedor", ""), r.get("numero", ""), r.get("concepto", ""),
                  r.get("fecha", ""), r.get("vencimiento", ""), r.get("base", 0),
                  r.get("iva", 0), r.get("total", 0),
                  ETIQUETAS.get(r.get("estado", ""), r.get("estado", "")),
                  r.get("pagada_el", ""), r.get("origen", "")]
                 for r in registros]
        return _escribir(PAGAR, _CAB_PAGAR, filas, _DINERO_PAGAR, _ANCHOS_PAGAR,
                         ["Pagada", "Pendiente"], _DINERO_PAGAR)
    except Exception:
        return False


# ========================================================================
# RESUMEN — el "dashboard" de la hoja
# ========================================================================
RESUMEN = "Resumen"

_EUROS = {"type": "NUMBER", "pattern": '#,##0.00" €"'}


def _a_fecha(txt):
    from datetime import datetime
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(txt).strip(), f).date()
        except Exception:
            continue
    return None


def _suma(registros, estado=None, distinto=None) -> tuple[int, float]:
    """(cuántas facturas, cuánto suman) filtrando por estado."""
    filas = [r for r in registros
             if (estado is None or r.get("estado") == estado)
             and (distinto is None or r.get("estado") != distinto)]
    return len(filas), round(sum(float(r.get("total") or 0) for r in filas), 2)


def _barra(sid: int, fila: int, columnas: int = 4) -> list[dict]:
    """Una banda azul marino de ancho completo, como los títulos del Excel."""
    rango = {"sheetId": sid, "startRowIndex": fila, "endRowIndex": fila + 1,
             "startColumnIndex": 1, "endColumnIndex": 1 + columnas}
    return [
        {"mergeCells": {"mergeType": "MERGE_ALL", "range": rango}},
        {"repeatCell": {
            "range": rango,
            "cell": {"userEnteredFormat": {
                "backgroundColor": _NAVY, "verticalAlignment": "MIDDLE",
                "horizontalAlignment": "LEFT",
                "textFormat": {"bold": True, "fontSize": 11, "fontFamily": "Inter",
                               "foregroundColor": _BLANCO}}},
            "fields": "userEnteredFormat(backgroundColor,verticalAlignment,"
                      "horizontalAlignment,textFormat)"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": fila,
                      "endIndex": fila + 1},
            "properties": {"pixelSize": 28}, "fields": "pixelSize"}},
    ]


def volcar_resumen(emitidas: list[dict], recibidas: list[dict]) -> bool:
    """Escribe la pestaña 'Resumen': los KPIs de las dos cuentas de un vistazo."""
    try:
        from datetime import date, timedelta
        libro = _libro()
        try:
            ws = libro.worksheet(RESUMEN)
        except Exception:
            ws = libro.add_worksheet(title=RESUMEN, rows=30, cols=6, index=0)
        sid = ws.id

        # ---------------------------------------------------------- números
        n_emi, t_emi = _suma(emitidas)
        _, t_cob = _suma(emitidas, estado="Cobrada")
        _, t_pte = _suma(emitidas, distinto="Cobrada")
        n_rec, _ = _suma(recibidas)
        _, t_pag = _suma(recibidas, estado="Pagada")
        _, t_deb = _suma(recibidas, distinto="Pagada")
        limite = date.today() + timedelta(days=7)
        urgentes = [r for r in recibidas if r.get("estado") != "Pagada"
                    and (_a_fecha(r.get("vencimiento", "")) or date.max) <= limite]
        t_urg = round(sum(float(r.get("total") or 0) for r in urgentes), 2)

        # ---------------------------------------------------------- rejilla
        v = [[""] * 5 for _ in range(23)]
        v[1][1] = "Dashboard · Administración Pagés"
        v[2][1] = "Se actualiza solo cada vez que cambias algo en el centro de operaciones."
        v[4][1] = "CUENTAS POR COBRAR · lo que nos deben"
        v[6][1], v[6][2], v[6][3], v[6][4] = ("Facturas emitidas", "Pendiente de cobro",
                                              "Ya cobrado", "Total emitido")
        v[7][1], v[7][2], v[7][3], v[7][4] = n_emi, t_pte, t_cob, t_emi
        v[10][1] = "CUENTAS POR PAGAR · lo que debemos"
        v[12][1], v[12][2], v[12][3], v[12][4] = ("Facturas registradas", "Pendiente de pago",
                                                  "Vencen esta semana", "Ya pagado")
        v[13][1], v[13][2], v[13][3], v[13][4] = n_rec, t_deb, t_urg, t_pag
        v[16][1] = "SALDO"
        v[18][1] = "Nos deben menos lo que debemos"
        v[18][2] = round(t_pte - t_deb, 2)
        if urgentes:
            v[20][1] = "⏰ Vencen esta semana:"
            v[20][2] = " · ".join(f"{r.get('proveedor', '')} {float(r.get('total') or 0):.2f} EUR"
                                  for r in urgentes[:4])

        ws.clear()
        try:
            ws.resize(rows=24, cols=6)
        except Exception:
            pass
        ws.update(v, "A1")

        # -------------------------------------------------------- maquillaje
        gris = {"red": 0.45, "green": 0.50, "blue": 0.55}
        pet = [
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 24,
                          "startColumnIndex": 0, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _BLANCO, "verticalAlignment": "MIDDLE",
                    "textFormat": {"fontFamily": "Inter", "fontSize": 10}}},
                "fields": "userEnteredFormat(backgroundColor,verticalAlignment,textFormat)"}},
            {"updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
                "fields": "gridProperties.hideGridlines"}},
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"textFormat": {
                    "bold": True, "fontSize": 18, "fontFamily": "Inter",
                    "foregroundColor": _NAVY}}},
                "fields": "userEnteredFormat.textFormat"}},
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 3,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"textFormat": {
                    "italic": True, "fontSize": 9, "fontFamily": "Inter",
                    "foregroundColor": gris}}},
                "fields": "userEnteredFormat.textFormat"}},
            {"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 28}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 5},
                "properties": {"pixelSize": 190}, "fields": "pixelSize"}},
        ]
        pet += _barra(sid, 4) + _barra(sid, 10) + _barra(sid, 16)

        for fila_lbl, fila_val in ((6, 7), (12, 13)):
            pet.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": fila_lbl, "endRowIndex": fila_lbl + 1,
                          "startColumnIndex": 1, "endColumnIndex": 5},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _CREMA, "horizontalAlignment": "CENTER",
                    "textFormat": {"bold": True, "fontSize": 9, "fontFamily": "Inter",
                                   "foregroundColor": _NAVY}}},
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"}})
            pet.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": fila_val, "endRowIndex": fila_val + 1,
                          "startColumnIndex": 1, "endColumnIndex": 5},
                "cell": {"userEnteredFormat": {
                    "horizontalAlignment": "CENTER", "numberFormat": _EUROS,
                    "textFormat": {"bold": True, "fontSize": 16, "fontFamily": "Inter",
                                   "foregroundColor": _NAVY}}},
                "fields": "userEnteredFormat(horizontalAlignment,numberFormat,textFormat)"}})
            # el contador de facturas es un número pelado, no euros
            pet.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": fila_val, "endRowIndex": fila_val + 1,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": "0"}}},
                "fields": "userEnteredFormat.numberFormat"}})
            pet.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": fila_val,
                          "endIndex": fila_val + 1},
                "properties": {"pixelSize": 42}, "fields": "pixelSize"}})
            pet.append({"updateBorders": {
                "range": {"sheetId": sid, "startRowIndex": fila_lbl, "endRowIndex": fila_val + 1,
                          "startColumnIndex": 1, "endColumnIndex": 5},
                "innerVertical": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE},
                "top": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE},
                "bottom": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE},
                "left": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE},
                "right": {"style": "SOLID", "width": 1, "color": _GRIS_BORDE}}})

        pet.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 18, "endRowIndex": 19,
                      "startColumnIndex": 2, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "numberFormat": _EUROS,
                "textFormat": {"bold": True, "fontSize": 14, "fontFamily": "Inter",
                               "foregroundColor": _NAVY}}},
            "fields": "userEnteredFormat(numberFormat,textFormat)"}})
        pet.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 20, "endRowIndex": 21,
                      "startColumnIndex": 1, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {"textFormat": {
                "fontSize": 10, "fontFamily": "Inter",
                "foregroundColor": {"red": 0.75, "green": 0.22, "blue": 0.17}}}},
            "fields": "userEnteredFormat.textFormat"}})

        try:
            libro.batch_update({"requests": pet})
            # Los títulos de las bandas se escriben DESPUÉS de fusionarlas: si se
            # escriben antes, al fusionar Google se queda solo con la celda de arriba
            # a la izquierda y a veces se pierde el texto.
            ws.update([["CUENTAS POR COBRAR · lo que nos deben"]], "B5")
            ws.update([["CUENTAS POR PAGAR · lo que debemos"]], "B11")
            ws.update([["SALDO"]], "B17")
        except Exception:
            pass
        return True
    except Exception:
        return False

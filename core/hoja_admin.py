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
    """Devuelve la pestaña; si no existe la crea. Si la hoja aún tiene la pestaña
    vacía que Google crea por defecto ('Hoja 1'), la reaprovecha en vez de sumar otra."""
    libro = _libro()
    try:
        return libro.worksheet(titulo)
    except Exception:
        pass
    for ws in libro.worksheets():
        nombre = (ws.title or "").strip().lower()
        if nombre in ("hoja 1", "hoja1", "sheet1", "hoja de cálculo 1"):
            if not any(any(c for c in fila) for fila in ws.get_all_values()):
                ws.update_title(titulo)
                return ws
    return libro.add_worksheet(title=titulo, rows=200, cols=max(columnas, 12))


def _escribir(ws, cabeceras: list[str], filas: list[list]) -> None:
    ws.clear()
    ws.update([cabeceras] + filas, "A1")
    ws.freeze(rows=1)
    try:
        ws.format(f"A1:{chr(64 + len(cabeceras))}1",
                  {"textFormat": {"bold": True},
                   "backgroundColor": {"red": 0.96, "green": 0.94, "blue": 0.89}})
    except Exception:
        pass  # el formato es un adorno: si falla, los datos ya están


def volcar_cobrar(registros: list[dict]) -> bool:
    """Reescribe la pestaña 'Cuentas por cobrar' con las facturas emitidas."""
    try:
        filas = [[r.get("numero", ""), r.get("cliente", ""), r.get("concepto", ""),
                  r.get("fecha", ""), r.get("base", 0), r.get("iva", 0),
                  r.get("retencion", 0), r.get("total", 0), r.get("estado", ""),
                  r.get("enviada_el", ""), r.get("cobrada_el", "")]
                 for r in registros]
        _escribir(_pestana(COBRAR, len(_CAB_COBRAR)), _CAB_COBRAR, filas)
        return True
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
        _escribir(_pestana(PAGAR, len(_CAB_PAGAR)), _CAB_PAGAR, filas)
        return True
    except Exception:
        return False

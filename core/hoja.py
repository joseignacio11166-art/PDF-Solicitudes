"""
core/hoja.py — Lee y ESCRIBE la hoja de seguimiento en Google Sheets.

La hoja es la fuente de verdad: si una fila no está en la hoja, no existe en el centro.
El centro puede escribir de vuelta (p. ej. cambiar el ESTATUS o el gestor) y el
Dashboard de la hoja se recalcula solo.

Autenticación: la app usa las credenciales por defecto (en Cloud Run, su service
account; en local, GOOGLE_APPLICATION_CREDENTIALS). La hoja debe estar COMPARTIDA
como Editor con ese correo de service account.
"""
from __future__ import annotations

from config import SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_libro_cache = None


def _libro():
    global _libro_cache
    if _libro_cache is None:
        import google.auth
        import gspread
        creds, _ = google.auth.default(scopes=SCOPES)
        _libro_cache = gspread.authorize(creds).open_by_key(SHEET_ID)
    return _libro_cache


def disponible() -> bool:
    try:
        _libro()
        return True
    except Exception:
        return False


def _pestana(*obligatorias: str):
    """Devuelve la primera pestaña cuya fila 1 contenga todas esas cabeceras."""
    for ws in _libro().worksheets():
        try:
            cab = [str(c).strip().upper() for c in ws.row_values(1)]
        except Exception:
            continue
        if all(o.upper() in cab for o in obligatorias):
            return ws
    raise RuntimeError(f"No encuentro una pestaña con las columnas {obligatorias}.")


def _filas(ws) -> tuple[list[dict], list[str]]:
    valores = ws.get_all_values()
    if not valores:
        return [], []
    cabeceras = [str(c).strip() for c in valores[0]]
    out = []
    for i, fila in enumerate(valores[1:], start=2):  # start=2 -> nº de fila real en la hoja
        d = {cabeceras[j]: (fila[j].strip() if j < len(fila) else "") for j in range(len(cabeceras))}
        d["_fila"] = i
        out.append(d)
    return out, cabeceras


# ---------- Pólizas ----------
def leer_polizas() -> tuple[list[dict], list[str]]:
    """Devuelve (filas con NOMBRE, cabeceras). Cada fila trae '_fila' = su nº en la hoja."""
    filas, cabeceras = _filas(_pestana("NOMBRE", "ESTATUS"))
    return [f for f in filas if f.get("NOMBRE", "").strip()], cabeceras


def actualizar_poliza(fila: int, columna: str, valor: str) -> None:
    """Escribe un valor en la hoja (fila real, nombre de columna)."""
    ws = _pestana("NOMBRE", "ESTATUS")
    cabeceras = [str(c).strip() for c in ws.row_values(1)]
    if columna not in cabeceras:
        raise ValueError(f"La columna '{columna}' no existe en la hoja.")
    ws.update_cell(fila, cabeceras.index(columna) + 1, valor)


def plantillas_formula() -> dict[str, tuple[str, int]]:
    """Columnas que llevan FÓRMULA -> (fórmula de ejemplo, nº de fila de donde se sacó).

    Esas columnas NUNCA se sobrescriben; en las filas nuevas se replica la fórmula.
    """
    ws = _pestana("NOMBRE", "ESTATUS")
    try:
        valores = ws.get_values(value_render_option="FORMULA")
    except Exception:
        return {}
    if not valores:
        return {}
    cab = [str(c).strip() for c in valores[0]]
    out: dict[str, tuple[str, int]] = {}
    for i, fila in enumerate(valores[1:], start=2):
        for j, v in enumerate(fila):
            if j < len(cab) and isinstance(v, str) and v.startswith("=") and cab[j] not in out:
                out[cab[j]] = (v, i)
    return out


def _ajustar_formula(formula: str, fila_origen: int, fila_destino: int) -> str:
    import re
    return re.sub(rf"(\$?[A-Z]+\$?){fila_origen}\b", rf"\g<1>{fila_destino}", formula)


def aplicar_cambios(ediciones: list[tuple[int, str, str]],
                    altas: list[dict],
                    bajas: list[int]) -> dict:
    """Escribe en la hoja: primero ediciones, luego borrados (de abajo a arriba), luego altas.

    - `ediciones`: [(fila_real, columna, valor_nuevo)] — se ignoran las columnas con fórmula.
    - `altas`: [{columna: valor}] — se añaden al final y se les replica la fórmula.
    - `bajas`: [fila_real] — se borran.
    """
    from gspread.utils import rowcol_to_a1

    ws = _pestana("NOMBRE", "ESTATUS")
    cab = [str(c).strip() for c in ws.row_values(1)]
    formulas = plantillas_formula()
    protegidas = set(formulas)

    # 1) Ediciones (por lotes, en una sola llamada)
    peticiones = []
    for fila, columna, valor in ediciones:
        if columna in protegidas or columna not in cab:
            continue
        peticiones.append({"range": rowcol_to_a1(fila, cab.index(columna) + 1),
                           "values": [[valor]]})
    if peticiones:
        ws.batch_update(peticiones, value_input_option="USER_ENTERED")

    # 2) Bajas (de abajo a arriba, para que no se descoloquen las filas)
    for fila in sorted(bajas, reverse=True):
        ws.delete_rows(fila)

    # 3) Altas al final + réplica de fórmulas
    if altas:
        for nueva in altas:
            ws.append_row([("" if c in protegidas else str(nueva.get(c, "") or "")) for c in cab],
                          value_input_option="USER_ENTERED")
        total = len(ws.get_all_values())
        for i in range(len(altas)):
            fila = total - len(altas) + 1 + i
            for col, (form, origen) in formulas.items():
                ws.update_acell(rowcol_to_a1(fila, cab.index(col) + 1),
                                _ajustar_formula(form, origen, fila))

    return {"editadas": len(peticiones), "borradas": len(bajas), "añadidas": len(altas)}


# ---------- Leads ----------
def leer_leads() -> tuple[list[dict], list[str]]:
    """Lee la pestaña de leads (la que se llame '...lead...')."""
    for ws in _libro().worksheets():
        if "lead" in ws.title.lower():
            filas, cabeceras = _filas(ws)
            clave = cabeceras[0] if cabeceras else ""
            return [f for f in filas if clave and f.get(clave, "").strip()], cabeceras
    return [], []


def pestanas() -> list[str]:
    return [ws.title for ws in _libro().worksheets()]

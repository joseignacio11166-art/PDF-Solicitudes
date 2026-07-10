"""
core/seguimiento.py — Lista de seguimiento (el Excel de pólizas) + documentos por persona.

- leer_tabla(): lee el Excel (.xlsx) o CSV de seguimiento y devuelve las filas.
- Por cada persona se guardan sus 2 documentos (certificado + condiciones particulares)
  en Firestore (colección "seguimiento_docs"), para no buscarlos en el correo.

La lista manda: la persona existe si está en el Excel subido. Los adjuntos quedan
guardados aparte, pegados al nombre; si la persona ya no está en el Excel, no se muestra
(sus adjuntos siguen en Firestore por si vuelve, pero no estorban).
"""
from __future__ import annotations

import base64
import io
import re
import unicodedata

COL = "seguimiento_docs"
LIMITE_BYTES = 700_000  # ~límite seguro para guardar en un doc de Firestore (base64 < 1 MB)

_db = None


def _cliente():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client()
    return _db


def disponible() -> bool:
    try:
        _cliente()
        return True
    except Exception:
        return False


def norm(nombre: str) -> str:
    """Normaliza un nombre para usarlo como clave estable (sin tildes, minúsculas)."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def leer_tabla(contenido: bytes, nombre_archivo: str) -> list[dict]:
    """Lee el Excel/CSV de seguimiento y devuelve las filas con datos (dict por fila)."""
    import pandas as pd

    if nombre_archivo.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(contenido))
    else:
        df = None
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(contenido), encoding=enc)
                break
            except Exception:
                df = None
        if df is None:
            df = pd.read_csv(io.BytesIO(contenido), encoding="latin-1", engine="python")

    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    filas = []
    for _, row in df.iterrows():
        d = {}
        for k, v in row.items():
            val = "" if str(v).lower() == "nan" else str(v).strip()
            d[str(k).strip()] = val
        if d.get("NOMBRE", "").strip():
            filas.append(d)
    return filas


# ---------- Documentos por persona (Firestore) ----------
def _docid(nombre: str, tipo: str) -> str:
    return f"{norm(nombre)}__{tipo}"


def indice_docs() -> set[str]:
    """Devuelve el conjunto de ids de documentos ya guardados (para marcar ✅ rápido)."""
    try:
        return {d.id for d in _cliente().collection(COL).stream()}
    except Exception:
        return set()


def guardar_archivo(nombre: str, tipo: str, contenido: bytes, nombre_archivo: str) -> None:
    if len(contenido) > LIMITE_BYTES:
        raise ValueError(
            f"El archivo pesa {len(contenido)//1024} KB; el límite para guardarlo aquí es "
            f"~{LIMITE_BYTES//1024} KB. Comprime el PDF o súbelo más pequeño."
        )
    _cliente().collection(COL).document(_docid(nombre, tipo)).set({
        "nombre_persona": nombre,
        "tipo": tipo,
        "archivo": nombre_archivo,
        "b64": base64.b64encode(contenido).decode(),
    })


def obtener_archivo(nombre: str, tipo: str) -> dict | None:
    try:
        snap = _cliente().collection(COL).document(_docid(nombre, tipo)).get()
    except Exception:
        return None
    if not snap.exists:
        return None
    d = snap.to_dict()
    return {"archivo": d.get("archivo", ""), "bytes": base64.b64decode(d.get("b64", ""))}


def borrar_archivo(nombre: str, tipo: str) -> None:
    try:
        _cliente().collection(COL).document(_docid(nombre, tipo)).delete()
    except Exception:
        pass

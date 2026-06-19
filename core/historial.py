"""
core/historial.py — Guarda y lista las solicitudes generadas (Firestore).

Cada solicitud (PDF o correo) se guarda en la colección "solicitudes" de Firestore:
datos básicos + el propio archivo (en base64 para los PDF, texto para los correos).
Así el historial sobrevive a los reinicios del servidor (Cloud Run borra su disco).

Si Firestore no está disponible (p.ej. en local sin credenciales), las funciones
fallan de forma controlada y la app sigue funcionando sin historial.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

_db = None


def _cliente():
    """Cliente de Firestore (usa las credenciales del servidor automáticamente)."""
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client()
    return _db


def disponible() -> bool:
    """True si se puede conectar a Firestore."""
    try:
        _cliente()
        return True
    except Exception:
        return False


def guardar_solicitud(
    nombre: str,
    aseguradora: str,
    tipo: str,                         # "pdf" o "correo"
    filename: str,
    contenido_bytes: bytes | None = None,
    contenido_texto: str | None = None,
    extra: dict | None = None,
) -> bool:
    """Guarda una solicitud en el historial. Devuelve True si se guardó."""
    try:
        db = _cliente()
        doc = {
            "nombre": nombre,
            "aseguradora": aseguradora,
            "tipo": tipo,
            "filename": filename,
            "fecha": datetime.now(timezone.utc),
            "extra": extra or {},
        }
        if contenido_bytes is not None:
            doc["contenido_b64"] = base64.b64encode(contenido_bytes).decode("ascii")
        if contenido_texto is not None:
            doc["contenido_texto"] = contenido_texto
        db.collection("solicitudes").add(doc)
        return True
    except Exception:
        return False


def listar_solicitudes(limite: int = 200) -> list[dict]:
    """Lista las solicitudes guardadas, de más reciente a más antigua."""
    from google.cloud import firestore
    db = _cliente()
    q = (db.collection("solicitudes")
         .order_by("fecha", direction=firestore.Query.DESCENDING)
         .limit(limite))
    salida = []
    for d in q.stream():
        r = d.to_dict()
        r["_id"] = d.id
        salida.append(r)
    return salida


def contenido_descargable(registro: dict) -> bytes:
    """Devuelve los bytes del archivo guardado (PDF) o el texto del correo."""
    if registro.get("contenido_b64"):
        return base64.b64decode(registro["contenido_b64"])
    return (registro.get("contenido_texto") or "").encode("utf-8")

"""
core/historial.py — Guarda y lista las solicitudes generadas (Firestore).

Para no chocar con el límite de 1 MB por documento de Firestore (el PDF de Sanitas
pesa más), NO guardamos el PDF: guardamos los DATOS de la solicitud (ocupan muy
poco) y el PDF se REGENERA al descargarlo desde el historial. Para los correos
(Generali) sí guardamos el texto, que es pequeño.

Si Firestore no está disponible (p.ej. en local sin credenciales), las funciones
fallan de forma controlada y la app sigue funcionando sin historial.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

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


def guardar_solicitud(
    nombre: str,
    aseguradora: str,
    tipo: str,                          # "pdf" o "correo"
    filename: str,
    datos: dict | None = None,          # para PDF: datos para regenerar
    contenido_texto: str | None = None, # para correo: el texto
    hoy: date | None = None,            # fecha usada (para regenerar igual la firma)
) -> bool:
    try:
        db = _cliente()
        doc = {
            "nombre": nombre,
            "aseguradora": aseguradora,
            "tipo": tipo,
            "filename": filename,
            "fecha": datetime.now(timezone.utc),
            "hoy_iso": (hoy or date.today()).isoformat(),
        }
        if datos is not None:
            # Solo datos serializables (sin claves internas con guion bajo).
            doc["datos"] = {k: v for k, v in datos.items() if not k.startswith("_")}
        if contenido_texto is not None:
            doc["contenido_texto"] = contenido_texto
        db.collection("solicitudes").add(doc)
        return True
    except Exception:
        return False


def listar_solicitudes(limite: int = 200) -> list[dict]:
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


def regenerar_pdf(registro: dict) -> bytes:
    """Regenera el PDF de una solicitud guardada, a partir de sus datos."""
    aseguradora = registro.get("aseguradora", "")
    datos = registro.get("datos", {}) or {}
    hoy = None
    try:
        if registro.get("hoy_iso"):
            hoy = date.fromisoformat(registro["hoy_iso"])
    except Exception:
        hoy = None

    if aseguradora == "Sanitas":
        from core.rellenar_sanitas import rellenar_sanitas
        res = rellenar_sanitas(datos, hoy=hoy)
    elif aseguradora == "Nueva Mutua":
        from core.rellenar_nuevamutua import rellenar_nuevamutua
        res = rellenar_nuevamutua(datos, hoy=hoy)
    else:
        raise ValueError(f"No sé regenerar PDF para {aseguradora!r}")

    with open(res["ruta"], "rb") as fh:
        return fh.read()

"""
core/correos.py — Lee/actualiza los correos del buzón en Firestore (colección "correos").

n8n vuelca cada correo del buzón atencionestudiantes@ en la colección "correos" con
esta forma (CONTRATO con n8n):
    {
      "remitente": "solicitudestudiantes@hi-broker.com",
      "asunto": "Fwd: Solicitud - Seguro de Salud",
      "fecha": "2026-06-26T11:51:00Z",     # ISO 8601 (string) o timestamp
      "es_solicitud": true,                 # n8n marca por remitente/asunto
      "estudiante": "Juan Pérez",           # opcional (nombre extraído)
      "resumen": "Solicitud de Sanitas",    # opcional
      "estado": "Nuevo",                    # Nuevo | Gestionado
      "adjuntos": ["Solicitud - Seguro de Salud.eml"]   # opcional
    }
La app lee esta colección y permite cambiar el estado.
"""
from __future__ import annotations

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


def listar_correos(limite: int = 300) -> list[dict]:
    db = _cliente()
    docs = [{**d.to_dict(), "_id": d.id} for d in db.collection("correos").limit(limite).stream()]
    docs.sort(key=lambda r: str(r.get("fecha", "")), reverse=True)
    return docs


def marcar_estado(doc_id: str, estado: str) -> bool:
    try:
        _cliente().collection("correos").document(doc_id).update({"estado": estado})
        return True
    except Exception:
        return False

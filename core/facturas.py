"""
core/facturas.py — Registro de facturas de Pagés en Firestore (administración).

Dos colecciones:
  - `facturas_emitidas`  → las que EMITE Pagés (cuentas por COBRAR). Estados:
                           Emitida → Enviada → Cobrada.
  - `facturas_recibidas` → las que RECIBE Pagés (cuentas por PAGAR). Estados:
                           Pendiente → Pagada.

El PDF se guarda dentro del propio registro en base64 (una factura pesa ~25 KB, muy
por debajo del límite de 1 MB por documento de Firestore). Si alguna fuera demasiado
grande, se guardan solo los datos y se avisa (`pdf_guardado: False`).

El número de factura correlativo vive en `admin_config/facturas`.

Si Firestore no está disponible (p. ej. en local sin credenciales) las funciones
fallan de forma controlada y la app sigue funcionando.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

EMITIDAS = "facturas_emitidas"
RECIBIDAS = "facturas_recibidas"

ESTADOS_EMITIDA = ["Emitida", "Enviada", "Cobrada"]
ESTADOS_RECIBIDA = ["Pendiente", "Pagada"]

# Firestore admite ~1 MB por documento; dejamos margen para el resto de campos.
_MAX_PDF_B64 = 900_000

_db = None


def _cliente():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client()
    return _db


_hay_conexion: bool | None = None


def disponible() -> bool:
    """¿Se puede hablar con Firestore? Se comprueba UNA vez y se recuerda: sin
    credenciales (p. ej. en local) crear el cliente tarda ~10 s en rendirse, y si no
    lo recordáramos la app se arrastraría en cada pantallazo."""
    global _hay_conexion
    if _hay_conexion is None:
        try:
            _cliente()
            _hay_conexion = True
        except Exception:
            _hay_conexion = False
    return _hay_conexion


# ------------------------------------------------- ajustes (admin_config)
def config() -> dict:
    """Ajustes de administración: numeración y envío por correo."""
    try:
        doc = _cliente().collection("admin_config").document("facturas").get()
        if doc.exists:
            return doc.to_dict() or {}
    except Exception:
        pass
    return {}


def fijar_config(campos: dict) -> bool:
    try:
        _cliente().collection("admin_config").document("facturas").set(campos, merge=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- numeración
def siguiente_numero(por_defecto: str = "2026/001") -> str:
    """Número que le toca a la próxima factura emitida."""
    return config().get("siguiente_numero") or por_defecto


def fijar_siguiente_numero(numero: str) -> bool:
    return fijar_config({"siguiente_numero": numero.strip()})


def numero_mas_uno(numero: str) -> str:
    """'2026/013' → '2026/014'. Respeta los ceros a la izquierda. '13' → '14'."""
    numero = (numero or "").strip()
    if "/" in numero:
        cabeza, cola = numero.rsplit("/", 1)
        if cola.isdigit():
            return f"{cabeza}/{str(int(cola) + 1).zfill(len(cola))}"
        return numero
    if numero.isdigit():
        return str(int(numero) + 1).zfill(len(numero))
    return numero


# ------------------------------------------------------------------ guardar
def _guardar(coleccion: str, doc: dict, pdf: bytes | None) -> str | None:
    try:
        doc = dict(doc)
        doc["creada"] = datetime.now(timezone.utc)
        doc["pdf_guardado"] = False
        if pdf:
            b64 = base64.b64encode(pdf).decode()
            if len(b64) <= _MAX_PDF_B64:
                doc["pdf_b64"] = b64
                doc["pdf_guardado"] = True
        _, ref = _cliente().collection(coleccion).add(doc)
        return ref.id
    except Exception:
        return None


def guardar_emitida(numero: str, cliente: str, concepto: str, fecha: str,
                    base: float, iva: float, retencion: float, total: float,
                    pdf: bytes | None = None, archivo: str = "") -> str | None:
    """Guarda una factura emitida (cuenta por cobrar) con estado 'Emitida'."""
    return _guardar(EMITIDAS, {
        "numero": numero, "cliente": cliente, "concepto": concepto, "fecha": fecha,
        "base": float(base), "iva": float(iva), "retencion": float(retencion),
        "total": float(total), "estado": "Emitida", "archivo": archivo,
        "enviada_el": "", "cobrada_el": "",
    }, pdf)


def guardar_recibida(proveedor: str, numero: str, fecha: str, vencimiento: str,
                     base: float, iva: float, total: float, concepto: str = "",
                     pdf: bytes | None = None, archivo: str = "",
                     origen: str = "subida a mano") -> str | None:
    """Guarda una factura recibida (cuenta por pagar) con estado 'Pendiente'."""
    return _guardar(RECIBIDAS, {
        "proveedor": proveedor, "numero": numero, "fecha": fecha,
        "vencimiento": vencimiento, "base": float(base), "iva": float(iva),
        "total": float(total), "concepto": concepto, "estado": "Pendiente",
        "archivo": archivo, "origen": origen, "pagada_el": "",
    }, pdf)


# ------------------------------------------------------------------- listar
def listar(coleccion: str, limite: int = 300) -> list[dict]:
    """Devuelve los registros, los más nuevos primero. Lista vacía si algo falla."""
    try:
        from google.cloud import firestore
        q = (_cliente().collection(coleccion)
             .order_by("creada", direction=firestore.Query.DESCENDING)
             .limit(limite))
        salida = []
        for d in q.stream():
            r = d.to_dict() or {}
            r["_id"] = d.id
            salida.append(r)
        return salida
    except Exception:
        return []


def pdf_de(registro: dict) -> bytes | None:
    """Recupera el PDF guardado dentro del registro (si se guardó)."""
    b64 = registro.get("pdf_b64")
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


# ---------------------------------------------------------------- modificar
def cambiar_estado(coleccion: str, doc_id: str, estado: str) -> bool:
    """Cambia el estado y deja constancia de la fecha del cambio."""
    campos: dict = {"estado": estado}
    hoy = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    if estado == "Enviada":
        campos["enviada_el"] = hoy
    elif estado == "Cobrada":
        campos["cobrada_el"] = hoy
    elif estado == "Pagada":
        campos["pagada_el"] = hoy
    try:
        _cliente().collection(coleccion).document(doc_id).update(campos)
        return True
    except Exception:
        return False


def borrar(coleccion: str, doc_id: str) -> bool:
    try:
        _cliente().collection(coleccion).document(doc_id).delete()
        return True
    except Exception:
        return False

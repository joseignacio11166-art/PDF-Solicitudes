"""
core/redsys.py — Procesa el export de operaciones de Redsys/Paygold.

Cada 'Cód. pedido' pasa por varios movimientos:
  - "Solicitud envío Paygold" -> Enviada  (link enviado al cliente; pendiente de cobro)
  - "Autorización Paygold"     -> Autorizada (el cliente pagó -> cobrado)
                               -> Denegada / Cancelada / Sin Finalizar (intentos fallidos)

Resumimos por pedido para saber su estado final:
  Cobrada  = el cliente pagó (hay una "Autorizada")  -> toca pagar la póliza a la aseguradora
  Pendiente = se envió el link pero aún no ha pagado
  Fallida  = solo hubo intentos denegados/cancelados
"""
from __future__ import annotations

import csv
import io

_COLS = {
    "fecha": "Fecha",
    "hora": "Hora",
    "pedido": "Cód. pedido",
    "resultado": "Resultado operación y código",
    "importe": "Importe Euros",
    "tipo": "Tipo operación",
    "tarjeta": "N.º tarjeta",
}


def _num(s: str) -> float:
    try:
        return float(str(s).replace(".", "").replace(",", ".")) if "," in str(s) else float(s)
    except Exception:
        return 0.0


def leer_operaciones(contenido: bytes) -> list[dict]:
    texto = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = contenido.decode(enc)
            break
        except Exception:
            texto = None
    if texto is None:
        texto = contenido.decode("latin-1", "ignore")

    filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    if not filas:
        return []
    cab = [c.strip() for c in filas[0]]

    def idx(nombre_col: str) -> int:
        for i, c in enumerate(cab):
            if c == nombre_col:
                return i
        return -1

    ix = {k: idx(v) for k, v in _COLS.items()}
    out = []
    for fila in filas[1:]:
        if not any(fila):
            continue
        def g(k):
            i = ix.get(k, -1)
            return fila[i].strip() if 0 <= i < len(fila) else ""
        out.append({
            "fecha": g("fecha"), "hora": g("hora"), "pedido": g("pedido"),
            "resultado": g("resultado"), "importe": _num(g("importe")),
            "tipo": g("tipo"), "tarjeta": g("tarjeta"),
        })
    return out


def _clasificar(resultado: str) -> str:
    r = resultado.strip().lower()
    if r.startswith("autorizada"):
        return "Cobrada"
    if r.startswith("enviada"):
        return "Enviada"
    if r.startswith("denegada"):
        return "Denegada"
    if r.startswith("cancelada"):
        return "Cancelada"
    if "sin finalizar" in r:
        return "Sin finalizar"
    return "Otro"


def resumen_por_pedido(operaciones: list[dict]) -> list[dict]:
    """Un registro por 'Cód. pedido' con su estado final e importe."""
    por: dict[str, dict] = {}
    for op in operaciones:
        p = op["pedido"]
        if not p:
            continue
        d = por.setdefault(p, {"pedido": p, "importe": 0.0, "estados": set(),
                               "fecha": op["fecha"], "hora": op["hora"], "tarjeta": ""})
        d["estados"].add(_clasificar(op["resultado"]))
        if op["importe"]:
            d["importe"] = op["importe"]
        if op["tarjeta"]:
            d["tarjeta"] = op["tarjeta"]
        # quedarse con la fecha/hora del último movimiento
        if (op["fecha"], op["hora"]) >= (d["fecha"], d["hora"]):
            d["fecha"], d["hora"] = op["fecha"], op["hora"]

    filas = []
    for p, d in por.items():
        est = d["estados"]
        if "Cobrada" in est:
            estado = "Cobrada"          # el cliente pagó
        elif "Enviada" in est:
            estado = "Pendiente"        # link enviado, sin pagar aún
        else:
            estado = "Fallida"          # solo denegadas/canceladas
        filas.append({
            "pedido": p, "estado": estado, "importe": round(d["importe"], 2),
            "fecha": d["fecha"], "tarjeta": d["tarjeta"],
            "intentos": len(d["estados"]),
        })
    # ordenar: cobradas y pendientes primero, por fecha desc
    orden = {"Cobrada": 0, "Pendiente": 1, "Fallida": 2}
    filas.sort(key=lambda r: (orden.get(r["estado"], 9), r["fecha"]), reverse=False)
    return filas


# ---------- Estado "pagado a la aseguradora" (Firestore) ----------
_db = None
_COL_PAGOS = "redsys_pagos"


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


def _docid(pedido: str) -> str:
    return pedido.replace("/", "__").replace(" ", "_") or "sin_pedido"


def pagos_guardados() -> set[str]:
    """Conjunto de 'Cód. pedido' marcados como pagados a la aseguradora."""
    try:
        return {d.to_dict().get("pedido", "") for d in _cliente().collection(_COL_PAGOS).stream()}
    except Exception:
        return set()


def marcar_pago(pedido: str, pagado: bool) -> None:
    try:
        doc = _cliente().collection(_COL_PAGOS).document(_docid(pedido))
        if pagado:
            doc.set({"pedido": pedido, "pagado": True})
        else:
            doc.delete()
    except Exception:
        pass


def totales(resumen: list[dict]) -> dict:
    def suma(estado):
        return round(sum(r["importe"] for r in resumen if r["estado"] == estado), 2)
    def cuenta(estado):
        return sum(1 for r in resumen if r["estado"] == estado)
    return {
        "cobrado": suma("Cobrada"), "n_cobrado": cuenta("Cobrada"),
        "pendiente": suma("Pendiente"), "n_pendiente": cuenta("Pendiente"),
        "fallida": suma("Fallida"), "n_fallida": cuenta("Fallida"),
        "n_total": len(resumen),
    }

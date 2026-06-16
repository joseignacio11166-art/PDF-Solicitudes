"""
reglas/inspeccionar_sanitas.py — Herramienta de DESARROLLO (no se usa en producción).

Lee el PDF en blanco de Sanitas y lista, por página, cada campo con su posición
(rect), tipo y, para casillas, sus estados "on" reales. Sirve para casar casillas
con su pregunta por POSICIÓN (los nombres internos engañan).
"""
from __future__ import annotations

import sys

from pypdf import PdfReader
from pypdf.generic import IndirectObject

from config import PLANTILLA_SANITAS


def estados_on(widget) -> list[str]:
    """Devuelve los estados '/On' posibles de una casilla (los que no son /Off)."""
    ap = widget.get("/AP")
    if not ap:
        return []
    ap = ap.get_object() if isinstance(ap, IndirectObject) else ap
    n = ap.get("/N") if hasattr(ap, "get") else None
    if not n:
        return []
    n = n.get_object() if isinstance(n, IndirectObject) else n
    try:
        return [k for k in n.keys() if k != "/Off"]
    except Exception:
        return []


def main(paginas: set[int]) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    reader = PdfReader(str(PLANTILLA_SANITAS))
    for i, page in enumerate(reader.pages):
        if paginas and i not in paginas:
            continue
        annots = page.get("/Annots")
        if not annots:
            continue
        print(f"\n========== PÁGINA {i + 1} (índice {i}) ==========")
        filas = []
        for a in annots:
            obj = a.get_object()
            if obj.get("/Subtype") != "/Widget":
                continue
            # Nombre: puede estar en el propio widget o en su padre.
            nombre = obj.get("/T")
            parent = obj.get("/Parent")
            if nombre is None and parent is not None:
                nombre = parent.get_object().get("/T")
            ft = obj.get("/FT")
            if ft is None and parent is not None:
                ft = parent.get_object().get("/FT")
            rect = obj.get("/Rect")
            try:
                x, y = float(rect[0]), float(rect[1])
            except Exception:
                x, y = 0.0, 0.0
            ons = estados_on(obj) if ft == "/Btn" else []
            filas.append((round(y, 1), round(x, 1), str(nombre), str(ft), ons))

        # Ordenar de arriba-abajo (y desc), izq-der (x asc)
        filas.sort(key=lambda f: (-f[0], f[1]))
        for y, x, nombre, ft, ons in filas:
            extra = f"  on={ons}" if ons else ""
            print(f"  y={y:6.1f} x={x:6.1f}  {ft:5}  {nombre}{extra}")


if __name__ == "__main__":
    # Por defecto, páginas 1, 3 y 4 (índices 0, 2, 3).
    args = sys.argv[1:]
    paginas = {int(a) for a in args} if args else {0, 2, 3}
    main(paginas)

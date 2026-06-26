"""
core/rellenar_nuevamutua.py — Rellena Nueva Mutua escribiendo texto por coordenadas.

El PDF original no tiene campos: generamos una capa (overlay) con reportlab y la
fusionamos sobre el PDF en blanco con pypdf. La firma se deja vacía.
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from config import PLANTILLA_NUEVAMUTUA, SALIDAS_DIR
from reglas.nuevamutua import construir_textos_nuevamutua

ANCHO, ALTO = 595, 842
FUENTE = "Helvetica"
TAM = 9


def _overlay(textos_por_pagina: list[list[tuple]], imgs_por_pagina=None) -> PdfReader:
    """Crea un PDF en memoria con el texto colocado (y opcionalmente una imagen por página)."""
    imgs_por_pagina = imgs_por_pagina or [None] * len(textos_por_pagina)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ANCHO, ALTO))
    c.setFont(FUENTE, TAM)
    for textos, img in zip(textos_por_pagina, imgs_por_pagina):
        for texto, x, y in textos:
            c.drawString(x, y, str(texto))
        if img:
            from reportlab.lib.utils import ImageReader
            png, ix, iy, iw, ih = img
            c.drawImage(ImageReader(io.BytesIO(png)), ix, iy, width=iw, height=ih,
                        mask="auto", preserveAspectRatio=True, anchor="sw")
        c.showPage()
        c.setFont(FUENTE, TAM)
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def rellenar_nuevamutua(datos: dict, ruta_salida: str | Path | None = None,
                        hoy: date | None = None, firma_png: bytes | None = None) -> dict:
    construido = construir_textos_nuevamutua(datos, hoy=hoy)

    base = PdfReader(str(PLANTILLA_NUEVAMUTUA))
    # Firma opcional, estampada en la página 2 sobre la línea "D./Dña. (Firma Tomador):" (y≈86).
    imgs = [None, (firma_png, 200, 78, 170, 32)] if firma_png else None
    overlay = _overlay([construido["pagina1"], construido["pagina2"]], imgs)

    writer = PdfWriter()
    for i, page in enumerate(base.pages):
        if i < len(overlay.pages):
            page.merge_page(overlay.pages[i])
        writer.add_page(page)

    SALIDAS_DIR.mkdir(exist_ok=True)
    if ruta_salida is None:
        apellidos = (datos.get("apellidos") or "solicitud").strip().replace(" ", "_")
        ruta_salida = SALIDAS_DIR / f"nuevamutua_{apellidos}.pdf"
    ruta_salida = Path(ruta_salida)

    with open(ruta_salida, "wb") as fh:
        writer.write(fh)

    return {"ruta": ruta_salida, "avisos": construido["avisos"], "parar": construido["parar"]}


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from config import ENTRADAS_DIR
    from core.leer_cotizacion import leer_cotizacion
    from cerebro.prompt_extraccion import extraer_datos

    for pdf in sorted(ENTRADAS_DIR.glob("*.pdf")):
        crudos = leer_cotizacion(pdf)
        if crudos.get("aseguradora_detectada") != "NUEVA_MUTUA":
            continue
        print(f"Cotización: {pdf.name}")
        datos = extraer_datos(crudos)
        res = rellenar_nuevamutua(datos)
        print(f"PDF generado: {res['ruta']}")
        print(f"parar={res['parar']}  avisos={res['avisos']}")
        break

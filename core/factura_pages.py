"""
core/factura_pages.py — Facturas EMITIDAS por Pagés Seguros en PDF (mismo esquema que el Excel).

Cabecera: logo de Pagés (izq) + datos del emisor (der). Bloque de cliente, conceptos
(con grupo opcional tipo "Gastos compartidos"), y totales: Base + IVA 21% + Retención 19%
opcional + Total (resaltado en azul). Calcula los totales; los importes los pone quien factura.
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config import BASE_DIR

_LOGO = BASE_DIR / "assets" / "pages_logo.png"

_EMISOR = ["CIF - B87699443", "Calle Hermosilla 80 Pl 2ª Letra A", "28001 MADRID - ESPAÑA",
           "www.pagesseguros.com", "Tel: +34 910 574 872"]
_IBAN = "ES20 0049 3026 88 2614487942"
_AZUL = (0.10, 0.20, 0.45)
_AZULT = (0.09, 0.22, 0.40)   # barra del total
_GRIS = (0.30, 0.34, 0.40)
_TINTA = (0.12, 0.14, 0.18)


def _eur(x: float) -> str:
    return f"{x:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".") + " €"


def generar_factura(datos: dict) -> bytes:
    """datos: cliente, cif_cliente, dir_cliente(list[str]), fecha, numero,
    grupo(str opcional), conceptos(list[(desc, importe)]), retencion(bool)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    xL = 20 * mm
    xR = W - 20 * mm
    y = H - 20 * mm

    # ---- Cabecera: logo (izq) + emisor (der) ----
    if _LOGO.exists():
        try:
            img = ImageReader(str(_LOGO))
            iw, ih = img.getSize()
            w = 46 * mm
            h = w * ih / iw
            c.drawImage(img, xL, y - h + 4, width=w, height=h, mask="auto")
        except Exception:
            pass
    c.setFillColorRGB(*_AZUL)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(xR, y, _EMISOR[0])
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(*_GRIS)
    yy = y
    for ln in _EMISOR[1:]:
        yy -= 11
        c.drawRightString(xR, yy, ln)

    # ---- Cliente + factura (debajo de la cabecera) ----
    y -= 66
    c.setFillColorRGB(*_TINTA)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(xL, y, "CLIENTE:")
    c.drawString(xR - 70 * mm, y, "FECHA:")
    c.drawString(xR - 25 * mm, y, str(datos.get("fecha", "")))
    y -= 13
    c.setFont("Helvetica-Bold", 11)
    c.drawString(xL, y, datos.get("cliente", ""))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(xR - 70 * mm, y, "FACTURA Nº")
    c.drawString(xR - 25 * mm, y, str(datos.get("numero", "")))
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(*_GRIS)
    for ln in ([datos.get("cif_cliente", "")] + list(datos.get("dir_cliente", []))):
        if ln:
            y -= 12
            c.drawString(xL, y, ln)

    # ---- Conceptos ----
    y -= 26
    c.setFillColorRGB(*_TINTA)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(xL, y, "CONCEPTO:")
    c.drawRightString(xR, y, "Monto")
    c.setStrokeColorRGB(0.78, 0.80, 0.84)
    c.setLineWidth(0.6)
    c.line(xL, y - 5, xR, y - 5)

    base = 0.0
    if datos.get("grupo"):
        y -= 17
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(*_TINTA)
        c.drawString(xL, y, str(datos["grupo"]))
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(*_TINTA)
    for desc, importe in datos.get("conceptos", []):
        y -= 16
        c.drawString(xL + 4, y, str(desc))
        c.drawRightString(xR, y, _eur(importe))
        base += float(importe)

    # ---- Totales ----
    iva = round(base * 0.21, 2)
    ret = round(base * 0.19, 2) if datos.get("retencion") else 0.0
    total = round(base + iva - ret, 2)

    y -= 20
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(*_TINTA)
    c.drawString(xL + 4, y, "Base Imponible:")
    c.drawRightString(xR, y, _eur(round(base, 2)))
    y -= 15
    c.drawString(xL + 4, y, "IVA")
    c.drawString(xL + 70 * mm, y, "21%")
    c.drawRightString(xR, y, _eur(iva))
    if ret:
        y -= 15
        c.drawString(xL + 4, y, "Retención")
        c.drawString(xL + 70 * mm, y, "19%")
        c.drawRightString(xR, y, "-" + _eur(ret))
    # barra del total (azul, texto blanco)
    y -= 20
    c.setFillColorRGB(*_AZULT)
    c.rect(xL + 62 * mm, y - 5, xR - (xL + 62 * mm), 18, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(xL + 65 * mm, y, "Total a pagar")
    c.drawRightString(xR - 3, y, _eur(total))

    # ---- Pago ----
    y -= 40
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(*_GRIS)
    c.drawString(xL, y, "Forma de pago: Transferencia Bancaria")
    y -= 12
    c.drawString(xL, y, f"IBAN: {_IBAN}")

    c.showPage()
    c.save()
    return buf.getvalue()


# ---- Presets con los datos/ejemplos que pasó la usuaria ----
_REDDO = {"cliente": "REDDO CREDIT, S.L.", "cif_cliente": "CIF - B88635487",
          "dir_cliente": ["Calle Hermosilla 80 2º -A.", "Madrid - 28001"]}
_QUORUM = {"cliente": "QUORUM LOGISTIC CORP", "cif_cliente": "CIF - P19000085771",
           "dir_cliente": ["2893 Executive Park Drive", "Suite 202, Weston, 33331", "EE.UU"]}
_MT = {"cliente": "MARÍA TERESA YABUR ADDIE", "cif_cliente": "", "dir_cliente": []}


def reddo_alquiler(fecha, numero, mes="enero 2026", importe=1167.89) -> bytes:
    return generar_factura({**_REDDO, "fecha": fecha, "numero": numero, "retencion": True,
                            "conceptos": [(f"Alquiler oficina Hermosilla 80, 2º A · Mes: {mes}", importe)]})


def reddo_gastos(fecha, numero, electricidad=730.85, alarma=372.71,
                 internet=3940.93, limpieza=1848.69) -> bytes:
    return generar_factura({**_REDDO, "fecha": fecha, "numero": numero, "retencion": False,
                            "grupo": "Gastos compartidos",
                            "conceptos": [("Electricidad", electricidad), ("Alarma", alarma),
                                          ("Internet y comunicaciones", internet),
                                          ("Limpieza, material de oficina y limpieza", limpieza)]})


def quorum_comisiones(fecha, numero, mes="Noviembre 2025", importe=2979.93) -> bytes:
    return generar_factura({**_QUORUM, "fecha": fecha, "numero": numero, "retencion": False,
                            "conceptos": [(f"Comisiones {mes}", importe)]})


def mt_factura(fecha, numero, concepto="HP enero 2026", importe=181.5, retencion=False) -> bytes:
    return generar_factura({**_MT, "fecha": fecha, "numero": numero, "retencion": retencion,
                            "conceptos": [(concepto, importe)]})

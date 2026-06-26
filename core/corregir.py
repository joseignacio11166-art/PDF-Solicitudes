"""
core/corregir.py — Corregir un dato en un PDF ya generado, sin rehacerlo todo.

Sube un PDF (Sanitas o Nueva Mutua), se leen los datos clave actuales, cambias lo
que necesites y se devuelve el PDF corregido EN SITIO (se conserva el resto, incluida
la firma si la hubiera):
- Sanitas: tiene campos AcroForm -> se actualizan los campos cambiados.
- Nueva Mutua: el texto va "pintado" -> se tapa el valor viejo y se repinta el nuevo.
"""
from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter

# Campos lógicos -> nombres internos del AcroForm de Sanitas (incluye duplicados pág. 4)
_SANITAS = {
    "Nombre": ["nombre tomador", "nombre asegurado pag310"],
    "Nº documento": ["numero documento", "num doc10"],
    "Email": ["email", "Teléfono 2_210"],
    "Teléfono móvil": ["movil1", "movil2", "movil1 pag310", "movil2 pag310"],
    "Dirección": ["domicilio tomador"],
    "Población": ["municipio tomador"],
    "Provincia": ["provincia tomador"],
    "Código postal": ["cp tomador"],
}

# Campos lógicos -> posición en Nueva Mutua (x, top, ancho_a_tapar). Calibrado v2.
_H, _DY = 842, 9
_NM = {
    "Nombre": (120, 179, 250),
    "Nº documento": (120, 193, 150),
    "Dirección": (43, 221, 400),
    "Población": (85, 235, 180),
    "Provincia": (321, 235, 110),
    "Código postal": (100, 249, 80),
    "Email": (360, 249, 190),
    "Teléfono móvil": (343, 264, 110),
}


def _y(top: float) -> float:
    return _H - top - _DY


def detectar(ruta: str) -> str | None:
    """Devuelve 'sanitas', 'nuevamutua' o None."""
    try:
        campos = PdfReader(ruta).get_fields() or {}
        if "nombre tomador" in campos:
            return "sanitas"
    except Exception:
        pass
    try:
        import pdfplumber
        t = (pdfplumber.open(ruta).pages[0].extract_text() or "").upper()
        if "PROFESIONAL FAMILIA" in t or "NUEVAMUTUA" in t or "NUEVA MUTUA" in t:
            return "nuevamutua"
    except Exception:
        pass
    return None


# ---------- Sanitas ----------
def leer_sanitas(ruta: str) -> dict:
    campos = PdfReader(ruta).get_fields() or {}
    out = {}
    for log, internos in _SANITAS.items():
        val = ""
        for fn in internos:
            if fn in campos and campos[fn].get("/V"):
                val = str(campos[fn]["/V"])
                break
        out[log] = val
    return out


def corregir_sanitas(ruta: str, cambios: dict) -> bytes:
    reader = PdfReader(ruta)
    writer = PdfWriter()
    writer.append(reader)
    valores = {}
    for log, nuevo in cambios.items():
        for fn in _SANITAS.get(log, []):
            valores[fn] = nuevo
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, valores, auto_regenerate=False)
        except Exception:
            pass
    try:
        writer.set_need_appearances_writer(True)
    except Exception:
        pass
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------- Nueva Mutua ----------
def leer_nm(ruta: str) -> dict:
    import pdfplumber
    pg = pdfplumber.open(ruta).pages[0]
    out = {}
    for log, (x, top, w) in _NM.items():
        try:
            # Quitar los espacios "fantasma" de la plantilla y reconstruir los reales por hueco.
            chars = [c for c in pg.crop((x - 2, top - 2, x + w, top + 12)).chars if c["text"].strip()]
            chars.sort(key=lambda c: c["x0"])
            txt, prev = "", None
            for c in chars:
                if prev is not None and c["x0"] - prev["x1"] > 1.5:
                    txt += " "
                txt += c["text"]
                prev = c
        except Exception:
            txt = ""
        out[log] = txt.strip()
    return out


def corregir_nm(ruta: str, cambios: dict) -> bytes:
    from reportlab.pdfgen import canvas
    base = PdfReader(ruta)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    for log, nuevo in cambios.items():
        if log not in _NM:
            continue
        x, top, w = _NM[log]
        y = _y(top)
        c.setFillColorRGB(1, 1, 1)            # tapar valor viejo (blanco)
        c.rect(x - 2, y - 3, w, 14, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)            # pintar valor nuevo
        c.setFont("Helvetica", 9)
        c.drawString(x, y, str(nuevo))
    c.showPage()
    c.save()
    buf.seek(0)
    overlay = PdfReader(buf)
    writer = PdfWriter()
    for i, page in enumerate(base.pages):
        if i == 0:
            page.merge_page(overlay.pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def extraer_firma(ruta: str) -> bytes | None:
    """Recorta la firma de la última página del PDF antiguo (PNG con fondo transparente)."""
    try:
        import pdfplumber
        import pypdfium2
        with pdfplumber.open(ruta) as pdf:
            last = pdf.pages[-1]
            W, Hh = last.width, last.height
            # La línea de firma es la ÚLTIMA "firma" (más abajo); las otras son texto legal.
            firmas = [w for w in last.extract_words() if "firma" in w["text"].lower()]
            firma = max(firmas, key=lambda w: w["top"]) if firmas else None
        if firma:
            # recortar DESPUÉS de la etiqueta "(Firma Tomador):", sobre la línea
            x0, t, x1, b = firma["x1"] + 70, firma["top"] - 22, W - 25, firma["top"] + 12
        else:
            x0, t, x1, b = 200, Hh - 95, W - 25, Hh - 55

        doc = pypdfium2.PdfDocument(ruta)
        scale = 3.0
        img = doc[len(doc) - 1].render(scale=scale).to_pil().convert("RGBA")
        crop = img.crop((int(x0 * scale), int(t * scale), int(x1 * scale), int(b * scale)))
        # blanco -> transparente, para que solo se vea el trazo de la firma
        px = [(r, g, b2, 0) if (r > 225 and g > 225 and b2 > 225) else (r, g, b2, a)
              for (r, g, b2, a) in crop.getdata()]
        crop.putdata(px)
        out = io.BytesIO()
        crop.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def leer(ruta: str, tipo: str) -> dict:
    return leer_sanitas(ruta) if tipo == "sanitas" else leer_nm(ruta)


def corregir(ruta: str, tipo: str, cambios: dict) -> bytes:
    return corregir_sanitas(ruta, cambios) if tipo == "sanitas" else corregir_nm(ruta, cambios)

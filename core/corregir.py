"""
core/corregir.py — Corregir un PDF ya hecho (Sanitas o Nueva Mutua), sin rehacerlo todo.

Sube un PDF, se leen los datos actuales (todos los campos), cambias lo que necesites
y se devuelve el PDF corregido EN SITIO:
- Sanitas: tiene campos AcroForm -> se actualizan los campos cambiados.
- Nueva Mutua: el texto va "pintado" -> se tapa el valor viejo y se repinta el nuevo.

Además: opción de INCLUIR LA FIRMA o no. Si no, se tapa (blanco) la zona de la firma.
"""
from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter

# ============================ SANITAS (AcroForm) ============================
# Campos lógicos -> nombres internos del AcroForm (incluye duplicados de pág. 3/4).
_SANITAS = {
    "Nombre": ["nombre tomador", "nombre asegurado pag310"],
    "Nº documento": ["numero documento", "num doc10"],
    "Nacionalidad": ["nacionalidad", "nacionalidado210"],
    "Producto": ["pto. anterior"],
    "Mediador": ["mediador"],
    "Email": ["email", "Teléfono 2_210"],
    "Teléfono móvil": ["movil1", "movil2", "movil1 pag310", "movil2 pag310"],
    "Dirección": ["domicilio tomador"],
    "Piso / puerta": ["domicilio tomador n"],
    "Población": ["municipio tomador"],
    "Provincia": ["provincia tomador"],
    "Código postal": ["cp tomador"],
}
# Fechas Sanitas (texto en 3 campos): lógico -> [(día, mes, año), ...] (pág.1 + pág.3)
_SANITAS_FECHA = {
    "Fecha de nacimiento": [("dia2", "mes2", "año2"), ("día_410", "mes_510", "año_510")],
}

# ============================ NUEVA MUTUA (overlay) ============================
# Calibrado v2 (mismas coords que reglas/nuevamutua.py). Texto simple: (x, top, ancho).
_H, _DY = 842, 9
_NM = {
    "Mediador": (240, 138, 85),
    "Nombre": (120, 179, 250),
    "Nº documento": (120, 193, 150),
    "Dirección": (43, 221, 400),
    "Población": (85, 235, 180),
    "Provincia": (321, 235, 110),
    "Código postal": (100, 249, 80),
    "Email": (360, 249, 190),
    "Teléfono fijo": (96, 264, 110),
    "Teléfono móvil": (343, 264, 110),
    "Profesión": (135, 278, 180),
    "Estado civil": (418, 317, 120),
    "Peso (kg)": (290, 481, 60),
    "Altura (cm)": (470, 481, 60),
    "Repatriación · Dirección": (43, 407, 400),
    "Repatriación · Población": (85, 421, 180),
    "Repatriación · Provincia": (321, 421, 110),
    "Repatriación · Código postal": (100, 434, 80),
}
# Fechas NM: lógico -> ([(x,top,ancho) día, mes, año], dígitos_del_año)
_NM_FECHA = {
    "Fecha de nacimiento": ([(166, 317, 16), (194, 317, 16), (213, 317, 26)], 4),
    "Fecha de alta deseada": ([(125, 138, 14), (143, 138, 14), (172, 138, 22)], 2),
}
# Sexo NM: valor -> (x, top) de la "X"
_NM_SEXO = {"Hombre": (268, 315), "Mujer": (314, 315)}


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

    def _val(internos: list[str]) -> str:
        for fn in internos:
            v = campos.get(fn, {}).get("/V")
            if v:
                return str(v)
        return ""

    out = {log: _val(internos) for log, internos in _SANITAS.items()}
    for log, grupos in _SANITAS_FECHA.items():
        d = m = a = ""
        for fd, fm, fa in grupos:
            d = d or str(campos.get(fd, {}).get("/V") or "")
            m = m or str(campos.get(fm, {}).get("/V") or "")
            a = a or str(campos.get(fa, {}).get("/V") or "")
        out[log] = f"{d}/{m}/{a}" if (d or m or a) else ""
    return out


def corregir_sanitas(ruta: str, cambios: dict) -> bytes:
    reader = PdfReader(ruta)
    writer = PdfWriter()
    writer.append(reader)
    valores: dict[str, str] = {}
    for log, nuevo in cambios.items():
        if log in _SANITAS:
            for fn in _SANITAS[log]:
                valores[fn] = nuevo
        elif log in _SANITAS_FECHA:
            partes = [p.strip() for p in str(nuevo).split("/")]
            if len(partes) == 3:
                d, m, a = partes
                for fd, fm, fa in _SANITAS_FECHA[log]:
                    valores[fd], valores[fm], valores[fa] = d, m, a
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
def _leer_celda(pg, x: float, top: float, w: float) -> str:
    """Lee el texto de una celda quitando los espacios 'fantasma' de la plantilla."""
    try:
        chars = [c for c in pg.crop((x - 2, top - 2, x + w, top + 12)).chars
                 if c["text"].strip() and c["text"] != "_"]
        chars.sort(key=lambda c: c["x0"])
        txt, prev = "", None
        for c in chars:
            if prev is not None and c["x0"] - prev["x1"] > 1.5:
                txt += " "
            txt += c["text"]
            prev = c
        return txt.strip()
    except Exception:
        return ""


def leer_nm(ruta: str) -> dict:
    import pdfplumber
    pg = pdfplumber.open(ruta).pages[0]
    out = {log: _leer_celda(pg, x, top, w) for log, (x, top, w) in _NM.items()}
    for log, (celdas, _ndig) in _NM_FECHA.items():
        partes = ["".join(ch for ch in _leer_celda(pg, x, top, w) if ch.isdigit())
                  for (x, top, w) in celdas]
        out[log] = "/".join(partes) if any(partes) else ""
    sexo = ""
    for val, (x, top) in _NM_SEXO.items():
        if _leer_celda(pg, x - 2, top, 12):
            sexo = val
    out["Sexo"] = sexo
    return out


def corregir_nm(ruta: str, cambios: dict) -> bytes:
    from reportlab.pdfgen import canvas
    base = PdfReader(ruta)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))

    def _tapa_y_pinta(x, top, w, texto):
        y = _y(top)
        c.setFillColorRGB(1, 1, 1)
        c.rect(x - 2, y - 3, w, 14, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 9)
        c.drawString(x, y, str(texto))

    for log, nuevo in cambios.items():
        if log in _NM:
            x, top, w = _NM[log]
            _tapa_y_pinta(x, top, w, nuevo)
        elif log in _NM_FECHA:
            celdas, ndig = _NM_FECHA[log]
            partes = [p.strip() for p in str(nuevo).split("/")]
            for i, (x, top, w) in enumerate(celdas):
                val = partes[i] if i < len(partes) else ""
                if i == 2 and ndig == 2 and len(val) > 2:
                    val = val[-2:]
                _tapa_y_pinta(x, top, w, val)
        elif log == "Sexo":
            for val, (x, top) in _NM_SEXO.items():
                c.setFillColorRGB(1, 1, 1)
                c.rect(x - 1, _y(top) - 3, 10, 13, fill=1, stroke=0)
            pos = _NM_SEXO.get(str(nuevo).capitalize())
            if pos:
                c.setFillColorRGB(0, 0, 0)
                c.setFont("Helvetica", 9)
                c.drawString(pos[0], _y(pos[1]), "X")

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


# ---------- Firma (quitar) ----------
def quitar_firma(pdf_bytes: bytes) -> bytes:
    """Tapa de blanco la zona de la firma (busca la palabra 'firma' más abajo de cada
    página y cubre desde ahí hacia la derecha y un poco por debajo)."""
    try:
        import pdfplumber
        from reportlab.pdfgen import canvas
        rects: list[list[tuple]] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                W, Hh = page.width, page.height
                words = page.extract_words()
                firmas = [w for w in words if "firma" in w["text"].lower()]
                page_rects = []
                if firmas:
                    f = max(firmas, key=lambda w: w["top"])  # la más abajo = la línea de firma
                    x0 = f["x1"] + 4
                    y0 = Hh - (f["top"] + 34)
                    page_rects.append((x0, y0, (W - 25) - x0, 40))
                rects.append((W, Hh, page_rects))

        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        for (W, Hh, page_rects) in rects:
            c.setPageSize((W, Hh))
            c.setFillColorRGB(1, 1, 1)
            for (x, y, w, h) in page_rects:
                if w > 0:
                    c.rect(x, y, w, h, fill=1, stroke=0)
            c.showPage()
        c.save()
        buf.seek(0)
        overlay = PdfReader(buf)
        base = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for i, page in enumerate(base.pages):
            if i < len(overlay.pages):
                page.merge_page(overlay.pages[i])
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        return pdf_bytes


def extraer_firma(ruta: str) -> bytes | None:
    """Recorta la firma de la última página del PDF (PNG con fondo transparente)."""
    try:
        import pdfplumber
        import pypdfium2
        with pdfplumber.open(ruta) as pdf:
            last = pdf.pages[-1]
            W, Hh = last.width, last.height
            words = last.extract_words()
        firmas = [w for w in words if "firma" in w["text"].lower()]
        firma = max(firmas, key=lambda w: w["top"]) if firmas else None
        if firma:
            linea = [w for w in words if abs(w["top"] - firma["top"]) <= 4]
            etiquetas = [w for w in linea if ":" in w["text"]]
            x_label = max(etiquetas, key=lambda w: w["x1"])["x1"] if etiquetas else firma["x1"]
            arriba = [w["bottom"] for w in words if w["top"] < firma["top"] - 3]
            t = (max(arriba) + 2) if arriba else (firma["top"] - 22)
            x0, x1, b = x_label + 4, W - 25, firma["top"] + 9
        else:
            x0, t, x1, b = 200, Hh - 95, W - 25, Hh - 60

        doc = pypdfium2.PdfDocument(ruta)
        scale = 3.0
        img = doc[len(doc) - 1].render(scale=scale).to_pil().convert("RGBA")
        crop = img.crop((int(x0 * scale), int(t * scale), int(x1 * scale), int(b * scale)))
        px = [(r, g, b2, 0) if min(r, g, b2) > 195 else (r, g, b2, a)
              for (r, g, b2, a) in crop.getdata()]
        crop.putdata(px)
        bbox = crop.getbbox()
        if not bbox:
            return None
        crop = crop.crop(bbox)
        out = io.BytesIO()
        crop.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def leer(ruta: str, tipo: str) -> dict:
    return leer_sanitas(ruta) if tipo == "sanitas" else leer_nm(ruta)


def corregir(ruta: str, tipo: str, cambios: dict, incluir_firma: bool = True) -> bytes:
    pdf = corregir_sanitas(ruta, cambios) if tipo == "sanitas" else corregir_nm(ruta, cambios)
    if not incluir_firma:
        pdf = quitar_firma(pdf)
    return pdf

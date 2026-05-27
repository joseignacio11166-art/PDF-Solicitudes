"""
AlumnusCare PDF Fill Server — v2
Rellena solicitudes de Sanitas y Nueva Mutua a partir de datos JSON.
Los templates PDF deben estar en el mismo directorio que este archivo.
"""
from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
import io, base64, os, traceback, datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Nombres de los templates (deben estar en el mismo directorio) ──────────────
# Sube estos dos archivos a tu repo de GitHub con estos nombres exactos:
SANITAS_TPL = os.path.join(BASE_DIR, "SS_castellano_editable_25.pdf")
NUEVA_MUTUA_TPL = os.path.join(BASE_DIR, "nueva_mutua.pdf")


# ── HELPERS ────────────────────────────────────────────────────────────────────

def parse_fecha_inicio(s):
    """Acepta DD/MM/YYYY → (dd, mm, yyyy)"""
    parts = (s or "01/01/2026").split("/")
    if len(parts) == 3:
        return parts[0].zfill(2), parts[1].zfill(2), parts[2]
    return "01", "01", "2026"

def parse_fecha_nac(s):
    """Acepta YYYY-MM-DD → (dd, mm, yyyy)"""
    parts = (s or "1990-01-01").split("-")
    if len(parts) == 3:
        return parts[2].zfill(2), parts[1].zfill(2), parts[0]
    return "01", "01", "1990"

def next_first_of_month(day, month, year):
    """Si el día no es 01, avanza al primer día del mes siguiente."""
    if day != "01":
        m, y = int(month), int(year)
        m += 1
        if m > 12:
            m, y = 1, y + 1
        return "01", str(m).zfill(2), str(y)
    return day, month, year

PROVINCIA_MAP = {
    "madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia",
    "sevilla": "Sevilla", "zaragoza": "Zaragoza", "málaga": "Málaga",
    "malaga": "Málaga", "bilbao": "Vizcaya", "alicante": "Alicante",
    "córdoba": "Córdoba", "cordoba": "Córdoba", "valladolid": "Valladolid",
    "granada": "Granada", "murcia": "Murcia", "palma": "Islas Baleares",
    "las palmas": "Las Palmas", "santa cruz": "Santa Cruz de Tenerife",
}

def provincia_from_municipio(municipio):
    return PROVINCIA_MAP.get((municipio or "").strip().lower(), "")


# ── SANITAS ────────────────────────────────────────────────────────────────────

def fill_sanitas(data):
    fi_day, fi_month, fi_year = parse_fecha_inicio(data.get("fecha_inicio", "01/01/2026"))
    fi_day, fi_month, fi_year = next_first_of_month(fi_day, fi_month, fi_year)
    fn_day, fn_month, fn_year = parse_fecha_nac(data.get("fecha_nac", "1990-01-01"))

    nombre    = data.get("nombre", "")
    num_doc   = data.get("num_doc", "")
    tipo_doc  = data.get("tipo_doc", "Pasaporte")
    sexo      = (data.get("sexo", "") or "").lower()
    email     = data.get("email", "")
    telefono  = data.get("telefono", "")
    direccion = data.get("direccion", "")
    numero    = data.get("numero", "")
    cp        = data.get("cp", "")
    municipio = data.get("municipio", "")
    peso      = str(data.get("peso", ""))
    altura    = str(data.get("altura", ""))
    q1        = (data.get("q1", "No") or "No").strip().lower()
    q2        = (data.get("q2", "No") or "No").strip().lower()
    q3        = (data.get("q3", "No") or "No").strip().lower()
    q4        = (data.get("q4", "No") or "No").strip().lower()
    provincia    = provincia_from_municipio(municipio)
    nacionalidad = data.get("nacionalidad", "")
    today = datetime.date.today()

    fv = {
        # ── Página 1: datos del mediador y tomador ──
        "Nueva póliza": "/On",
        "Corredor": "/On",
        "codigo mediador": "30149",
        "mediador": "Rose & Pagés S.L.",
        "Anual": "/On",
        "El Mediador": "/On",
        "nombre tomador": nombre,
        "numero documento": num_doc,
        "email": email,
        "movil1": telefono,
        "domicilio tomador": direccion,
        "domicilio tomador n": numero,
        "municipio tomador": municipio,
        "cp tomador": cp,
        "provincia tomador": provincia,
        "mes1": fi_month,
        "año1": fi_year,
        "asegurados": "1",
        # ── Página 3 (RGPD): marcar todos los Sí ──
        "Sí": "/On",
        # ── Página 4 (Cuestionario asegurado nº1) ──
        "nueva poliza30": "/On",
        "nombre asegurado pag310": nombre,
        "num doc10": num_doc,
        "parentesco10": "el mismo",
        "movil1 pag310": telefono,
        "mes_610": fi_month,
        "año_610": fi_year,
        "día_410": fn_day,
        "mes_510": fn_month,
        "año_510": fn_year,
        "peso10": peso,
        "estatura10": altura,
        "nacionalidado210": nacionalidad,
        # Sanitas o Bupa anterior: No
        "Sí_510": "/On",
        # Preguntas de salud
        **( {"No_310": "/On"} if q1 in ("no", "n")  else {} ),
        **( {"No_430": "/On"} if q2 in ("no", "n")  else {"Sí_730": "/On"} ),
        **( {"No_530": "/On"} if q3 in ("no", "n")  else {"Sí_830": "/On"} ),
        **( {"No_630": "/On"} if q4 in ("no", "n")  else {"Sí_930": "/On"} ),
        "No_6301": "/On",
        # Fecha firma
        "día_730": str(today.day).zfill(2),
        "mes_730": str(today.month).zfill(2),
        "año_730": str(today.year),
    }

    # Tipo documento
    doc_fields = {
        "Pasaporte": ["Pasaporte", "Pasaporte_211"],
        "NIE":       ["NIE", "NIE_210"],
        "NIF":       ["NIF", "NIF_210"],
    }
    for f in doc_fields.get(tipo_doc, doc_fields["Pasaporte"]):
        fv[f] = "/On"

    # Sexo
    if sexo in ("mujer", "female", "f", "woman"):
        fv["Mujer"] = "/On"
        fv["Mujer_210"] = "/On"
    else:
        fv["Hombre"] = "/On"
        fv["Hombre_210"] = "/On"

    # Rellenar el PDF
    reader = PdfReader(SANITAS_TPL)
    writer = PdfWriter()
    writer.append(reader)

    # Páginas 0-indexed: 0=portada, 2=RGPD, 3=cuestionario asegurado 1
    for page_idx in [0, 2, 3]:
        writer.update_page_form_field_values(
            writer.pages[page_idx], fv, auto_regenerate=False
        )

    # El email en página 3 (RGPD) se pone también con overlay
    # porque el campo email de esa página no acepta texto largo
    if email:
        PAGE_W, PAGE_H = 595.0, 842.0
        packet = io.BytesIO()
        c = rl_canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
        c.setFont("Helvetica", 8)
        c.drawString(50, 586.6, email)
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet)
        writer.pages[3].merge_page(overlay.pages[0])

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


# ── NUEVA MUTUA ────────────────────────────────────────────────────────────────

def fill_nueva_mutua(data):
    PAGE_W, PAGE_H = 595.32, 841.92

    fi_day, fi_month, fi_year = parse_fecha_inicio(data.get("fecha_inicio", "01/01/2026"))
    fn_day, fn_month, fn_year = parse_fecha_nac(data.get("fecha_nac", "1990-01-01"))

    nombre      = data.get("nombre", "")
    num_doc     = data.get("num_doc", "")
    sexo        = (data.get("sexo", "") or "").lower()
    email       = data.get("email", "")
    telefono    = data.get("telefono", "")
    direccion   = data.get("direccion", "")
    numero      = data.get("numero", "")
    cp          = data.get("cp", "")
    municipio   = data.get("municipio", "")
    peso        = str(data.get("peso", ""))
    altura      = str(data.get("altura", ""))
    q1          = (data.get("q1", "No") or "No").strip()
    estado_civil = data.get("estado_civil", "")
    provincia   = provincia_from_municipio(municipio)
    full_addr   = f"{direccion}, {numero}".rstrip(", ") if numero else direccion

    def ry(y):
        """Convierte coordenada Y (desde arriba) a coordenada PDF (desde abajo)."""
        return PAGE_H - y + 1

    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 8)

    # ── Fecha de alta deseada ──
    c.drawString(124, ry(147.6), fi_day)
    c.drawString(140, ry(147.6), fi_month)
    c.drawString(160, ry(147.6), fi_year)

    # ── Datos del tomador ──
    c.drawString(120, ry(186.6), nombre)
    c.drawString(73,  ry(200.6), num_doc)
    c.drawString(40,  ry(228),   full_addr)
    c.drawString(82,  ry(242.9), municipio)
    c.drawString(318, ry(242.9), provincia)
    c.drawString(97,  ry(257.4), cp)
    c.drawString(358, ry(257.4), email)
    c.drawString(340, ry(271.6), telefono)

    # ── Domicilio de prestación (igual que el tomador) ──
    c.drawString(40,  ry(360),   full_addr)
    c.drawString(82,  ry(382.7), municipio)
    c.drawString(318, ry(382.7), provincia)
    c.drawString(97,  ry(398.1), cp)
    c.drawString(358, ry(398.1), email)
    c.drawString(77,  ry(421.6), telefono)

    # ── Datos del estudiante ──
    c.drawString(120, ry(458.8), nombre)
    c.drawString(119, ry(479.7), num_doc)
    c.drawString(390, ry(479.7), f"{fn_day}/{fn_month}/{fn_year}")
    c.drawString(357, ry(500.7), estado_civil)

    # Sexo
    if sexo in ("mujer", "female", "f", "woman"):
        c.drawString(119, ry(509.8), "X")   # columna Mujer
    else:
        c.drawString(64,  ry(509.8), "X")   # columna Hombre

    c.drawString(418, ry(519.0), "el mismo")

    # ── Cuestionario de salud ──
    c.drawString(277, ry(580.9), peso)
    c.drawString(456, ry(580.9), altura)

    c.setFont("Helvetica-Bold", 9)
    if q1.lower() in ("sí", "si", "s", "yes", "y"):
        c.drawString(34, ry(746.6), "X")   # columna SÍ
    else:
        c.drawString(64, ry(746.6), "X")   # columna NO

    detalle = data.get("q1_detalle", "")
    if detalle:
        c.setFont("Helvetica", 7)
        c.drawString(179, ry(763.0), detalle[:70])

    c.save()
    packet.seek(0)

    overlay  = PdfReader(packet)
    original = PdfReader(NUEVA_MUTUA_TPL)
    writer   = PdfWriter()
    for i, orig_page in enumerate(original.pages):
        if i == 0:
            orig_page.merge_page(overlay.pages[0])
        writer.add_page(orig_page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


# ── ENDPOINTS ──────────────────────────────────────────────────────────────────

@app.route("/fill-pdf", methods=["POST"])
def fill_pdf():
    try:
        data     = request.json or {}
        producto = (data.get("producto", "") or "").upper().replace(" ", "_")

        if "SANITAS" in producto:
            if not os.path.exists(SANITAS_TPL):
                return jsonify({"error": f"Template no encontrado: {SANITAS_TPL}"}), 500
            pdf_bytes = fill_sanitas(data)
            filename  = f"solicitud_sanitas_{_safe_name(data)}.pdf"

        elif "NUEVA_MUTUA" in producto or "NUEVAMUTUA" in producto:
            if not os.path.exists(NUEVA_MUTUA_TPL):
                return jsonify({"error": f"Template no encontrado: {NUEVA_MUTUA_TPL}"}), 500
            pdf_bytes = fill_nueva_mutua(data)
            filename  = f"solicitud_nuevamutua_{_safe_name(data)}.pdf"

        else:
            return jsonify({"error": f"Producto desconocido: '{data.get('producto')}'. Usa SANITAS o NUEVA_MUTUA"}), 400

        return jsonify({
            "success":    True,
            "pdf_base64": base64.b64encode(pdf_bytes).decode(),
            "filename":   filename,
            "producto":   producto,
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "templates": {
            "sanitas":      os.path.exists(SANITAS_TPL),
            "nueva_mutua":  os.path.exists(NUEVA_MUTUA_TPL),
        },
        "template_paths": {
            "sanitas":      SANITAS_TPL,
            "nueva_mutua":  NUEVA_MUTUA_TPL,
        }
    })


def _safe_name(data):
    return (data.get("nombre", "cliente") or "cliente").replace(" ", "_")[:30]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"AlumnusCare PDF Server v2 en http://0.0.0.0:{port}")
    print(f"  Sanitas template:    {'OK' if os.path.exists(SANITAS_TPL) else 'NO ENCONTRADO'} ({SANITAS_TPL})")
    print(f"  Nueva Mutua template: {'OK' if os.path.exists(NUEVA_MUTUA_TPL) else 'NO ENCONTRADO'} ({NUEVA_MUTUA_TPL})")
    app.run(host="0.0.0.0", port=port, debug=False)

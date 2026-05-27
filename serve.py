"""
AlumnusCare PDF Fill Server
Corre en Render (puerto 8000)
n8n llama: POST https://pdf-solicitudes.onrender.com/fill-pdf
"""
from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
import fitz  # PyMuPDF
import io, base64, os, traceback, datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANITAS_TPL     = os.path.join(BASE_DIR, "SS_castellano_editable_25.pdf")
NUEVA_MUTUA_TPL = os.path.join(BASE_DIR, "SOLICITUDESTUDIANTES-TOMADOR_2025_v2.pdf")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def parse_fecha_inicio(s):
    """'15/05/2026' → (day='15', month='05', year='2026')"""
    parts = (s or "01/01/2026").split("/")
    return parts[0].zfill(2), parts[1].zfill(2), parts[2]

def parse_fecha_nac(s):
    """'1981-10-03' → (day='03', month='10', year='1981')"""
    parts = (s or "1990-01-01").split("-")
    return parts[2].zfill(2), parts[1].zfill(2), parts[0]

def next_first_of_month(day, month, year):
    """Si el dia no es 01, avanza al primer día del mes siguiente"""
    if day != "01":
        m, y = int(month), int(year)
        m = m + 1
        if m > 12:
            m, y = 1, y + 1
        return "01", str(m).zfill(2), str(y)
    return day, month, year

def provincia_from_municipio(municipio):
    MAP = {
        "madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia",
        "sevilla": "Sevilla", "zaragoza": "Zaragoza", "málaga": "Málaga",
        "malaga": "Málaga", "bilbao": "Vizcaya", "alicante": "Alicante",
        "córdoba": "Córdoba", "cordoba": "Córdoba", "valladolid": "Valladolid",
    }
    return MAP.get(municipio.strip().lower(), "")

# ─────────────────────────────────────────────
# SANITAS (PDF editable con pypdf + post-proceso con PyMuPDF)
# ─────────────────────────────────────────────
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
    q1        = (data.get("q1", "No") or "No").lower()
    q2        = (data.get("q2", "No") or "No").lower()
    q3        = (data.get("q3", "No") or "No").lower()
    q4        = (data.get("q4", "No") or "No").lower()
    provincia = provincia_from_municipio(municipio)
    nacionalidad = data.get("nacionalidad", "")

    today = datetime.date.today()

    # ── Mapeo de campos pypdf ──
    fv = {
        # Solicitud tipo
        "Nueva póliza": "/On",
        # Mediador
        "Corredor": "/On",
        "codigo mediador": "30149",
        "mediador": "Rose & Pagés S.L.",
        "Anual": "/On",
        "El Mediador": "/On",
        # Tomador
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
        # RGPD page 3
        "Sí": "/On",
        # Cuestionario asegurado 1 (page 4)
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
        # Q2 (¿padece enfermedad?)
        **( {"No_310": "/On"} if q1 in ("no", "n") else {} ),
        # Q3 (¿hospitalizado?)
        **( {"No_430": "/On"} if q2 in ("no", "n") else {"Sí_730": "/On"} ),
        # Q4 (¿tratamiento?)
        **( {"No_530": "/On"} if q3 in ("no", "n") else {"Sí_830": "/On"} ),
        # Q5 (¿prueba médica?)
        **( {"No_630": "/On"} if q4 in ("no", "n") else {"Sí_930": "/On"} ),
        # Q6 (¿síntoma?) → siempre No
        "No_6301": "/On",
    }

    # Tipo documento
    doc_map = {
        "Pasaporte": ["Pasaporte", "Pasaporte_211"],
        "NIE":       ["NIE",       "NIE_210"],
        "NIF":       ["NIF",       "NIF_210"],
    }
    for f in doc_map.get(tipo_doc, doc_map["Pasaporte"]):
        fv[f] = "/On"

    # Sexo
    if sexo in ("mujer", "female", "f", "woman"):
        fv["Mujer"] = "/On"
        fv["Mujer_210"] = "/On"
    else:
        fv["Hombre"] = "/On"
        fv["Hombre_210"] = "/On"

    # ── Paso 1: rellenar campos con pypdf ──
    reader = PdfReader(SANITAS_TPL)
    writer = PdfWriter()
    writer.append(reader)

    for page_idx in [0, 2, 3]:
        writer.update_page_form_field_values(
            writer.pages[page_idx], fv, auto_regenerate=False
        )

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    # ── Paso 2: post-proceso con PyMuPDF ──
    # 2a. Checkbox "No" de ¿Ex-Sanitas? (campo mal nombrado en template)
    # 2b. Email en página 4 (campo no existe en template)
    doc_fitz = fitz.open(stream=buf.read(), filetype="pdf")

    # Buscar página 4 (índice 3) del cuestionario
    cuestionario_page = doc_fitz[3]

    # 2a. Eliminar widget "N de póliza anterior15" (x≈269) y dibujar ■ negro
    for w in cuestionario_page.widgets():
        if w.field_name == "N de póliza anterior15" and abs(w.rect.x0 - 269) < 2:
            no_rect = fitz.Rect(w.rect)
            cuestionario_page.delete_widget(w)
            # Dibujar cuadrado negro del mismo tamaño que los demás checkboxes
            inner = fitz.Rect(
                no_rect.x0 + 1, no_rect.y0 + 1,
                no_rect.x1 - 1, no_rect.y1 - 1
            )
            shape = cuestionario_page.new_shape()
            shape.draw_rect(inner)
            shape.finish(fill=(0, 0, 0), color=(0, 0, 0), width=0)
            shape.commit()
            break

    # 2b. Insertar email (el campo no existe en el template de Sanitas)
    if email:
        cuestionario_page.insert_text(
            fitz.Point(50, 255.4),
            email,
            fontsize=8,
            color=(0, 0, 0)
        )

    out_buf = io.BytesIO()
    doc_fitz.save(out_buf)
    doc_fitz.close()
    out_buf.seek(0)
    return out_buf.read()

# ─────────────────────────────────────────────
# NUEVA MUTUA (PDF plano, overlay ReportLab)
# ─────────────────────────────────────────────
def fill_nueva_mutua(data):
    PAGE_W, PAGE_H = 595.32, 841.92

    fi_day, fi_month, fi_year = parse_fecha_inicio(data.get("fecha_inicio", "01/01/2026"))
    fn_day, fn_month, fn_year = parse_fecha_nac(data.get("fecha_nac", "1990-01-01"))

    nombre       = data.get("nombre", "")
    num_doc      = data.get("num_doc", "")
    sexo         = (data.get("sexo", "") or "").lower()
    email        = data.get("email", "")
    telefono     = data.get("telefono", "")
    direccion    = data.get("direccion", "")
    numero       = data.get("numero", "")
    cp           = data.get("cp", "")
    municipio    = data.get("municipio", "")
    peso         = str(data.get("peso", ""))
    altura       = str(data.get("altura", ""))
    q1           = (data.get("q1", "No") or "No").strip()
    estado_civil = data.get("estado_civil", "")
    provincia    = provincia_from_municipio(municipio)

    full_addr = f"{direccion}, {numero}" if numero else direccion

    def ry(plumber_bottom):
        return PAGE_H - plumber_bottom + 1

    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 8)

    # ── FECHA ALTA DESEADA ──
    c.drawString(124, ry(147.6), fi_day)
    c.drawString(140, ry(147.6), fi_month)
    c.drawString(160, ry(147.6), fi_year)

    # ── SECCIÓN TOMADOR ──
    c.drawString(120, ry(186.6), nombre)
    c.drawString(73,  ry(200.6), num_doc)
    c.drawString(40,  ry(228),   full_addr)
    c.drawString(82,  ry(242.9), municipio)
    c.drawString(318, ry(242.9), provincia)
    c.drawString(97,  ry(257.4), cp)
    c.drawString(358, ry(257.4), email)
    c.drawString(340, ry(271.6), telefono)

    # ── DIRECCIÓN PRESTACIÓN DEL SERVICIO ──
    c.drawString(40,  ry(360),   full_addr)
    c.drawString(82,  ry(382.7), municipio)
    c.drawString(318, ry(382.7), provincia)
    c.drawString(97,  ry(398.1), cp)
    c.drawString(358, ry(398.1), email)
    c.drawString(77,  ry(421.6), telefono)

    # ── DATOS DEL ESTUDIANTE ──
    c.drawString(120, ry(458.8), nombre)
    c.drawString(119, ry(479.7), num_doc)
    c.drawString(390, ry(479.7), f"{fn_day}/{fn_month}/{fn_year}")
    c.drawString(357, ry(500.7), estado_civil)

    if sexo in ("mujer", "female", "f", "woman"):
        c.drawString(119, ry(509.8), "X")
    else:
        c.drawString(64,  ry(509.8), "X")

    c.drawString(418, ry(519.0), "el mismo")

    # ── CUESTIONARIO DE SALUD ──
    c.drawString(277, ry(580.9), peso)
    c.drawString(456, ry(580.9), altura)

    if q1.lower() in ("sí", "si", "s", "yes", "y"):
        c.setFont("Helvetica-Bold", 9)
        c.drawString(34, ry(746.6), "X")
    else:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(64, ry(746.6), "X")

    detalle = data.get("q1_detalle", "")
    if detalle:
        c.setFont("Helvetica", 7)
        c.drawString(179, ry(763.0), detalle[:70])

    c.save()

    # Fusionar overlay con original
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

# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────
@app.route("/fill-pdf", methods=["POST"])
def fill_pdf():
    try:
        data     = request.json or {}
        producto = (data.get("producto", "") or "").upper()

        if "SANITAS" in producto:
            pdf_bytes = fill_sanitas(data)
            filename  = f"solicitud_sanitas_{nombre_safe(data)}.pdf"
        elif "NUEVA_MUTUA" in producto or "NUEVA MUTUA" in producto:
            pdf_bytes = fill_nueva_mutua(data)
            filename  = f"solicitud_nuevamutua_{nombre_safe(data)}.pdf"
        else:
            return jsonify({"error": f"Producto desconocido: {producto}"}), 400

        return jsonify({
            "success":    True,
            "pdf_base64": base64.b64encode(pdf_bytes).decode(),
            "filename":   filename,
            "producto":   producto,
        })
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

def nombre_safe(data):
    return (data.get("nombre", "cliente") or "cliente").replace(" ", "_")[:30]

@app.route("/health", methods=["GET"])
def health():
    templates_ok = {
        "sanitas":     os.path.exists(SANITAS_TPL),
        "nueva_mutua": os.path.exists(NUEVA_MUTUA_TPL),
    }
    return jsonify({"status": "ok", "templates": templates_ok})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"AlumnusCare PDF Server arrancando en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

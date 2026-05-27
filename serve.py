"""
AlumnusCare PDF Fill Server — v4
Usa templates pre-rellenados con campos fijos.
Solo escribe los campos variables del asegurado.
"""
from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
import io, base64, os, traceback, datetime, subprocess, tempfile

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SANITAS_TPL     = os.path.join(BASE_DIR, "test_sanitas_ fijo.pdf")
NUEVA_MUTUA_TPL = os.path.join(BASE_DIR, "nueva_mutua.pdf")

# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_nac(s):
    """YYYY-MM-DD → (dd, mm, yyyy)"""
    p = (s or "1990-01-01").split("-")
    if len(p) == 3:
        return p[2].zfill(2), p[1].zfill(2), p[0]
    return "01", "01", "1990"

def parse_inicio(s):
    """DD/MM/YYYY → (01, mm, yyyy) — siempre primer día del mes"""
    p = (s or "01/01/2026").split("/")
    if len(p) == 3:
        return "01", p[1].zfill(2), p[2]
    return "01", "01", "2026"

NAC_MAP = {
    "españa": "Española", "española": "Española", "espanol": "Española", "español": "Española",
    "colombia": "Colombiana", "colombiana": "Colombiana", "colombiano": "Colombiana",
    "venezuela": "Venezolana", "venezolana": "Venezolana", "venezolano": "Venezolana",
    "mexico": "Mexicana", "méxico": "Mexicana", "mexicana": "Mexicana", "mexicano": "Mexicana",
    "peru": "Peruana", "perú": "Peruana", "peruana": "Peruana", "peruano": "Peruana",
    "argentina": "Argentina", "argentino": "Argentina", "argentino/a": "Argentina",
    "chile": "Chilena", "chilena": "Chilena", "chileno": "Chilena",
    "ecuador": "Ecuatoriana", "ecuatoriana": "Ecuatoriana", "ecuatoriano": "Ecuatoriana",
    "bolivia": "Boliviana", "boliviana": "Boliviana", "boliviano": "Boliviana",
    "brasil": "Brasileña", "brazil": "Brasileña", "brasileña": "Brasileña",
    "china": "China", "chino": "China", "china": "China",
    "india": "India", "indio": "India",
    "eeuu": "Estadounidense", "usa": "Estadounidense", "estados unidos": "Estadounidense",
    "marruecos": "Marroquí", "marroqui": "Marroquí", "marroquí": "Marroquí",
    "ucrania": "Ucraniana", "ucraniana": "Ucraniana",
    "rusia": "Rusa", "ruso": "Rusa", "rusa": "Rusa",
    "italia": "Italiana", "italiana": "Italiana", "italiano": "Italiana",
    "francia": "Francesa", "francesa": "Francesa", "francés": "Francesa",
    "alemania": "Alemana", "alemana": "Alemana", "alemán": "Alemana",
    "reino unido": "Británica", "uk": "Británica",
    "nigeria": "Nigeriana", "nigeriana": "Nigeriana",
    "senegal": "Senegalesa", "senegalesa": "Senegalesa",
    "honduras": "Hondureña", "hondureña": "Hondureña",
    "guatemala": "Guatemalteca", "guatemalteca": "Guatemalteca",
    "cuba": "Cubana", "cubana": "Cubana", "cubano": "Cubana",
    "dominicana": "Dominicana", "república dominicana": "Dominicana",
    "paraguay": "Paraguaya", "paraguaya": "Paraguaya",
    "uruguay": "Uruguaya", "uruguaya": "Uruguaya",
    "panama": "Panameña", "panamá": "Panameña",
    "costa rica": "Costarricense",
    "el salvador": "Salvadoreña", "salvadoreña": "Salvadoreña",
    "nicaragua": "Nicaragüense",
}

def normalizar_nac(n):
    return NAC_MAP.get((n or "").strip().lower(), (n or "").capitalize())

PROVINCIA_MAP = {
    "madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia",
    "sevilla": "Sevilla", "zaragoza": "Zaragoza", "málaga": "Málaga",
    "malaga": "Málaga", "bilbao": "Vizcaya", "alicante": "Alicante",
    "granada": "Granada", "murcia": "Murcia", "valladolid": "Valladolid",
    "palma": "Islas Baleares", "las palmas": "Las Palmas",
    "santa cruz de tenerife": "Santa Cruz de Tenerife",
    "córdoba": "Córdoba", "cordoba": "Córdoba",
}

def get_provincia(municipio):
    return PROVINCIA_MAP.get((municipio or "").strip().lower(), "")


# ── SANITAS ───────────────────────────────────────────────────────────────────

def fill_sanitas(data):
    fn_d, fn_m, fn_y = parse_nac(data.get("fecha_nac", ""))
    fi_d, fi_m, fi_y = parse_inicio(data.get("fecha_inicio", ""))
    today = datetime.date.today()

    nombre       = data.get("nombre", "")
    num_doc      = data.get("num_doc", "")
    tipo_doc     = data.get("tipo_doc", "Pasaporte")
    sexo         = (data.get("sexo", "") or "").lower()
    email        = data.get("email", "")
    telefono     = data.get("telefono", "")
    direccion    = data.get("direccion", "") or "Calle Hermosilla 80"
    numero       = data.get("numero", "") or "2"
    cp           = data.get("cp", "")
    municipio    = data.get("municipio", "")
    nacionalidad = normalizar_nac(data.get("nacionalidad", ""))
    provincia    = get_provincia(municipio)
    peso         = str(data.get("peso", ""))
    altura       = str(data.get("altura", ""))
    q1 = (data.get("q1", "No") or "No").strip().lower()
    q2 = (data.get("q2", "No") or "No").strip().lower()
    q3 = (data.get("q3", "No") or "No").strip().lower()
    q4 = (data.get("q4", "No") or "No").strip().lower()

    # Solo campos variables — el template ya tiene todo lo fijo
    fv = {
        # Página 1 — tomador
        "nombre tomador":      nombre,
        "numero documento":    num_doc,
        "email":               email,
        "movil1":              telefono,
        "domicilio tomador":   direccion,
        "domicilio tomador n": numero,
        "municipio tomador":   municipio,
        "cp tomador":          cp,
        "provincia tomador":   provincia,
        "nacionalidad":        nacionalidad,
        "dia2":                fn_d,
        "mes2":                fn_m,
        "año2":                fn_y,
        "mes1":                fi_m,
        "año1":                fi_y,
        # Página 4 — cuestionario
        "nombre asegurado pag310": nombre,
        "num doc10":               num_doc,
        "movil1 pag310":           telefono,
        "mes_610":                 fi_m,
        "año_610":                 fi_y,
        "día_410":                 fn_d,
        "mes_510":                 fn_m,
        "año_510":                 fn_y,
        "peso10":                  peso,
        "estatura10":              altura,
        "nacionalidado210":        nacionalidad,
        # Preguntas salud
        **( {"No_310": "/On"} if q1 in ("no","n") else {"Sí_630": "/On"} ),
        **( {"No_430": "/On"} if q2 in ("no","n") else {"Sí_730": "/On"} ),
        **( {"No_530": "/On"} if q3 in ("no","n") else {"Sí_830": "/On"} ),
        **( {"No_630": "/On"} if q4 in ("no","n") else {"Sí_930": "/On"} ),
        # Fecha firma
        "día_730": str(today.day).zfill(2),
        "mes_730": str(today.month).zfill(2),
        "año_730": str(today.year),
    }

    # Tipo documento
    doc_map = {
        "Pasaporte": ["Pasaporte", "Pasaporte_211"],
        "NIE":       ["NIE", "NIE_210"],
        "NIF":       ["NIF", "NIF_210"],
    }
    for f in doc_map.get(tipo_doc, doc_map["Pasaporte"]):
        fv[f] = "/On"

    # Sexo
    if sexo in ("mujer", "female", "f", "woman"):
        fv["Mujer"] = "/On"; fv["Mujer_210"] = "/On"
    else:
        fv["Hombre"] = "/On"; fv["Hombre_210"] = "/On"

    reader = PdfReader(SANITAS_TPL)
    writer = PdfWriter()
    writer.append(reader)

    for page_idx in [0, 2, 3]:
        writer.update_page_form_field_values(
            writer.pages[page_idx], fv, auto_regenerate=False
        )

    # Escribir PDF temporal
    tmp_in  = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp_out = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    try:
        writer.write(tmp_in)
        tmp_in.close()
        tmp_out.close()
        # qpdf --generate-appearances hace visibles los campos sin aplanar
        subprocess.run(
            ['qpdf', '--generate-appearances', tmp_in.name, tmp_out.name],
            check=True, capture_output=True
        )
        with open(tmp_out.name, 'rb') as f:
            return f.read()
    except Exception:
        # Si qpdf falla, devolver el PDF sin procesar
        tmp_in_path = tmp_in.name
        with open(tmp_in_path, 'rb') as f:
            return f.read()
    finally:
        for p in [tmp_in.name, tmp_out.name]:
            try: os.unlink(p)
            except: pass


# ── NUEVA MUTUA ───────────────────────────────────────────────────────────────

def fill_nueva_mutua(data):
    from reportlab.pdfgen import canvas as rl_canvas
    PAGE_W, PAGE_H = 595.32, 841.92

    fn_d, fn_m, fn_y = parse_nac(data.get("fecha_nac", ""))
    fi_d, fi_m, fi_y = parse_inicio(data.get("fecha_inicio", ""))

    nombre      = data.get("nombre", "")
    num_doc     = data.get("num_doc", "")
    sexo        = (data.get("sexo", "") or "").lower()
    email       = data.get("email", "")
    telefono    = data.get("telefono", "")
    direccion   = data.get("direccion", "") or "Calle Hermosilla 80"
    numero      = data.get("numero", "") or "2"
    cp          = data.get("cp", "")
    municipio   = data.get("municipio", "")
    peso        = str(data.get("peso", ""))
    altura      = str(data.get("altura", ""))
    q1          = (data.get("q1", "No") or "No").strip()
    estado_civil = data.get("estado_civil", "")
    provincia   = get_provincia(municipio)
    full_addr   = f"{direccion}, {numero}".rstrip(", ") if numero else direccion

    def ry(y): return PAGE_H - y + 1

    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 8)

    c.drawString(124, ry(147.6), fi_d)
    c.drawString(140, ry(147.6), fi_m)
    c.drawString(160, ry(147.6), fi_y)
    c.drawString(120, ry(186.6), nombre)
    c.drawString(73,  ry(200.6), num_doc)
    c.drawString(40,  ry(228),   full_addr)
    c.drawString(82,  ry(242.9), municipio)
    c.drawString(318, ry(242.9), provincia)
    c.drawString(97,  ry(257.4), cp)
    c.drawString(358, ry(257.4), email)
    c.drawString(340, ry(271.6), telefono)
    c.drawString(40,  ry(360),   full_addr)
    c.drawString(82,  ry(382.7), municipio)
    c.drawString(318, ry(382.7), provincia)
    c.drawString(97,  ry(398.1), cp)
    c.drawString(358, ry(398.1), email)
    c.drawString(77,  ry(421.6), telefono)
    c.drawString(120, ry(458.8), nombre)
    c.drawString(119, ry(479.7), num_doc)
    c.drawString(390, ry(479.7), f"{fn_d}/{fn_m}/{fn_y}")
    c.drawString(357, ry(500.7), estado_civil)
    if sexo in ("mujer","female","f","woman"):
        c.drawString(119, ry(509.8), "X")
    else:
        c.drawString(64,  ry(509.8), "X")
    c.drawString(418, ry(519.0), "el mismo")
    c.drawString(277, ry(580.9), peso)
    c.drawString(456, ry(580.9), altura)
    c.setFont("Helvetica-Bold", 9)
    if q1.lower() in ("sí","si","s","yes","y"):
        c.drawString(34, ry(746.6), "X")
    else:
        c.drawString(64, ry(746.6), "X")
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


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

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
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "version": "v4",
        "templates": {
            "sanitas":     os.path.exists(SANITAS_TPL),
            "nueva_mutua": os.path.exists(NUEVA_MUTUA_TPL),
        }
    })


def _safe_name(data):
    return (data.get("nombre", "cliente") or "cliente").replace(" ", "_")[:30]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"AlumnusCare PDF Server v4 en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

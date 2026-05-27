"""
AlumnusCare PDF Fill Server — v5
Usa pdfrw para rellenar y aplanar campos AcroForm correctamente.
Los datos son visibles en cualquier visor PDF.
"""

from flask import Flask, request, jsonify
import io, base64, os, traceback, datetime
import pdfrw

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANITAS_TPL = os.path.join(BASE_DIR, "test_sanitas_ fijo.pdf")

ANNOT_KEY       = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY   = '/V'
ANNOT_RECT_KEY  = '/Rect'
SUBTYPE_KEY     = '/Subtype'
WIDGET_SUBTYPE  = '/Widget'
ANNOT_TYPE_KEY  = '/FT'

def parse_nac(s):
    p = (s or "1990-01-01").split("-")
    if len(p) == 3:
        return p[2].zfill(2), p[1].zfill(2), p[0]
    return "01", "01", "1990"

def parse_inicio(s):
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
    "argentina": "Argentina", "argentino": "Argentina",
    "chile": "Chilena", "chilena": "Chilena", "chileno": "Chilena",
    "ecuador": "Ecuatoriana", "ecuatoriana": "Ecuatoriana", "ecuatoriano": "Ecuatoriana",
    "bolivia": "Boliviana", "boliviana": "Boliviana", "boliviano": "Boliviana",
    "brasil": "Brasileña", "brazil": "Brasileña", "brasileña": "Brasileña",
    "china": "China", "chino": "China",
    "india": "India", "indio": "India",
    "eeuu": "Estadounidense", "usa": "Estadounidense", "estados unidos": "Estadounidense",
    "marruecos": "Marroquí", "marroqui": "Marroquí",
    "ucrania": "Ucraniana", "ucraniana": "Ucraniana",
    "rusia": "Rusa", "ruso": "Rusa", "rusa": "Rusa",
    "italia": "Italiana", "italiana": "Italiana", "italiano": "Italiana",
    "francia": "Francesa", "francesa": "Francesa",
    "alemania": "Alemana", "alemana": "Alemana",
    "reino unido": "Británica", "uk": "Británica",
    "cuba": "Cubana", "cubana": "Cubana", "cubano": "Cubana",
    "dominicana": "Dominicana", "república dominicana": "Dominicana",
}

def normalizar_nac(n):
    return NAC_MAP.get((n or "").strip().lower(), (n or "").capitalize())

PROVINCIA_MAP = {
    "madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia",
    "sevilla": "Sevilla", "zaragoza": "Zaragoza", "málaga": "Málaga",
    "malaga": "Málaga", "bilbao": "Vizcaya", "alicante": "Alicante",
    "granada": "Granada", "murcia": "Murcia", "valladolid": "Valladolid",
    "palma": "Islas Baleares", "las palmas": "Las Palmas",
    "córdoba": "Córdoba", "cordoba": "Córdoba",
}

def get_provincia(municipio):
    return PROVINCIA_MAP.get((municipio or "").strip().lower(), "")


def fill_pdf_pdfrw(template_path, field_values):
    """
    Rellena un PDF AcroForm usando pdfrw y lo aplana para visibilidad máxima.
    field_values: dict { nombre_campo: valor_string }
    Para checkboxes, el valor debe ser '/On' o '/Off'
    """
    template = pdfrw.PdfReader(template_path)
    template.Root.AcroForm.update(
        pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject('true'))
    )

    for page in template.pages:
        annotations = page.get(ANNOT_KEY)
        if not annotations:
            continue
        for annotation in annotations:
            if annotation.get(SUBTYPE_KEY) != WIDGET_SUBTYPE:
                continue
            key = annotation.get(ANNOT_FIELD_KEY)
            if not key:
                continue
            # pdfrw devuelve los nombres con paréntesis: (nombre)
            field_name = key[1:-1] if key.startswith('(') else str(key)
            if field_name in field_values:
                val = field_values[field_name]
                ft = annotation.get(ANNOT_TYPE_KEY)
                if ft == '/Btn':
                    # Checkbox o radio
                    annotation.update(pdfrw.PdfDict(
                        V=pdfrw.PdfName(val.lstrip('/')),
                        AS=pdfrw.PdfName(val.lstrip('/'))
                    ))
                else:
                    # Campo de texto
                    annotation.update(pdfrw.PdfDict(
                        V=val,
                        AP=pdfrw.PdfDict()  # limpiar apariencia para forzar regeneración
                    ))

    out = io.BytesIO()
    pdfrw.PdfWriter().write(out, template)
    out.seek(0)
    return out.read()


def fill_sanitas(data):
    fn_d, fn_m, fn_y = parse_nac(data.get("fecha_nac", ""))
    fi_d, fi_m, fi_y = parse_inicio(data.get("fecha_inicio", ""))
    today = datetime.date.today()

    nombre      = data.get("nombre", "")
    num_doc     = data.get("num_doc", "")
    tipo_doc    = data.get("tipo_doc", "Pasaporte")
    sexo        = (data.get("sexo", "") or "").lower()
    email       = data.get("email", "")
    telefono    = data.get("telefono", "")
    direccion   = data.get("direccion", "") or "Calle Hermosilla 80"
    numero      = data.get("numero", "") or "2"
    cp          = data.get("cp", "")
    municipio   = data.get("municipio", "")
    nacionalidad = normalizar_nac(data.get("nacionalidad", ""))
    provincia   = get_provincia(municipio)
    peso        = str(data.get("peso", ""))
    altura      = str(data.get("altura", ""))

    q1 = (data.get("q1", "No") or "No").strip().lower()
    q2 = (data.get("q2", "No") or "No").strip().lower()
    q3 = (data.get("q3", "No") or "No").strip().lower()
    q4 = (data.get("q4", "No") or "No").strip().lower()

    hoy_d = str(today.day).zfill(2)
    hoy_m = str(today.month).zfill(2)
    hoy_y = str(today.year)

    fv = {
        # Página 1 — tomador
        "nombre tomador":       nombre,
        "numero documento":     num_doc,
        "email":                email,
        "movil1":               telefono,
        "domicilio tomador":    direccion,
        "domicilio tomador n":  numero,
        "municipio tomador":    municipio,
        "cp tomador":           cp,
        "provincia tomador":    provincia,
        "nacionalidad":         nacionalidad,
        "dia2":                 fn_d,
        "mes2":                 fn_m,
        "año2":                 fn_y,
        "mes1":                 fi_m,
        "año1":                 fi_y,
        # Fechas firma
        "dia2 firma":           hoy_d,
        "mes2 firma":           hoy_m,
        "año2 firma":           hoy_y,
        "día_3":                hoy_d,
        "mes_4":                hoy_m,
        "año_4":                hoy_y,
        # Página 4 — cuestionario
        "nombre asegurado pag310": nombre,
        "num doc10":            num_doc,
        "movil1 pag310":        telefono,
        "mes_610":              fi_m,
        "año_610":              fi_y,
        "día_410":              fn_d,
        "mes_510":              fn_m,
        "año_510":              fn_y,
        "peso10":               peso,
        "estatura10":           altura,
        "nacionalidado210":     nacionalidad,
        "parentesco10":         "el mismo",
        # Fecha firma cuestionario
        "día_730":              hoy_d,
        "mes_730":              hoy_m,
        "año_730":              hoy_y,
    }

    # Preguntas salud (checkboxes)
    fv["No_310"]  = "On" if q1 in ("no","n") else "Off"
    fv["Sí_630"]  = "Off" if q1 in ("no","n") else "On"
    fv["No_430"]  = "On" if q2 in ("no","n") else "Off"
    fv["Sí_730"]  = "Off" if q2 in ("no","n") else "On"
    fv["No_530"]  = "On" if q3 in ("no","n") else "Off"
    fv["Sí_830"]  = "Off" if q3 in ("no","n") else "On"
    fv["No_630"]  = "On" if q4 in ("no","n") else "Off"
    fv["Sí_930"]  = "Off" if q4 in ("no","n") else "On"

    # Tipo documento
    doc_map = {
        "Pasaporte": ["Pasaporte", "Pasaporte_211"],
        "NIE":       ["NIE", "NIE_210"],
        "NIF":       ["NIF", "NIF_210"],
    }
    for f in doc_map.get(tipo_doc, doc_map["Pasaporte"]):
        fv[f] = "On"

    # Sexo
    if sexo in ("mujer", "female", "f", "woman"):
        fv["Mujer"] = "On"; fv["Mujer_210"] = "On"
    else:
        fv["Hombre"] = "On"; fv["Hombre_210"] = "On"

    return fill_pdf_pdfrw(SANITAS_TPL, fv)


# ── RUTAS ────────────────────────────────────────────────────────────────────

@app.route("/fill-sanitas", methods=["POST"])
def fill_sanitas_route():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "No JSON recibido"}), 400
        pdf_bytes = fill_sanitas(data)
        return jsonify({"pdf_base64": base64.b64encode(pdf_bytes).decode()})
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "v5-pdfrw"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

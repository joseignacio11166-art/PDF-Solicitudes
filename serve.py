"""
AlumnusCare PDF Fill Server - v11
"""
from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
import io, base64, os, traceback, datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANITAS_TPL = os.path.join(BASE_DIR, "test_sanitas_ fijo.pdf")

NAC_MAP = {
    "espana": "Espanola", "espanol": "Espanola", "espanola": "Espanola",
    "colombia": "Colombiana", "colombiana": "Colombiana", "colombiano": "Colombiana",
    "venezuela": "Venezolana", "venezolana": "Venezolana", "venezolano": "Venezolana",
    "mexico": "Mexicana", "mexicana": "Mexicana", "mexicano": "Mexicana",
    "peru": "Peruana", "peruana": "Peruana", "peruano": "Peruana",
    "argentina": "Argentina", "argentino": "Argentina",
    "chile": "Chilena", "chilena": "Chilena",
    "ecuador": "Ecuatoriana", "ecuatoriana": "Ecuatoriana",
    "bolivia": "Boliviana",
    "brasil": "Brasilena", "brazil": "Brasilena",
    "china": "China", "india": "India",
    "eeuu": "Estadounidense", "usa": "Estadounidense",
    "marruecos": "Marroqui",
    "italia": "Italiana", "francesa": "Francesa", "francia": "Francesa",
    "alemania": "Alemana",
    "reino unido": "Britanica", "uk": "Britanica",
    "cuba": "Cubana", "dominicana": "Dominicana",
    "rusia": "Rusa", "ucrania": "Ucraniana",
    "polonia": "Polaca", "rumania": "Rumana",
    "portugal": "Portuguesa", "grecia": "Griega", "turquia": "Turca",
    "nigeria": "Nigeriana", "ghana": "Ghanesa", "senegal": "Senegalesa",
    "honduras": "Hondurena", "guatemala": "Guatemalteca",
    "nicaragua": "Nicaraguense",
    "el salvador": "Salvadorena", "costa rica": "Costarricense",
    "panama": "Panamena",
    "paraguay": "Paraguaya", "uruguay": "Uruguaya",
}
PROV_MAP = {
    "madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia",
    "sevilla": "Sevilla", "zaragoza": "Zaragoza", "malaga": "Malaga",
    "bilbao": "Vizcaya", "alicante": "Alicante", "granada": "Granada",
    "murcia": "Murcia", "cordoba": "Cordoba", "valladolid": "Valladolid",
    "palma": "Islas Baleares", "las palmas": "Las Palmas",
    "tenerife": "Santa Cruz de Tenerife",
}


def fill_sanitas(data):
    fn_raw = (data.get("fecha_nac", "1990-01-01") or "1990-01-01")
    fn = fn_raw.split("-")
    if len(fn) == 3 and len(fn[0]) == 4:
        fn_d, fn_m, fn_y = fn[2].zfill(2), fn[1].zfill(2), fn[0]
    else:
        fn_d, fn_m, fn_y = "01", "01", "1990"

    fi_raw = (data.get("fecha_inicio", "01/01/2026") or "01/01/2026")
    fi = fi_raw.split("/")
    if len(fi) == 3:
        fi_d, fi_m, fi_y = fi[0].zfill(2), fi[1].zfill(2), fi[2]
    else:
        fi_d, fi_m, fi_y = "01", "01", "2026"

    hoy = datetime.date.today()
    hd = str(hoy.day).zfill(2)
    hm = str(hoy.month).zfill(2)
    hy = str(hoy.year)

    nombre   = data.get("nombre", "")
    num_doc  = data.get("num_doc", "")
    tipo_doc = data.get("tipo_doc", "Pasaporte")
    sexo     = (data.get("sexo", "") or "").lower()
    email    = data.get("email", "")
    tel      = data.get("telefono", "")
    dir_     = data.get("direccion", "")
    num_v    = data.get("numero", "")
    cp       = data.get("cp", "")
    mun      = data.get("municipio", "")
    nac_raw  = (data.get("nacionalidad", "") or "").strip()
    nac      = NAC_MAP.get(nac_raw.lower(), nac_raw.capitalize())
    prov     = PROV_MAP.get((mun or "").lower(), "")
    peso     = str(data.get("peso", "") or "")
    altura   = str(data.get("altura", "") or "")
    q1 = (data.get("q1", "No") or "No").strip().lower()
    q2 = (data.get("q2", "No") or "No").strip().lower()
    q3 = (data.get("q3", "No") or "No").strip().lower()
    q4 = (data.get("q4", "No") or "No").strip().lower()

    fv = {}

    def s(pg, fid, val):
        fv.setdefault(pg, {})[fid] = val

    # Pagina 1
    s(1, "nombre tomador", nombre)
    s(1, "numero documento", num_doc)
    s(1, "dia2", fn_d)
    s(1, "mes2", fn_m)
    s(1, "ano2", fn_y)
    s(1, "nacionalidad", nac)
    s(1, "movil1", tel)
    s(1, "movil2", email)
    s(1, "email", email)
    s(1, "empresa", "")
    s(1, "domicilio tomador", dir_)
    s(1, "domicilio tomador n", num_v)
    s(1, "municipio tomador", mun)
    s(1, "cp tomador", cp)
    s(1, "provincia tomador", prov)
    s(1, "mes1", fi_m)
    s(1, "ano1", fi_y)
    s(1, "dia2 firma", hd)
    s(1, "mes2 firma", hm)
    s(1, "ano2 firma", hy)
    if tipo_doc == "NIE":
        s(1, "NIE", "/On")
    elif tipo_doc == "NIF":
        s(1, "NIF", "/On")
    else:
        s(1, "Pasaporte", "/On")
    if sexo in ("mujer", "f", "female", "woman"):
        s(1, "Mujer", "/On")
    else:
        s(1, "Hombre", "/On")

    # Pagina 3 RGPD
    s(3, "dia_3", hd)
    s(3, "mes_4", hm)
    s(3, "ano_4", hy)

    # Pagina 4 cuestionario
    s(4, "nombre asegurado pag310", nombre)
    s(4, "num doc10", num_doc)
    s(4, "dia_410", fn_d)
    s(4, "mes_510", fn_m)
    s(4, "ano_510", fn_y)
    s(4, "nacionalidado210", nac)
    s(4, "movil1 pag310", tel)
    s(4, "movil2 pag310", email)
    s(4, "mes_610", fi_m)
    s(4, "ano_610", fi_y)
    s(4, "parentesco10", "el mismo")
    s(4, "peso10", peso)
    s(4, "estatura10", altura)
    s(4, "dia_730", hd)
    s(4, "mes_730", hm)
    s(4, "ano_730", hy)
    if tipo_doc == "NIE":
        s(4, "NIE_210", "/On")
    elif tipo_doc == "NIF":
        s(4, "NIF_210", "/On")
    else:
        s(4, "Pasaporte_211", "/On")
    if sexo in ("mujer", "f", "female", "woman"):
        s(4, "Mujer_210", "/On")
    else:
        s(4, "Hombre_210", "/On")

    # Paginas 5-7: nacionalidad y email
    s(5, "nacionalidado210", nac)
    s(5, "movil2 pag310", email)
    s(6, "nacionalidado210", nac)
    s(6, "movil2 pag310", email)
    s(7, "nacionalidado210", nac)
    s(7, "movil2 pag310", email)
    s(8, "nacionalidado210", nac)

    # Preguntas salud q1 y q2 (pagina 4)
    if q1 in ("no", "n"):
        s(4, "No_310", "/On")
    else:
        s(4, "Si_630", "/On")
    if q2 in ("no", "n"):
        s(4, "No_430", "/On")
    else:
        s(4, "Si_730", "/On")

    # Pregunta 5 - casilla fija No en todas las paginas
    s(4, "No_530", "/On")
    s(5, "No_5a30", "/On")
    s(6, "No_53a0", "/On")
    s(7, "No_5s30", "/On")
    s(8, "No_5q30", "/On")

    # Pregunta 6 (q4)
    if q4 in ("no", "n"):
        s(4, "No_630a", "/On")
    else:
        s(4, "Si_930v", "/On")

    reader = PdfReader(SANITAS_TPL)
    writer = PdfWriter(clone_from=reader)
    for page, vals in fv.items():
        writer.update_page_form_field_values(
            writer.pages[page - 1], vals, auto_regenerate=False
        )
    writer.set_need_appearances_writer(True)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


@app.route("/fill-sanitas", methods=["POST"])
def fill_sanitas_route():
    try:
        data = request.get_json(force=True)
        pdf_bytes = fill_sanitas(data)
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        return jsonify({"pdf_base64": pdf_b64})
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

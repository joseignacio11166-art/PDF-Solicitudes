"""
AlumnusCare PDF Fill Server - v13
"""
from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io, base64, os, traceback, datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANITAS_TPL = os.path.join(BASE_DIR, "test_sanitas_ fijo.pdf")
NUEVA_MUTUA_TPL = os.path.join(BASE_DIR, "nueva_mutua.pdf")

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
MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre"
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
    q4 = (data.get("q4", "No") or "No").strip().lower()

    fv = {}
    def s(pg, fid, val): fv.setdefault(pg, {})[fid] = val

    s(1, "nombre tomador", nombre)
    s(1, "numero documento", num_doc)
    s(1, "dia2", fn_d); s(1, "mes2", fn_m); s(1, "año2", fn_y)
    s(1, "nacionalidad", nac)
    s(1, "movil1", tel); s(1, "movil2", tel)
    s(1, "email", email); s(1, "empresa", "")
    s(1, "domicilio tomador", dir_)
    s(1, "domicilio tomador n", num_v)
    s(1, "municipio tomador", mun)
    s(1, "cp tomador", cp)
    s(1, "provincia tomador", prov)
    s(1, "mes1", fi_m); s(1, "año1", fi_y)
    s(1, "dia2 firma", hd); s(1, "mes2 firma", hm); s(1, "año2 firma", hy)
    if tipo_doc == "NIE": s(1, "NIE", "/On")
    elif tipo_doc == "NIF": s(1, "NIF", "/On")
    else: s(1, "Pasaporte", "/On")
    if sexo in ("mujer", "f", "female", "woman"): s(1, "Mujer", "/On")
    else: s(1, "Hombre", "/On")

    s(3, "día_3", hd); s(3, "mes_4", hm); s(3, "año_4", hy)

    s(4, "nombre asegurado pag310", nombre)
    s(4, "num doc10", num_doc)
    s(4, "día_410", fn_d); s(4, "mes_510", fn_m); s(4, "año_510", fn_y)
    s(4, "nacionalidado210", nac)
    s(4, "movil1 pag310", tel); s(4, "movil2 pag310", tel)
    s(4, "Teléfono 2_210", email)
    s(4, "mes_610", fi_m); s(4, "año_610", fi_y)
    s(4, "parentesco10", "el mismo")
    s(4, "peso10", peso); s(4, "estatura10", altura)
    s(4, "día_730", hd); s(4, "mes_730", hm); s(4, "año_730", hy)
    if tipo_doc == "NIE": s(4, "NIE_210", "/On")
    elif tipo_doc == "NIF": s(4, "NIF_210", "/On")
    else: s(4, "Pasaporte_211", "/On")
    if sexo in ("mujer", "f", "female", "woman"): s(4, "Mujer_210", "/On")
    else: s(4, "Hombre_210", "/On")
    if q1 in ("no", "n"): s(4, "No_310", "/On")
    else: s(4, "Sí_610", "/On")
    if q2 in ("no", "n"): s(4, "No_430", "/On")
    else: s(4, "Sí_730", "/On")
    if q4 in ("no", "n"): s(4, "No_630a", "/On")
    else: s(4, "Sí_930v", "/On")

    reader = PdfReader(SANITAS_TPL)
    writer = PdfWriter(clone_from=reader)
    for page, vals in fv.items():
        writer.update_page_form_field_values(writer.pages[page-1], vals, auto_regenerate=False)
    writer.set_need_appearances_writer(True)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def fill_nueva_mutua(data):
    fn_raw = (data.get("fecha_nac", "1990-01-01") or "1990-01-01")
    fn = fn_raw.split("-")
    if len(fn) == 3 and len(fn[0]) == 4:
        fn_d, fn_m, fn_y = fn[2].zfill(2), fn[1].zfill(2), fn[0]
    else:
        fn_d, fn_m, fn_y = "01", "01", "1990"

    fi_raw = (data.get("fecha_inicio", "01/01/2026") or "01/01/2026")
    fi = fi_raw.split("/")
    if len(fi) == 3:
        fi_d, fi_m, fi_y = fi[0].zfill(2), fi[1].zfill(2), fi[2][2:]
    else:
        fi_d, fi_m, fi_y = "01", "01", "26"

    hoy = datetime.date.today()
    hd = str(hoy.day)
    hm_num = str(hoy.month).zfill(2)
    hy = str(hoy.year)
    mes_nombre = MESES[hm_num]

    nombre     = data.get("nombre", "")
    num_doc    = data.get("num_doc", "")
    sexo       = (data.get("sexo", "") or "").lower()
    email      = data.get("email", "")
    tel        = data.get("telefono", "")
    dir_       = data.get("direccion", "")
    num_v      = data.get("numero", "")
    cp         = data.get("cp", "")
    mun        = data.get("municipio", "")
    prov       = data.get("nacionalidad", "")
    peso       = str(data.get("peso", "") or "")
    altura     = str(data.get("altura", "") or "")
    parentesco = data.get("parentesco", "el mismo")

    # Direccion prestacion: extranjero = oficina Hermosilla
    es_espana = any(e in (prov or "").lower() for e in ["espana","españa","madrid","barcelona","valencia","sevilla"]) \
                or (mun or "").lower() in ["madrid","barcelona","valencia","sevilla","bilbao","malaga"]
    if es_espana:
        dir_prest = dir_ + (", " + num_v if num_v else "")
        mun_prest = mun; cp_prest = cp; prov_prest = prov
    else:
        dir_prest = "Calle Hermosilla 80, 2A"
        mun_prest = "Madrid"; cp_prest = "28001"; prov_prest = "Madrid"

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica", 9)

    c.drawString(124.0, 695.3, fi_d)
    c.drawString(140.0, 695.3, fi_m)
    c.drawString(168.0, 695.3, fi_y)
    c.drawString(120.0, 656.3, nombre)
    c.drawString(73.0,  642.3, num_doc)
    c.drawString(40.0,  614.9, dir_ + (", " + num_v if num_v else ""))
    c.drawString(82.0,  600.0, mun)
    c.drawString(318.0, 600.0, prov)
    c.drawString(97.0,  585.5, cp)
    c.drawString(358.0, 585.5, email)
    c.drawString(340.0, 571.3, tel)
    c.drawString(40.0,  482.9, dir_prest)
    c.drawString(82.0,  460.2, mun_prest)
    c.drawString(318.0, 460.2, prov_prest)
    c.drawString(97.0,  444.8, cp_prest)
    c.drawString(358.0, 444.8, email)
    c.drawString(77.0,  421.3, tel)
    c.drawString(120.0, 384.1, nombre)
    c.drawString(119.0, 363.2, num_doc)
    c.drawString(390.0, 363.2, fn_d + "/" + fn_m + "/" + fn_y)
    if sexo in ("mujer", "f", "female", "woman"):
        c.drawString(125.0, 333.1, "X")
    else:
        c.drawString(60.0, 333.1, "X")
    c.drawString(418.0, 323.9, parentesco)
    c.drawString(310.0, 262.0, peso)
    c.drawString(488.0, 262.0, altura)
    c.drawString(87.0,  96.3,  "X")

    c.showPage()
    c.setFont("Helvetica", 9)
    c.drawString(46.0,  155.4, "Madrid")
    c.drawString(152.0, 155.4, hd)
    c.drawString(187.0, 155.4, mes_nombre)
    c.drawString(286.0, 155.4, hy)
    c.save()

    packet.seek(0)
    overlay = PdfReader(packet)
    template = PdfReader(NUEVA_MUTUA_TPL)
    writer = PdfWriter()
    p1 = template.pages[0]
    p1.merge_page(overlay.pages[0])
    writer.add_page(p1)
    p2 = template.pages[1]
    p2.merge_page(overlay.pages[1])
    writer.add_page(p2)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


@app.route("/fill-sanitas", methods=["POST"])
def fill_sanitas_route():
    try:
        data = request.get_json(force=True)
        return jsonify({"pdf_base64": base64.b64encode(fill_sanitas(data)).decode()})
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500


@app.route("/fill-nueva-mutua", methods=["POST"])
def fill_nueva_mutua_route():
    try:
        data = request.get_json(force=True)
        return jsonify({"pdf_base64": base64.b64encode(fill_nueva_mutua(data)).decode()})
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

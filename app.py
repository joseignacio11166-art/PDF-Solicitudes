"""
app.py — AlumnusCare · Centro de Operaciones.

Tres secciones en el menú lateral:
  📄 Solicitudes  -> Adjuntar formulario (cotización PDF) o Rellenar a mano.
  📊 Leads        -> tabla de leads del cotizador (datos de ejemplo por ahora).
  💬 WhatsApp     -> bandeja de conversaciones con resumen + estado (ejemplo).

Las secciones Leads y WhatsApp van con datos de EJEMPLO; se conectarán a las APIs
reales (cotizador / n8n) más adelante sin rehacer la estructura.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from config import BASE_DIR, GENERALI, NUEVA_MUTUA, SANITAS, OFICINA
from core.leer_cotizacion import leer_cotizacion
from core.generar_generali import generar_generali

ASISA = "ASISA"
LOGO = str(BASE_DIR / "assets" / "alumnuscare_logo.png")

st.set_page_config(page_title="AlumnusCare · Centro de Operaciones", page_icon=LOGO, layout="wide")

NOMBRE_ASEGURADORA = {
    SANITAS: "Sanitas (PDF)",
    NUEVA_MUTUA: "Nueva Mutua (PDF)",
    GENERALI: "AlumnusCare / Generali (correo)",
    ASISA: "ASISA (próximamente)",
}

# --- Estilo (azul AlumnusCare) ------------------------------------------
st.markdown(
    """
    <style>
      h1, h2, h3 { color: #1F3148; }
      div[data-testid="stHeadingWithActionElements"] h2 {
          border-left: 5px solid #1CA0D4; padding-left: 12px;
      }
      .stButton > button, .stDownloadButton > button {
          background: #1CA0D4; color: white; border: none;
          border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem;
      }
      .stButton > button:hover, .stDownloadButton > button:hover {
          background: #1689B8; color: white;
      }
      div[data-testid="stExpander"] { border: 1px solid #CFE7F3; border-radius: 10px; }
      section[data-testid="stSidebar"] { background: #F4FAFD; }
      .badge { padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
      .b-rojo { background:#FDE7E7; color:#C0392B; }
      .b-azul { background:#E4F1FB; color:#2470A8; }
      .b-verde { background:#E3F6E8; color:#268C4B; }
      .b-naranja { background:#FDEFD9; color:#B9770E; }
      .b-gris { background:#ECEFF3; color:#5A6B82; }
      .wa-card { border:1px solid #E2E8F0; border-radius:10px; padding:12px 16px; margin-bottom:10px; background:white; }
      .wa-resumen { color:#1F3148; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _badge(texto: str, clase: str) -> str:
    return f"<span class='badge {clase}'>{texto}</span>"


def _guardar_temporal(archivo) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(archivo.getbuffer())
    tmp.close()
    return Path(tmp.name)


def _texto_pdf(ruta) -> str:
    """Texto del PDF: el del contenido + los valores de los campos de formulario (si los hay)."""
    import pdfplumber
    from pypdf import PdfReader
    partes = []
    try:
        with pdfplumber.open(ruta) as pdf:
            partes.append("\n".join((p.extract_text() or "") for p in pdf.pages))
    except Exception:
        pass
    try:
        campos = PdfReader(ruta).get_fields() or {}
        vals = [f"{k}: {v.get('/V')}" for k, v in campos.items() if v.get("/V")]
        if vals:
            partes.append("CAMPOS DEL FORMULARIO:\n" + "\n".join(str(x) for x in vals))
    except Exception:
        pass
    return "\n".join(partes)


# --- Acceso por contraseña ----------------------------------------------
_PASSWORD = os.getenv("APP_PASSWORD", "")
if _PASSWORD and not st.session_state.get("_auth_ok"):
    _c = st.columns([1, 2, 1])
    with _c[1]:
        st.image(LOGO, use_container_width=True)
        _pwd = st.text_input("🔒 Contraseña de acceso", type="password",
                             placeholder="Introduce la contraseña para entrar")
        if _pwd:
            if _pwd == _PASSWORD:
                st.session_state["_auth_ok"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

# --- Menú lateral --------------------------------------------------------
with st.sidebar:
    st.image(LOGO, use_container_width=True)
    st.markdown("<p style='text-align:center;color:#5A6B82;margin-top:-6px'>Centro de Operaciones</p>",
                unsafe_allow_html=True)
    st.divider()
    seccion = st.radio(
        "Navegación",
        ["📄 Solicitudes", "📧 Correo", "📊 Leads", "💬 WhatsApp"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Rose & Pagés · AlumnusCare")


# ========================================================================
# SECCIÓN: SOLICITUDES
# ========================================================================
def _validacion_fecha_efecto(datos: dict) -> None:
    """Aviso si la fecha de inicio de póliza no va con ≥2 meses de antelación."""
    from dateutil.relativedelta import relativedelta
    try:
        fe = datetime.strptime(datos.get("fecha_efecto", ""), "%d/%m/%Y").date()
        minimo = date.today() + relativedelta(months=2)
        if fe < minimo:
            st.warning(
                f"⚠️ La **fecha de inicio de la póliza** ({datos['fecha_efecto']}) NO está a 2 meses "
                f"vista (mínimo: {minimo.strftime('%d/%m/%Y')}). Debe empezar con al menos 2 meses "
                "de antelación: revísala."
            )
    except Exception:
        pass


def _guardar_historial(nombre, aseguradora, tipo, filename, datos=None, texto=None, hoy=None) -> None:
    """Guarda la solicitud en el Historial (Firestore). Avisa si no se pudo."""
    try:
        from core.historial import guardar_solicitud
        if guardar_solicitud(nombre, aseguradora, tipo, filename, datos=datos, contenido_texto=texto, hoy=hoy):
            st.caption("🗂️ Guardado en el Historial.")
        else:
            st.caption("⚠️ No se pudo guardar en el Historial (revisa los permisos de Firestore).")
    except Exception:
        pass


def _descarga_sanitas(datos: dict) -> None:
    from core.rellenar_sanitas import rellenar_sanitas
    hoy = date.today()
    res = rellenar_sanitas(datos, hoy=hoy)
    with open(res["ruta"], "rb") as fh:
        pdf_bytes = fh.read()
    if res["parar"]:
        st.error("🛑 El cuestionario tiene algún 'Sí': las casillas de salud se han dejado "
                 "**SIN marcar**. Revísalo y márcalas a mano antes de enviar.")
    st.success("PDF de Sanitas generado: **editable** y **sin firmar** (firma en págs. 1, 3 y 4).")
    st.download_button("⬇️ Descargar PDF de Sanitas", data=pdf_bytes,
                       file_name=res["ruta"].name, mime="application/pdf")
    for a in res["avisos"]:
        st.caption(f"• {a}")
    _guardar_historial(datos.get("nombre_completo", ""), "Sanitas", "pdf", res["ruta"].name, datos=datos, hoy=hoy)


def _descarga_nuevamutua(datos: dict, firma_png: bytes | None = None) -> None:
    from core.rellenar_nuevamutua import rellenar_nuevamutua
    hoy = date.today()
    res = rellenar_nuevamutua(datos, hoy=hoy, firma_png=firma_png)
    with open(res["ruta"], "rb") as fh:
        pdf_bytes = fh.read()
    if res["parar"]:
        st.error("🛑 El cuestionario tiene algún 'Sí': el 'NO' de salud se ha dejado **SIN marcar**. "
                 "Revísalo y márcalo a mano antes de enviar.")
    st.success("PDF de Nueva Mutua generado: relleno y **sin firmar** (firma en la última página).")
    st.download_button("⬇️ Descargar PDF de Nueva Mutua", data=pdf_bytes,
                       file_name=res["ruta"].name, mime="application/pdf")
    for a in res["avisos"]:
        st.caption(f"• {a}")
    _guardar_historial(datos.get("nombre_completo", ""), "Nueva Mutua", "pdf", res["ruta"].name, datos=datos, hoy=hoy)


def _descarga_generali(datos: dict, direccion_completa: str) -> None:
    crudos_para_correo = {
        "nombre": datos.get("nombre_completo") or f"{datos.get('nombre','')} {datos.get('apellidos','')}".strip(),
        "fecha_inicio_poliza": datos.get("fecha_efecto", ""),
        "correo": datos.get("correo", ""),
        "telefono_movil": datos.get("telefono_movil", ""),
        "direccion": direccion_completa,
    }
    correo = generar_generali(crudos_para_correo)
    texto = f"ASUNTO:\n{correo['asunto']}\n\nCUERPO:\n{correo['cuerpo']}"
    fname = f"generali_{datos.get('apellidos','').strip() or 'correo'}.txt"
    st.text_input("ASUNTO", correo["asunto"])
    st.text_area("CUERPO", correo["cuerpo"], height=380)
    st.download_button("⬇️ Descargar correo (.txt)", data=texto, file_name=fname)
    st.caption("Recuerda adjuntar: documento de identidad y carta de aceptación de la universidad.")
    _guardar_historial(datos.get("nombre_completo") or f"{datos.get('nombre','')} {datos.get('apellidos','')}".strip(),
                       "Generali", "correo", fname, texto=texto)


def render_adjuntar() -> None:
    """Flujo que ya existía: subir cotización -> cerebro -> revisar -> generar."""
    st.header("1 · Sube la cotización")
    archivo = st.file_uploader("Arrastra aquí el PDF de HiBroker (Pagés)", type=["pdf"])
    if not archivo:
        st.info("Esperando una cotización en PDF para empezar.")
        return

    if st.session_state.get("_archivo") != archivo.name:
        ruta = _guardar_temporal(archivo)
        st.session_state["_archivo"] = archivo.name
        st.session_state["crudos"] = leer_cotizacion(ruta)
        st.session_state.pop("cerebro", None)

    crudos = st.session_state["crudos"]
    detectada = crudos.get("aseguradora_detectada")

    st.header("2 · Aseguradora detectada")
    if detectada:
        st.success(f"Detectada por el producto **{crudos.get('producto')}** → **{NOMBRE_ASEGURADORA[detectada]}**")
    else:
        st.error(f"No reconozco el producto '{crudos.get('producto')}'. Elige la aseguradora a mano.")

    opciones = [SANITAS, NUEVA_MUTUA, GENERALI]
    elegida = st.selectbox("Aseguradora a usar", opciones,
                           index=opciones.index(detectada) if detectada in opciones else 0,
                           format_func=lambda a: NOMBRE_ASEGURADORA[a])
    if detectada and elegida != detectada:
        st.warning(f"⚠️ Ojo: el producto es **{NOMBRE_ASEGURADORA[detectada]}**, pero elegiste **{NOMBRE_ASEGURADORA[elegida]}**.")

    st.header("3 · Revisa lo que se va a poner")
    if st.button("🧠 Analizar con el cerebro (Claude)"):
        with st.spinner("Razonando los datos variables…"):
            from cerebro.prompt_extraccion import extraer_datos
            try:
                d = extraer_datos(crudos)
                d["_direccion_oficina"] = not d.get("direccion_en_espana", True)
                if d["_direccion_oficina"]:
                    d["direccion_via"] = OFICINA["via"]
                    d["direccion_numero"] = OFICINA["numero"]
                    d["direccion_piso"] = OFICINA["piso"]
                    d["direccion_puerta"] = OFICINA["puerta"]
                    d["municipio"] = OFICINA["municipio"]
                    d["provincia"] = OFICINA["provincia"]
                    d["codigo_postal"] = OFICINA["codigo_postal"]
                    d["direccion_en_espana"] = True
                st.session_state["cerebro"] = d
            except Exception as e:  # noqa: BLE001
                st.error(f"Error al analizar: {e}")

    datos = st.session_state.get("cerebro")
    if not datos:
        st.info("Pulsa **Analizar con el cerebro** para proponer los datos.")
        return

    _validacion_fecha_efecto(datos)

    if datos.get("avisos"):
        with st.expander(f"⚠️ {len(datos['avisos'])} aviso(s) para revisar", expanded=True):
            for a in datos["avisos"]:
                st.markdown(f"- {a}")

    salud = datos.get("cuestionario_salud", {})
    if salud.get("tiene_algun_si"):
        st.error("🛑 El cuestionario de salud tiene algún **'Sí'**. En Sanitas/Nueva Mutua **NO se marca "
                 f"automáticamente**: se gestiona a mano.\n\n**Resumen:** {salud.get('resumen_para_formulario','')}")
    else:
        st.success("Cuestionario de salud: todo en **No** (se marcará 'No' automáticamente).")

    st.subheader("Datos propuestos (puedes corregir)")
    col1, col2 = st.columns(2)
    with col1:
        datos["nombre"] = st.text_input("Nombre", datos.get("nombre", ""))
        datos["numero_documento"] = st.text_input("Nº documento", datos.get("numero_documento", ""))
        datos["sexo"] = st.text_input("Sexo", datos.get("sexo", ""))
        datos["fecha_nacimiento"] = st.text_input("Fecha nacimiento", datos.get("fecha_nacimiento", ""))
        datos["telefono_movil"] = st.text_input("Teléfono móvil", datos.get("telefono_movil", ""))
        datos["correo"] = st.text_input("Correo", datos.get("correo", ""))
    with col2:
        datos["apellidos"] = st.text_input("Apellidos", datos.get("apellidos", ""))
        datos["tipo_documento"] = st.text_input("Tipo documento", datos.get("tipo_documento", ""))
        datos["nacionalidad"] = st.text_input("Nacionalidad", datos.get("nacionalidad", ""))
        datos["fecha_efecto"] = st.text_input("Fecha efecto (inicio póliza)", datos.get("fecha_efecto", ""))
        datos["peso_kg"] = st.text_input("Peso (kg)", datos.get("peso_kg", ""))
        datos["altura_cm"] = st.text_input("Altura (cm)", datos.get("altura_cm", ""))
        datos["telefono_fijo"] = st.text_input("Teléfono fijo", datos.get("telefono_fijo", ""))

    st.markdown("**Dirección**")
    if datos.get("_direccion_oficina"):
        st.caption("ℹ️ No había dirección en España → se muestra la de la oficina (puedes editarla).")
    datos["direccion_via"] = st.text_input("Vía (tipo + nombre)", datos.get("direccion_via", ""))
    cnum, cpiso, cpta = st.columns(3)
    datos["direccion_numero"] = cnum.text_input("Número", datos.get("direccion_numero", ""))
    datos["direccion_piso"] = cpiso.text_input("Piso", datos.get("direccion_piso", ""))
    datos["direccion_puerta"] = cpta.text_input("Puerta", datos.get("direccion_puerta", ""))
    cmun, cprov, ccp = st.columns(3)
    datos["municipio"] = cmun.text_input("Municipio / población", datos.get("municipio", ""))
    datos["provincia"] = cprov.text_input("Provincia", datos.get("provincia", ""))
    datos["codigo_postal"] = ccp.text_input("Código postal", datos.get("codigo_postal", ""))

    st.header("4 · Generar")
    if elegida == GENERALI:
        if st.button("✉️ Generar correo de Generali"):
            _descarga_generali(datos, crudos.get("direccion", ""))
    elif elegida == SANITAS:
        if st.button("📄 Generar PDF de Sanitas"):
            _descarga_sanitas(datos)
    else:
        if st.button("📄 Generar PDF de Nueva Mutua"):
            _descarga_nuevamutua(datos)


def render_manual() -> None:
    """Formulario para introducir los datos a mano y generar el PDF/correo."""
    st.header("Rellenar a mano")
    st.caption("Introduce los datos del estudiante, elige la aseguradora y genera el documento. "
               "No usa la IA (no consume API).")

    aseg = st.selectbox("Aseguradora", [SANITAS, NUEVA_MUTUA, GENERALI, ASISA],
                        format_func=lambda a: NOMBRE_ASEGURADORA[a])
    if aseg == ASISA:
        st.info("⏳ **ASISA todavía no está disponible**: falta su plantilla. En cuanto la tengamos, "
                "se genera igual que las demás.")

    c1, c2, c3 = st.columns(3)
    with c1:
        nombre = st.text_input("Nombre")
        tipo_doc = st.selectbox("Tipo de documento", ["Pasaporte", "NIE", "NIF", "DNI"])
        sexo = st.selectbox("Sexo", ["Mujer", "Hombre"])
        f_nac = st.date_input("Fecha de nacimiento", value=date(2005, 1, 1),
                              min_value=date(1940, 1, 1), max_value=date.today())
    with c2:
        apellidos = st.text_input("Apellidos")
        num_doc = st.text_input("Nº de documento")
        nacionalidad = st.text_input("Nacionalidad")
        f_efecto = st.date_input("Fecha de inicio de la póliza", value=date.today(),
                                 min_value=date(2020, 1, 1), max_value=date(2100, 1, 1))
    with c3:
        correo = st.text_input("Correo electrónico")
        telefono = st.text_input("Teléfono móvil")
        peso = st.text_input("Peso (kg)")
        altura = st.text_input("Altura (cm)")

    st.markdown("**Dirección** (en blanco = se usa la de la oficina)")
    d1, d2, d3 = st.columns(3)
    via = d1.text_input("Vía (tipo + nombre)", value=OFICINA["via"])
    numero = d2.text_input("Número", value=OFICINA["numero"])
    piso = d3.text_input("Piso", value=OFICINA["piso"])
    e1, e2, e3, e4 = st.columns(4)
    puerta = e1.text_input("Puerta", value=OFICINA["puerta"])
    municipio = e2.text_input("Municipio", value=OFICINA["municipio"])
    provincia = e3.text_input("Provincia", value=OFICINA["provincia"])
    cp = e4.text_input("Código postal", value=OFICINA["codigo_postal"])

    repat_direccion = repat_poblacion = repat_provincia = repat_cp = ""
    if aseg == NUEVA_MUTUA:
        st.markdown("**Dirección en el extranjero (para repatriación)** — opcional")
        r1, r2 = st.columns([2, 1])
        repat_direccion = r1.text_input("Dirección completa (país de origen)")
        repat_cp = r2.text_input("Código postal (extranjero)")
        r3, r4 = st.columns(2)
        repat_poblacion = r3.text_input("Población (extranjero)")
        repat_provincia = r4.text_input("Provincia / estado (extranjero)")

    st.markdown("**Cuestionario de salud**")
    if aseg == NUEVA_MUTUA:
        sp1, sp2 = st.columns(2)
        p1 = sp1.radio("1. ¿Padece/ha padecido alguna enfermedad de la lista?", ["No", "Sí"], horizontal=True)
        p2 = sp2.radio("2. ¿Pendiente de diagnóstico/seguimiento/tratamiento?", ["No", "Sí"], horizontal=True)
        algun_si = (p1 == "Sí") or (p2 == "Sí")
        detalle = st.text_area("Detalle (si marcaste algún 'Sí')", "") if algun_si else ""
        salud_dict = {"p1": p1, "p2": p2, "tiene_algun_si": algun_si,
                      "resumen_para_formulario": detalle, "detalle_original": detalle}
        if algun_si:
            st.info("Pondré la **X en el 'Sí'** que elegiste. Recuerda escribir el detalle a mano en el PDF.")
    else:
        hay_si = st.checkbox("El estudiante declara algún 'Sí' (enfermedad, hospitalización, tratamiento…)")
        detalle = st.text_area("Detalle (si hay algún 'Sí')", "") if hay_si else ""
        salud_dict = {"tiene_algun_si": hay_si,
                      "resumen_para_formulario": detalle if hay_si else "", "detalle_original": detalle}
        if hay_si:
            st.warning("Con algún 'Sí', el PDF se genera pero las casillas de salud quedan SIN marcar (gestión manual).")

    if st.button("Generar documento", type="primary"):
        if not nombre or not apellidos:
            st.error("Pon al menos nombre y apellidos.")
            return
        datos = {
            "nombre_completo": f"{nombre} {apellidos}".strip(),
            "nombre": nombre, "apellidos": apellidos,
            "tipo_documento": tipo_doc, "numero_documento": num_doc,
            "sexo": sexo, "nacionalidad": nacionalidad,
            "peso_kg": peso, "altura_cm": altura,
            "fecha_nacimiento": f_nac.strftime("%d/%m/%Y"),
            "fecha_efecto": f_efecto.strftime("%d/%m/%Y"),
            "telefono_movil": telefono, "telefono_fijo": "", "correo": correo,
            "direccion_en_espana": True,
            "direccion_via": via, "direccion_numero": numero,
            "direccion_piso": piso, "direccion_puerta": puerta,
            "municipio": municipio, "provincia": provincia, "codigo_postal": cp,
            "repat_direccion": repat_direccion, "repat_poblacion": repat_poblacion,
            "repat_provincia": repat_provincia, "repat_cp": repat_cp,
            "cuestionario_salud": salud_dict,
        }
        _validacion_fecha_efecto(datos)
        if aseg == SANITAS:
            _descarga_sanitas(datos)
        elif aseg == NUEVA_MUTUA:
            _descarga_nuevamutua(datos)
        elif aseg == GENERALI:
            direccion = f"{via} {numero}".strip()
            if piso:
                direccion += f", PISO {piso} {puerta}".rstrip()
            direccion += f", {municipio}, {cp}"
            _descarga_generali(datos, direccion)
        else:
            st.info("ASISA todavía no disponible.")


def render_corregir() -> None:
    """Sube un PDF ya hecho y cambia un dato sin rehacerlo todo."""
    st.header("Corregir un PDF")
    st.caption("Sube una solicitud de Sanitas o Nueva Mutua, revisa/cambia los campos y descárgala "
               "corregida. Los campos vacíos puedes rellenarlos; solo se tocan los que cambies. "
               "Puedes elegir incluir la firma o dejarla en blanco.")
    archivo = st.file_uploader("Sube el PDF a corregir", type=["pdf"], key="corr_up")
    if not archivo:
        return

    from core import corregir as _corr
    if st.session_state.get("corr_file") != archivo.name:
        ruta = _guardar_temporal(archivo)
        st.session_state["corr_file"] = archivo.name
        st.session_state["corr_ruta"] = str(ruta)
        st.session_state["corr_tipo"] = _corr.detectar(str(ruta))
        st.session_state["corr_actuales"] = (
            _corr.leer(str(ruta), st.session_state["corr_tipo"]) if st.session_state["corr_tipo"] else {}
        )

    tipo = st.session_state.get("corr_tipo")
    if not tipo:
        st.error("No reconozco el PDF. Debe ser una solicitud de **Sanitas** o **Nueva Mutua**.")
        return
    actuales = st.session_state["corr_actuales"]
    st.success(f"Detectado: **{tipo.title()}**. Cambia lo que necesites y genera el corregido.")

    nuevos = {}
    cols = st.columns(2)
    for i, (log, val) in enumerate(actuales.items()):
        nuevos[log] = cols[i % 2].text_input(log, val, key="corr_" + log)

    incluir_firma = st.radio(
        "Firma",
        ["Incluir la firma del original", "Sin firma (en blanco)"],
        horizontal=True,
    ).startswith("Incluir")

    if st.button("Generar PDF corregido", type="primary"):
        cambios = {log: v for log, v in nuevos.items() if v != actuales.get(log, "")}
        if not cambios and incluir_firma:
            st.info("No cambiaste ningún dato.")
            return
        pdf = _corr.corregir(st.session_state["corr_ruta"], tipo, cambios, incluir_firma=incluir_firma)
        msg = "✅ PDF corregido."
        if cambios:
            msg += " Cambiado: " + ", ".join(cambios.keys())
        if not incluir_firma:
            msg += " · sin firma"
        st.success(msg)
        st.download_button("⬇️ Descargar PDF corregido", data=pdf,
                           file_name="corregido_" + archivo.name, mime="application/pdf")


def render_solicitudes() -> None:
    st.title("📄 Solicitudes")
    modo = st.radio("Modo", ["📎 Adjuntar formulario", "✍️ Rellenar a mano", "✏️ Corregir un PDF",
                             "🗂️ Historial"], horizontal=True)
    st.divider()
    if modo.startswith("📎"):
        render_adjuntar()
    elif modo.startswith("✍"):
        render_manual()
    elif modo.startswith("✏"):
        render_corregir()
    else:
        render_historial()


# ========================================================================
# SECCIÓN: HISTORIAL
# ========================================================================
def render_historial() -> None:
    st.title("🗂️ Historial de solicitudes")
    from core import historial
    if not historial.disponible():
        st.warning("El historial aún no está disponible: hay que activar **Firestore** en el "
                   "proyecto de Google. (En local no aparece; funciona en el servidor.)")
        return
    try:
        registros = historial.listar_solicitudes()
    except Exception as e:  # noqa: BLE001
        st.error(f"No pude leer el historial: {e}")
        return
    if not registros:
        st.info("Todavía no hay solicitudes guardadas. Genera una en 📄 Solicitudes y aparecerá aquí.")
        return

    ca, cb = st.columns([3, 1])
    ca.caption(f"{len(registros)} solicitud(es) guardada(s).")
    if cb.button("🗑️ Borrar todo"):
        st.session_state["confirmar_borrar_todo"] = True
    if st.session_state.get("confirmar_borrar_todo"):
        st.warning("¿Seguro que quieres borrar **TODAS** las solicitudes del historial?")
        cc1, cc2 = st.columns(2)
        if cc1.button("Sí, borrar todo"):
            n = historial.borrar_todas()
            st.session_state.pop("confirmar_borrar_todo", None)
            st.success(f"Borradas {n} solicitudes.")
            st.rerun()
        if cc2.button("Cancelar"):
            st.session_state.pop("confirmar_borrar_todo", None)
            st.rerun()

    buscar = st.text_input("Buscar por nombre", "")
    for r in registros:
        if buscar and buscar.lower() not in r.get("nombre", "").lower():
            continue
        fecha = r.get("fecha")
        fstr = fecha.strftime("%d/%m/%Y %H:%M") if hasattr(fecha, "strftime") else str(fecha)
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        c1.markdown(f"**{r.get('nombre', '(sin nombre)')}**  \n"
                    f"<span style='color:#5A6B82'>{r.get('aseguradora', '')}</span>", unsafe_allow_html=True)
        c2.markdown(f"<span style='color:#5A6B82'>{fstr}</span>", unsafe_allow_html=True)
        key = r["_id"]
        if r.get("tipo") == "correo":
            c3.download_button("⬇️ Descargar", data=r.get("contenido_texto", ""),
                               file_name=r.get("filename", "correo.txt"), mime="text/plain", key="dl" + key)
        else:
            if c3.button("⬇️ Preparar PDF", key="prep" + key):
                st.session_state["regen_" + key] = True
            if st.session_state.get("regen_" + key):
                try:
                    pdf = historial.regenerar_pdf(r)
                    c3.download_button("Descargar PDF", data=pdf, file_name=r.get("filename", "solicitud.pdf"),
                                       mime="application/pdf", key="dl" + key)
                except Exception as e:  # noqa: BLE001
                    c3.caption(f"Error al regenerar: {e}")
        if c4.button("🗑️", key="del" + key, help="Borrar esta solicitud"):
            historial.borrar_solicitud(key)
            st.rerun()
        st.divider()


# ========================================================================
# SECCIÓN: CORREO (lee Firestore "correos", que vuelca n8n)
# ========================================================================
def render_correo() -> None:
    st.title("📧 Correo")
    st.caption("Solicitudes que llegan al buzón **atencionestudiantes@**. Las vuelca n8n y se ven aquí.")
    from core import correos
    if not correos.disponible():
        st.warning("Aún sin conexión a Firestore.")
        return
    try:
        items = correos.listar_correos()
    except Exception as e:  # noqa: BLE001
        st.error(f"No pude leer los correos: {e}")
        return
    if not items:
        st.info("Todavía no hay correos. Cuando n8n empiece a volcar el buzón, aparecerán aquí. "
                "(La sección está lista y esperando la conexión de n8n.)")
        return

    sol = [i for i in items if i.get("es_solicitud")]
    m1, m2, m3 = st.columns(3)
    m1.metric("Correos", len(items))
    m2.metric("📋 Solicitudes", len(sol))
    m3.metric("✅ Gestionadas", sum(1 for i in items if i.get("estado") == "Gestionado"))
    st.divider()

    filtro = st.radio("Ver", ["Solo solicitudes", "Todos"], horizontal=True)
    for i in items:
        if filtro == "Solo solicitudes" and not i.get("es_solicitud"):
            continue
        estado = i.get("estado", "Nuevo")
        badge = _badge("📋 Solicitud", "b-azul") if i.get("es_solicitud") else _badge("Otro", "b-gris")
        est_badge = _badge("✅ Gestionado", "b-verde") if estado == "Gestionado" else _badge("🟠 Nuevo", "b-naranja")
        resumen = (f"<div class='wa-resumen' style='margin-top:4px'>🧠 {i.get('resumen')}</div>"
                   if i.get("resumen") else "")
        col = st.columns([6, 1])
        col[0].markdown(
            f"""<div class='wa-card'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <b>{i.get('asunto', '(sin asunto)')}</b> {badge} {est_badge}
              </div>
              <div style='color:#5A6B82;margin-top:4px'>{i.get('remitente', '')} · {i.get('fecha', '')}</div>
              {resumen}
            </div>""",
            unsafe_allow_html=True,
        )
        nuevo = "Nuevo" if estado == "Gestionado" else "Gestionado"
        etq = "↩️ Reabrir" if estado == "Gestionado" else "✅ Gestionado"
        if col[1].button(etq, key="cor_" + i["_id"]):
            correos.marcar_estado(i["_id"], nuevo)
            st.rerun()
    st.caption("La detección de solicitudes (por remitente/asunto) la hace n8n; aquí las gestionas.")


# ========================================================================
# SECCIÓN: LEADS (datos de ejemplo)
# ========================================================================
def render_leads() -> None:
    st.title("📊 Leads")
    st.caption("Leads del cotizador. **Datos de ejemplo** — se conectará a la API del cotizador.")

    leads = [
        {"Nombre": "María González", "Provincia": "Madrid", "Fecha": "19/06/2026", "Estado": "Caliente", "Teléfono": "+34 675 29 36 77", "Email": "maria.g@gmail.com"},
        {"Nombre": "José Cruz", "Provincia": "Madrid", "Fecha": "19/06/2026", "Estado": "Caliente", "Teléfono": "+34 675 29 36 77", "Email": "jose.cruz@gmail.com"},
        {"Nombre": "Leyan Ardakani", "Provincia": "Madrid", "Fecha": "18/06/2026", "Estado": "Frío", "Teléfono": "+971 050 558 2131", "Email": "layan.a@gmail.com"},
        {"Nombre": "Camila Restrepo", "Provincia": "Barcelona", "Fecha": "18/06/2026", "Estado": "Caliente", "Teléfono": "+57 300 123 4567", "Email": "camila.r@gmail.com"},
        {"Nombre": "Ahmed Saleh", "Provincia": "Valencia", "Fecha": "17/06/2026", "Estado": "Frío", "Teléfono": "+20 100 555 1234", "Email": "ahmed.s@gmail.com"},
    ]
    cal = sum(1 for l in leads if l["Estado"] == "Caliente")
    m1, m2, m3 = st.columns(3)
    m1.metric("Leads totales", len(leads))
    m2.metric("🔥 Calientes", cal)
    m3.metric("❄️ Fríos", len(leads) - cal)
    st.divider()

    f = st.columns([2, 1, 1])
    buscar = f[0].text_input("Buscar por nombre", "")
    estado_f = f[1].selectbox("Estado", ["Todos", "Caliente", "Frío"])
    filtrados = [l for l in leads
                 if (not buscar or buscar.lower() in l["Nombre"].lower())
                 and (estado_f == "Todos" or l["Estado"] == estado_f)]
    st.dataframe(filtrados, use_container_width=True, hide_index=True)
    st.caption("Próximo paso: enchufar la API del cotizador para que estos leads sean los reales y en vivo.")


# ========================================================================
# SECCIÓN: WHATSAPP (datos de ejemplo)
# ========================================================================
_WA_CONVERS = [
    {"id": "maria", "contacto": "María González", "estado": "Necesita humano",
     "resumen": "Preguntó por la **renovación** de su póliza Sanitas y si sube el precio."},
    {"id": "col1", "contacto": "+34 6XX XX 12 34", "estado": "Bot activo",
     "resumen": "Pide **cotización** para estudiante de Colombia que viene en septiembre."},
    {"id": "ahmed", "contacto": "Ahmed Saleh", "estado": "Necesita humano",
     "resumen": "Duda sobre **documentos** para el visado; quiere saber qué adjuntar."},
    {"id": "camila", "contacto": "Camila Restrepo", "estado": "Resuelto",
     "resumen": "**Contrató** Sanitas Students; se le envió la solicitud para firmar."},
    {"id": "col2", "contacto": "+57 3XX XXX 45 67", "estado": "Bot activo",
     "resumen": "Comparando **precios** entre Sanitas y Nueva Mutua."},
]

_WA_SEEDS = {
    "maria": [("in", "Hola, tengo una póliza con vosotros"),
              ("in", "¿Me podéis decir cuánto sería la renovación?")],
    "col1": [("in", "Hola, quiero un seguro para estudiar en Madrid"),
             ("out", "¡Hola! Claro 😊 ¿De qué país vienes y cuándo llegas?"),
             ("in", "De Colombia, llego en septiembre")],
    "ahmed": [("in", "What documents do I need for the visa?")],
    "camila": [("in", "¿Ya está mi solicitud?"),
               ("out", "¡Sí! Te la acabo de enviar para firmar 📄"),
               ("in", "¡Perfecto, muchas gracias!")],
    "col2": [("in", "¿Cuál es más barato, Sanitas o Nueva Mutua?"),
             ("out", "Depende del plan. ¿Quieres que te pase las dos opciones?")],
}

_WA_ESTILO = {
    "Necesita humano": ("b-naranja", "🟠 Necesita humano"),
    "Bot activo": ("b-verde", "🟢 Bot activo"),
    "Resuelto": ("b-gris", "⚪ Resuelto"),
}


def _wa_html(msgs) -> str:
    import base64
    import html as _html
    filas = ""
    for m in msgs:
        out = m["dir"] == "out"
        side = "flex-end" if out else "flex-start"
        bg = "#DCF8C6" if out else "#FFFFFF"
        if m["tipo"] == "text":
            cuerpo = _html.escape(m["text"]).replace("\n", "<br>")
        elif m["tipo"] == "img":
            b64 = base64.b64encode(m["data"]).decode()
            cuerpo = (f"<img src='data:{m.get('mime', 'image/png')};base64,{b64}' "
                      "style='max-width:220px;border-radius:8px;display:block'>")
        else:  # audio
            b64 = base64.b64encode(m["data"]).decode()
            cuerpo = f"<audio controls src='data:audio/wav;base64,{b64}' style='max-width:240px'></audio>"
        filas += (f"<div style='display:flex;justify-content:{side};margin:5px 0'>"
                  f"<div style='background:{bg};padding:8px 12px;border-radius:10px;max-width:78%;"
                  f"box-shadow:0 1px 1px rgba(0,0,0,.10);font-size:14px;color:#111'>{cuerpo}</div></div>")
    return (f"<div style='background:#ECE5DD;padding:14px;border-radius:10px;"
            f"max-height:420px;overflow-y:auto'>{filas}</div>")


def render_whatsapp() -> None:
    st.title("💬 WhatsApp")

    abierto = st.session_state.get("wa_open")

    # ---- Vista de CHAT (una conversación abierta) ----
    if abierto:
        conv = next((c for c in _WA_CONVERS if c["id"] == abierto), None)
        if conv is None:
            st.session_state.pop("wa_open", None)
            st.rerun()
        st.session_state.setdefault("wa_msgs", {})
        if abierto not in st.session_state["wa_msgs"]:
            st.session_state["wa_msgs"][abierto] = [
                {"dir": d, "tipo": "text", "text": t} for d, t in _WA_SEEDS.get(abierto, [])
            ]
        msgs = st.session_state["wa_msgs"][abierto]

        c1, c2 = st.columns([1, 5])
        if c1.button("← Volver"):
            st.session_state.pop("wa_open", None)
            st.rerun()
        clase, etq = _WA_ESTILO[conv["estado"]]
        c2.markdown(f"### {conv['contacto']} &nbsp; {_badge(etq, clase)}", unsafe_allow_html=True)
        st.caption("Simulación para la demo — aún no conectado a WhatsApp real.")

        st.markdown(_wa_html(msgs), unsafe_allow_html=True)

        with st.expander("📎 Adjuntar foto o audio"):
            nonce = st.session_state.get("wa_nonce", 0)
            img = st.file_uploader("Foto", type=["png", "jpg", "jpeg"], key=f"waimg{nonce}")
            aud = st.audio_input("Audio", key=f"waaud{nonce}")
            if st.button("Enviar adjunto"):
                enviado = False
                if img is not None:
                    msgs.append({"dir": "out", "tipo": "img", "data": img.getvalue(),
                                 "mime": img.type or "image/png"})
                    enviado = True
                if aud is not None:
                    msgs.append({"dir": "out", "tipo": "audio", "data": aud.getvalue()})
                    enviado = True
                if enviado:
                    st.session_state["wa_nonce"] = nonce + 1
                    st.rerun()
                else:
                    st.warning("Sube una foto o graba un audio primero.")

        prompt = st.chat_input("Escribe un mensaje…")
        if prompt:
            msgs.append({"dir": "out", "tipo": "text", "text": prompt})
            st.rerun()
        return

    # ---- Vista de BANDEJA (lista de conversaciones) ----
    st.caption("Bandeja con **resumen automático** y estado. Entra en un chat para responder. "
               "**Datos de ejemplo** — se conectará a n8n / WhatsApp.")
    pend = sum(1 for c in _WA_CONVERS if c["estado"] == "Necesita humano")
    m1, m2, m3 = st.columns(3)
    m1.metric("Conversaciones", len(_WA_CONVERS))
    m2.metric("🟠 Necesitan humano", pend)
    m3.metric("🟢 Atendidas por bot", sum(1 for c in _WA_CONVERS if c["estado"] == "Bot activo"))
    st.divider()

    filtro = st.radio("Ver", ["Todas", "Necesita humano", "Bot activo", "Resuelto"], horizontal=True)
    for c in _WA_CONVERS:
        if filtro != "Todas" and c["estado"] != filtro:
            continue
        clase, etq = _WA_ESTILO[c["estado"]]
        col = st.columns([6, 1])
        col[0].markdown(
            f"""<div class='wa-card'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <b>{c['contacto']}</b> {_badge(etq, clase)}
              </div>
              <div class='wa-resumen' style='margin-top:6px'>🧠 {c['resumen']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if col[1].button("Abrir", key="waopen_" + c["id"]):
            st.session_state["wa_open"] = c["id"]
            st.rerun()
    st.caption("La IA resume cada conversación en una línea para saber de un vistazo quién escribió y sobre qué.")


# ========================================================================
# Enrutado
# ========================================================================
if seccion.startswith("📄"):
    render_solicitudes()
elif seccion.startswith("📧"):
    render_correo()
elif seccion.startswith("📊"):
    render_leads()
else:
    render_whatsapp()

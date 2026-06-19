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
        ["📄 Solicitudes", "🗂️ Historial", "📊 Leads", "💬 WhatsApp"],
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


def _guardar_historial(nombre, aseguradora, tipo, filename, bytes_=None, texto=None) -> None:
    """Guarda la solicitud en el Historial (Firestore). Falla en silencio si no hay."""
    try:
        from core.historial import guardar_solicitud
        if guardar_solicitud(nombre, aseguradora, tipo, filename, bytes_, texto):
            st.caption("🗂️ Guardado en el Historial.")
    except Exception:
        pass


def _descarga_sanitas(datos: dict) -> None:
    from core.rellenar_sanitas import rellenar_sanitas
    res = rellenar_sanitas(datos)
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
    _guardar_historial(datos.get("nombre_completo", ""), "Sanitas", "pdf", res["ruta"].name, bytes_=pdf_bytes)


def _descarga_nuevamutua(datos: dict) -> None:
    from core.rellenar_nuevamutua import rellenar_nuevamutua
    res = rellenar_nuevamutua(datos)
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
    _guardar_historial(datos.get("nombre_completo", ""), "Nueva Mutua", "pdf", res["ruta"].name, bytes_=pdf_bytes)


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

    st.markdown("**Cuestionario de salud**")
    hay_si = st.checkbox("El estudiante declara algún 'Sí' (enfermedad, hospitalización, tratamiento…)")
    detalle = st.text_area("Detalle (si hay algún 'Sí')", "") if hay_si else ""
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
            "cuestionario_salud": {
                "tiene_algun_si": hay_si,
                "resumen_para_formulario": detalle if hay_si else "",
                "detalle_original": detalle,
            },
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


def render_solicitudes() -> None:
    st.title("📄 Solicitudes")
    modo = st.radio("Modo", ["📎 Adjuntar formulario", "✍️ Rellenar a mano"], horizontal=True)
    st.divider()
    if modo.startswith("📎"):
        render_adjuntar()
    else:
        render_manual()


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

    st.caption(f"{len(registros)} solicitud(es) guardada(s).")
    buscar = st.text_input("Buscar por nombre", "")
    for r in registros:
        if buscar and buscar.lower() not in r.get("nombre", "").lower():
            continue
        fecha = r.get("fecha")
        fstr = fecha.strftime("%d/%m/%Y %H:%M") if hasattr(fecha, "strftime") else str(fecha)
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.markdown(f"**{r.get('nombre', '(sin nombre)')}**  \n"
                    f"<span style='color:#5A6B82'>{r.get('aseguradora', '')}</span>", unsafe_allow_html=True)
        c2.markdown(f"<span style='color:#5A6B82'>{fstr}</span>", unsafe_allow_html=True)
        mime = "application/pdf" if r.get("tipo") == "pdf" else "text/plain"
        c3.download_button("⬇️ Descargar", data=historial.contenido_descargable(r),
                           file_name=r.get("filename", "solicitud"), mime=mime, key=r["_id"])
        st.divider()


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
def render_whatsapp() -> None:
    st.title("💬 WhatsApp")
    st.caption("Bandeja de conversaciones con **resumen automático** y estado. "
               "**Datos de ejemplo** — se conectará a n8n / WhatsApp.")

    convers = [
        {"contacto": "María González", "estado": "Necesita humano",
         "resumen": "Preguntó por la **renovación** de su póliza Sanitas y si sube el precio.",
         "ultimo": "¿Me podéis decir cuánto sería la renovación?"},
        {"contacto": "+34 6XX XX 12 34", "estado": "Bot activo",
         "resumen": "Pide **cotización** para estudiante de Colombia que viene en septiembre.",
         "ultimo": "Hola, quiero un seguro para estudiar en Madrid"},
        {"contacto": "Ahmed Saleh", "estado": "Necesita humano",
         "resumen": "Duda sobre **documentos** para el visado; quiere saber qué adjuntar.",
         "ultimo": "What documents do I need for the visa?"},
        {"contacto": "Camila Restrepo", "estado": "Resuelto",
         "resumen": "**Contrató** Sanitas Students; se le envió la solicitud para firmar.",
         "ultimo": "¡Perfecto, muchas gracias!"},
        {"contacto": "+57 3XX XXX 45 67", "estado": "Bot activo",
         "resumen": "Comparando **precios** entre Sanitas y Nueva Mutua.",
         "ultimo": "¿Cuál es más barato de los dos?"},
    ]

    estilo = {
        "Necesita humano": ("b-naranja", "🟠 Necesita humano"),
        "Bot activo": ("b-verde", "🟢 Bot activo"),
        "Resuelto": ("b-gris", "⚪ Resuelto"),
    }
    pend = sum(1 for c in convers if c["estado"] == "Necesita humano")
    m1, m2, m3 = st.columns(3)
    m1.metric("Conversaciones", len(convers))
    m2.metric("🟠 Necesitan humano", pend)
    m3.metric("🟢 Atendidas por bot", sum(1 for c in convers if c["estado"] == "Bot activo"))
    st.divider()

    filtro = st.radio("Ver", ["Todas", "Necesita humano", "Bot activo", "Resuelto"], horizontal=True)
    for c in convers:
        if filtro != "Todas" and c["estado"] != filtro:
            continue
        clase, txt = estilo[c["estado"]]
        st.markdown(
            f"""<div class='wa-card'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <b>{c['contacto']}</b> {_badge(txt, clase)}
              </div>
              <div class='wa-resumen' style='margin-top:6px'>🧠 {c['resumen']}</div>
              <div style='color:#7A8AA0;font-size:0.85rem;margin-top:4px'>Último: “{c['ultimo']}”</div>
            </div>""",
            unsafe_allow_html=True,
        )
    st.caption("La idea: la IA lee cada conversación y te la resume en una línea, "
               "para que sepas de un vistazo quién escribió y sobre qué. Se conectará a n8n.")


# ========================================================================
# Enrutado
# ========================================================================
if seccion.startswith("📄"):
    render_solicitudes()
elif seccion.startswith("🗂"):
    render_historial()
elif seccion.startswith("📊"):
    render_leads()
else:
    render_whatsapp()

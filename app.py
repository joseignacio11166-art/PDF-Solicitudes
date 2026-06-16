"""
app.py — Interfaz local (Streamlit) del Generador de Solicitudes.

Se ejecuta con:  streamlit run app.py
Se abre en el navegador en http://localhost:8501 — sigue siendo LOCAL (no es una
web pública; nada sale de tu ordenador).

Flujo: subir cotización -> detecta aseguradora -> el cerebro propone los datos ->
tú revisas/corriges -> generar (correo Generali; los PDF de Sanitas/Nueva Mutua
llegan en el siguiente paso).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from config import BASE_DIR, GENERALI, NUEVA_MUTUA, SANITAS
from core.leer_cotizacion import leer_cotizacion
from core.generar_generali import generar_generali

LOGO = str(BASE_DIR / "assets" / "alumnuscare_logo.png")

st.set_page_config(page_title="AlumnusCare · Generador de Solicitudes", page_icon=LOGO, layout="centered")

# --- Estilo (azul AlumnusCare) ------------------------------------------
st.markdown(
    """
    <style>
      h1, h2, h3 { color: #1F3148; }
      /* Cabeceras de paso con acento azul a la izquierda */
      div[data-testid="stHeadingWithActionElements"] h2 {
          border-left: 5px solid #1CA0D4; padding-left: 12px;
      }
      /* Botones en azul de marca */
      .stButton > button, .stDownloadButton > button {
          background: #1CA0D4; color: white; border: none;
          border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem;
      }
      .stButton > button:hover, .stDownloadButton > button:hover {
          background: #1689B8; color: white;
      }
      div[data-testid="stExpander"] {
          border: 1px solid #CFE7F3; border-radius: 10px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

_lc = st.columns([1, 2, 1])
with _lc[1]:
    st.image(LOGO, use_container_width=True)
st.markdown(
    "<h2 style='text-align:center;margin:0.2rem 0 0'>Generador de Solicitudes de Seguro</h2>"
    "<p style='text-align:center;color:#5A6B82;margin:0.2rem 0 0'>"
    "Rose &amp; Pagés · Herramienta local y privada — los datos no salen de tu ordenador</p>",
    unsafe_allow_html=True,
)
st.divider()

NOMBRE_ASEGURADORA = {
    GENERALI: "Generali (correo)",
    NUEVA_MUTUA: "Nueva Mutua (PDF)",
    SANITAS: "Sanitas (PDF)",
}


def _guardar_temporal(archivo) -> Path:
    """Guarda el PDF subido en un archivo temporal y devuelve su ruta."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(archivo.getbuffer())
    tmp.close()
    return Path(tmp.name)


# --- Acceso por contraseña ----------------------------------------------
# Solo se exige si existe APP_PASSWORD (en .env local o en variables del servidor).
# En local sin esa variable, no pide contraseña.
_PASSWORD = os.getenv("APP_PASSWORD", "")
if _PASSWORD and not st.session_state.get("_auth_ok"):
    _pwd = st.text_input("🔒 Contraseña de acceso", type="password",
                         placeholder="Introduce la contraseña para entrar")
    if _pwd:
        if _pwd == _PASSWORD:
            st.session_state["_auth_ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

# --- Paso 1: subir la cotización ----------------------------------------
st.header("1 · Sube la cotización")
archivo = st.file_uploader("Arrastra aquí el PDF de HiBroker (Pagés)", type=["pdf"])

if not archivo:
    st.info("Esperando una cotización en PDF para empezar.")
    st.stop()

# Leer (determinista) y cachear por nombre de archivo.
if st.session_state.get("_archivo") != archivo.name:
    ruta = _guardar_temporal(archivo)
    st.session_state["_archivo"] = archivo.name
    st.session_state["crudos"] = leer_cotizacion(ruta)
    st.session_state.pop("cerebro", None)  # invalidar análisis previo

crudos = st.session_state["crudos"]
detectada = crudos.get("aseguradora_detectada")

# --- Paso 2: aseguradora detectada --------------------------------------
st.header("2 · Aseguradora detectada")
if detectada:
    st.success(f"Detectada por el producto **{crudos.get('producto')}** → **{NOMBRE_ASEGURADORA[detectada]}**")
else:
    st.error(f"No reconozco el producto '{crudos.get('producto')}'. Elige la aseguradora a mano.")

opciones = [SANITAS, NUEVA_MUTUA, GENERALI]
elegida = st.selectbox(
    "Aseguradora a usar",
    opciones,
    index=opciones.index(detectada) if detectada in opciones else 0,
    format_func=lambda a: NOMBRE_ASEGURADORA[a],
)
if detectada and elegida != detectada:
    st.warning(f"⚠️ Ojo: el producto es **{NOMBRE_ASEGURADORA[detectada]}**, pero elegiste **{NOMBRE_ASEGURADORA[elegida]}**.")

# --- Paso 3: el cerebro propone -----------------------------------------
st.header("3 · Revisa lo que se va a poner")

if st.button("🧠 Analizar con el cerebro (Claude)"):
    with st.spinner("Razonando los datos variables…"):
        from cerebro.prompt_extraccion import extraer_datos
        from config import OFICINA
        try:
            d = extraer_datos(crudos)
            # Si la dirección NO es de España, mostrar ya la de la oficina (es la que
            # se usará en Sanitas/Nueva Mutua). El domicilio original queda en los avisos.
            d["_direccion_oficina"] = not d.get("direccion_en_espana", True)
            if d["_direccion_oficina"]:
                d["direccion_via"] = OFICINA["via"]
                d["direccion_numero"] = OFICINA["numero"]
                d["direccion_piso"] = OFICINA["piso"]
                d["direccion_puerta"] = OFICINA["puerta"]
                d["municipio"] = OFICINA["municipio"]
                d["provincia"] = OFICINA["provincia"]
                d["codigo_postal"] = OFICINA["codigo_postal"]
                d["direccion_en_espana"] = True  # la de oficina SÍ es de España (respeta ediciones)
            st.session_state["cerebro"] = d
        except Exception as e:  # noqa: BLE001
            st.error(f"Error al analizar: {e}")

datos = st.session_state.get("cerebro")
if not datos:
    st.info("Pulsa **Analizar con el cerebro** para proponer los datos.")
    st.stop()

# Aviso determinista: la fecha de inicio de póliza debe ir con ≥2 meses de antelación.
from datetime import date as _date, datetime as _dt
from dateutil.relativedelta import relativedelta
try:
    _fe = _dt.strptime(datos.get("fecha_efecto", ""), "%d/%m/%Y").date()
    _minimo = _date.today() + relativedelta(months=2)
    if _fe < _minimo:
        st.warning(
            f"⚠️ La **fecha de inicio de la póliza** ({datos['fecha_efecto']}) NO está a 2 meses vista "
            f"(mínimo: {_minimo.strftime('%d/%m/%Y')}). La póliza debe empezar con al menos 2 meses "
            "de antelación: revisa/corrige la fecha de efecto."
        )
except Exception:
    pass

# Avisos del cerebro
if datos.get("avisos"):
    with st.expander(f"⚠️ {len(datos['avisos'])} aviso(s) para revisar", expanded=True):
        for a in datos["avisos"]:
            st.markdown(f"- {a}")

# Cuestionario de salud: regla crítica
salud = datos.get("cuestionario_salud", {})
if salud.get("tiene_algun_si"):
    st.error(
        "🛑 El cuestionario de salud tiene algún **'Sí'** declarado. "
        "En Sanitas/Nueva Mutua **NO se marca automáticamente**: este caso se gestiona a mano.\n\n"
        f"**Resumen:** {salud.get('resumen_para_formulario','')}"
    )
else:
    st.success("Cuestionario de salud: todo en **No** (se marcará 'No' automáticamente).")

# Campos editables (tabla campo -> valor)
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

# Dirección (editable). Si no hay dirección en España, en Sanitas/Nueva Mutua se
# usará por defecto la de la oficina (Hermosilla 80, 2A, Madrid, 28001).
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

# --- Paso 4: generar -----------------------------------------------------
st.header("4 · Generar")

if elegida == GENERALI:
    if st.button("✉️ Generar correo de Generali"):
        # Para Generali, la dirección va completa tal como viene en la cotización.
        crudos_para_correo = dict(crudos)
        crudos_para_correo["nombre"] = datos["nombre_completo"] if datos.get("nombre_completo") else f"{datos['nombre']} {datos['apellidos']}".strip()
        crudos_para_correo["fecha_inicio_poliza"] = datos["fecha_efecto"]
        crudos_para_correo["correo"] = datos["correo"]
        crudos_para_correo["telefono_movil"] = datos["telefono_movil"]
        correo = generar_generali(crudos_para_correo)

        st.text_input("ASUNTO", correo["asunto"])
        st.text_area("CUERPO", correo["cuerpo"], height=380)
        st.download_button(
            "⬇️ Descargar correo (.txt)",
            data=f"ASUNTO:\n{correo['asunto']}\n\nCUERPO:\n{correo['cuerpo']}",
            file_name=f"generali_{datos.get('apellidos','').strip() or 'correo'}.txt",
        )
        st.caption("Recuerda adjuntar a mano: documento de identidad y carta de aceptación de la universidad.")

elif elegida == SANITAS:
    if st.button("📄 Generar PDF de Sanitas"):
        from core.rellenar_sanitas import rellenar_sanitas
        res = rellenar_sanitas(datos)
        with open(res["ruta"], "rb") as fh:
            pdf_bytes = fh.read()
        if res["parar"]:
            st.error("🛑 El cuestionario tiene algún 'Sí': las casillas de salud se han dejado "
                     "**SIN marcar**. Revisa el caso y márcalas a mano antes de enviar.")
        st.success("PDF de Sanitas generado: **editable** y **sin firmar** (la persona firma en págs. 1, 3 y 4).")
        st.download_button("⬇️ Descargar PDF de Sanitas", data=pdf_bytes,
                           file_name=res["ruta"].name, mime="application/pdf")
        for a in res["avisos"]:
            st.caption(f"• {a}")

else:  # NUEVA_MUTUA
    if st.button("📄 Generar PDF de Nueva Mutua"):
        from core.rellenar_nuevamutua import rellenar_nuevamutua
        res = rellenar_nuevamutua(datos)
        with open(res["ruta"], "rb") as fh:
            pdf_bytes = fh.read()
        if res["parar"]:
            st.error("🛑 El cuestionario tiene algún 'Sí': el 'NO' de salud se ha dejado "
                     "**SIN marcar**. Revisa el caso y márcalo a mano antes de enviar.")
        st.success("PDF de Nueva Mutua generado: relleno y **sin firmar** (la persona firma en la última página).")
        st.download_button("⬇️ Descargar PDF de Nueva Mutua", data=pdf_bytes,
                           file_name=res["ruta"].name, mime="application/pdf")
        for a in res["avisos"]:
            st.caption(f"• {a}")

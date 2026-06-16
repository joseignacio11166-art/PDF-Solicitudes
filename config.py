"""
config.py — Valores FIJOS y rutas del proyecto.

Aquí vive todo lo DETERMINISTA: lo que el código pone siempre igual y la IA
nunca decide. Si una regla fija cambia (un código, un correo, una dirección
por defecto), se cambia AQUÍ y en un solo sitio.
"""
from pathlib import Path

# --- Rutas ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PLANTILLAS_DIR = BASE_DIR / "plantillas"
ENTRADAS_DIR = BASE_DIR / "entradas"
SALIDAS_DIR = BASE_DIR / "salidas"
REGLAS_DIR = BASE_DIR / "reglas"
EJEMPLOS_DIR = BASE_DIR / "ejemplos"

PLANTILLA_SANITAS = PLANTILLAS_DIR / "sanitas_blanco.pdf"
PLANTILLA_NUEVAMUTUA = PLANTILLAS_DIR / "nuevamutua_blanco.pdf"
MAPEO_SANITAS = REGLAS_DIR / "sanitas_campos_mapeo.json"

# --- Aseguradoras --------------------------------------------------------
GENERALI = "GENERALI"
NUEVA_MUTUA = "NUEVA_MUTUA"
SANITAS = "SANITAS"

# Detección por el campo "Producto" de la cotización HiBroker.
# Se compara en MAYÚSCULAS y sin espacios sobrantes.
DETECCION_PRODUCTO = {
    "SANITAS_STUDENTS": SANITAS,
    "SANITAS": SANITAS,
    "NUEVA_MUTUA_SANITARIA": NUEVA_MUTUA,
    "SALUD PROFESIONAL FAMILIA": NUEVA_MUTUA,
    "ALUMNUSCARE": GENERALI,
}

# --- Dirección por defecto de la OFICINA --------------------------------
# Se usa SOLO cuando la cotización no trae una dirección en España.
OFICINA = {
    "via": "Calle Hermosilla",
    "numero": "80",
    "piso": "2",
    "puerta": "A",
    "municipio": "Madrid",
    "provincia": "Madrid",
    "codigo_postal": "28001",
}

# --- Valores FIJOS por aseguradora --------------------------------------
FIJOS_GENERALI = {
    "asunto_prefijo": "Emisión: Salud Med: 17704",
    "codigo_tipologia": "T1",
    "codigo_tipo_peticion": "ST8",
    "codigo_entidad_mediador": "17704",
    "mail_peticionario": "jcato@pagesseguros.com",
    "agrupacion_ramo": "16",
    "pago": "Anual TDC",
    "nota": "Emitir con certificado para extranjería.",
}

FIJOS_NUEVA_MUTUA = {
    "producto": "SALUD PROFESIONAL FAMILIA sin copago",
    "mediador": "ROSE & PAGES",
    "metodo_pago": "tarjeta",  # marca casilla "x" PAGO POR TARJETA
    "parentesco": "el mismo",
}

FIJOS_SANITAS = {
    "asegurados": "1",
    "producto": "Sanitas International Students",
    "mediador": "Rose & Pagés",
    "codigo_mediador": "30149",
    "parentesco": "el mismo",
    "calidad_sueno": "Regular, depende del día",
}

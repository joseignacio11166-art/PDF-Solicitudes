"""
reglas/sanitas.py — Mapeo de campos y reglas (fijo/variable) de Sanitas.

Construye el diccionario {nombre_campo: valor} que se escribirá en el PDF AcroForm.
Las casillas se casaron por POSICIÓN abriendo el PDF (los nombres internos engañan):
ver reglas/inspeccionar_sanitas.py.

Hallazgos clave (verificados por posición en el PDF en blanco):
- Producto "Sanitas International Students" -> campo `pto. anterior` (está bajo la
  etiqueta "Nombre del producto a contratar"; el nombre interno despista). El campo
  de póliza anterior real es `pza anterior`, que se deja vacío.
- Las 3 casillas "No Consiento" (pág. 3) son: `No Consiento`, `No Consiento_2`, `toggle_6`.
- Cuestionario de salud (pág. 4) "No": No_310, No_430, No_530, No_630, No_630a.
- Estadísticas (pág. 4): fumador No=No_61301, alcohol No=No_6301, sueño Regular=No_630111.
- La fecha de efecto: el día es "01" PREIMPRESO; solo se rellenan mes y año.
"""
from __future__ import annotations

from datetime import date

from config import FIJOS_SANITAS, OFICINA

ON = "/On"


def _partes_fecha(fecha: str) -> tuple[str, str, str]:
    """'dd/mm/aaaa' -> ('dd','mm','aaaa'). Devuelve ('','','') si no se puede."""
    try:
        d, m, a = fecha.strip().split("/")
        return d.zfill(2), m.zfill(2), a
    except Exception:
        return "", "", ""


def _direccion(datos: dict) -> dict:
    """Decide la dirección: la de la persona si está en España; si no, la de oficina."""
    if datos.get("direccion_en_espana") and datos.get("direccion_via"):
        via = datos.get("direccion_via", "")
        numero = datos.get("direccion_numero", "")
        piso = datos.get("direccion_piso", "")
        puerta = datos.get("direccion_puerta", "")
        municipio = datos.get("municipio", "")
        provincia = datos.get("provincia", "")
        cp = datos.get("codigo_postal", "")
    else:
        via, numero = OFICINA["via"], OFICINA["numero"]
        piso, puerta = OFICINA["piso"], OFICINA["puerta"]
        municipio, provincia = OFICINA["municipio"], OFICINA["provincia"]
        cp = OFICINA["codigo_postal"]

    # Sanitas: número en la línea de la vía; piso/puerta en el campo "n".
    linea_via = f"{via} {numero}".strip()
    linea_n = " ".join(p for p in [f"PISO {piso}".strip() if piso else "", puerta] if p).strip()
    return {
        "via": linea_via,
        "n": linea_n,
        "municipio": municipio,
        "provincia": provincia,
        "cp": cp,
    }


def construir_valores_sanitas(datos: dict, hoy: date | None = None) -> dict:
    """
    Devuelve {"valores": {...}, "avisos": [...], "parar": bool}.
    `datos` = salida del cerebro (ya revisada por la usuaria).
    `parar` = True si el cuestionario de salud tiene algún "Sí" (gestión manual).
    """
    hoy = hoy or date.today()
    f = FIJOS_SANITAS
    avisos: list[str] = []
    v: dict[str, str] = {}

    # --- FIJOS de cabecera (pág. 1) -------------------------------------
    v["asegurados"] = f["asegurados"]
    v["pto. anterior"] = f["producto"]          # producto va AQUÍ (ver cabecera módulo)
    v["Nueva póliza"] = ON
    v["mediador"] = f["mediador"]
    v["Corredor"] = ON
    v["codigo mediador"] = f["codigo_mediador"]
    v["Anual"] = ON
    v["El Mediador"] = ON

    # --- Tomador (pág. 1, variable) -------------------------------------
    v["nombre tomador"] = datos.get("nombre_completo", "")
    v["numero documento"] = datos.get("numero_documento", "")
    v["nacionalidad"] = datos.get("nacionalidad", "")
    if not datos.get("nacionalidad"):
        avisos.append("Falta 'nacionalidad' (no viene en la cotización): revísalo en el PDF.")

    # Tipo de documento
    tipo = (datos.get("tipo_documento", "") or "").lower()
    if "pasaporte" in tipo:
        v["Pasaporte"] = ON
        v["Pasaporte_211"] = ON
    elif "nie" in tipo:
        v["NIE"] = ON
        v["NIE_210"] = ON
    elif "nif" in tipo or "dni" in tipo:
        v["NIF"] = ON
        v["NIF_210"] = ON

    # Sexo
    if datos.get("sexo") == "Mujer":
        v["Mujer"] = ON
        v["Mujer_210"] = ON
    elif datos.get("sexo") == "Hombre":
        v["Hombre"] = ON
        v["Hombre_210"] = ON

    # Nacimiento
    dn, mn, an = _partes_fecha(datos.get("fecha_nacimiento", ""))
    v["dia2"], v["mes2"], v["año2"] = dn, mn, an

    # Fecha de efecto: día "01" preimpreso -> solo mes y año
    _, mef, aef = _partes_fecha(datos.get("fecha_efecto", ""))
    v["mes1"], v["año1"] = mef, aef

    # Contacto
    movil = datos.get("telefono_movil", "")
    v["movil1"] = movil
    v["movil2"] = movil
    v["email"] = datos.get("correo", "")

    # Domicilio del tomador
    dirc = _direccion(datos)
    v["domicilio tomador"] = dirc["via"]
    v["domicilio tomador n"] = dirc["n"]
    v["municipio tomador"] = dirc["municipio"]
    v["cp tomador"] = dirc["cp"]
    v["provincia tomador"] = dirc["provincia"]

    # --- Consentimientos (pág. 3): las 3 casillas "No Consiento" ---------
    v["No Consiento"] = ON
    v["No Consiento_2"] = ON
    v["toggle_6"] = ON

    # --- Asegurado (pág. 4) = el mismo ----------------------------------
    v["nueva poliza30"] = ON
    v["parentesco10"] = f["parentesco"]
    v["nombre asegurado pag310"] = datos.get("nombre_completo", "")
    v["día_410"], v["mes_510"], v["año_510"] = dn, mn, an
    v["mes_610"], v["año_610"] = mef, aef
    v["movil1 pag310"] = movil
    v["movil2 pag310"] = movil
    v["Teléfono 2_210"] = datos.get("correo", "")
    v["nacionalidado210"] = datos.get("nacionalidad", "")
    v["num doc10"] = datos.get("numero_documento", "")
    v["peso10"] = datos.get("peso_kg", "")
    v["estatura10"] = datos.get("altura_cm", "")

    # --- Dos preguntas previas al cuestionario (FIJO = No) --------------
    # (casadas por posición; los nombres internos engañan)
    v["N de póliza anterior15"] = "/1"  # ¿asegurado de Sanitas/Bupa antes? -> No (casilla dcha.)
    v["Sí_510"] = "/On"                 # ¿procede de otra compañía? -> No (casilla dcha.)

    # --- Preguntas estadísticas (FIJO) ----------------------------------
    v["No_61301"] = ON   # fumador: No
    v["No_6301"] = ON    # alcohol: No
    v["No_630111"] = ON  # calidad de sueño: "Regular, depende del día"

    # --- Cuestionario de salud (REGLA CRÍTICA) --------------------------
    salud = datos.get("cuestionario_salud", {})
    parar = bool(salud.get("tiene_algun_si"))
    if parar:
        avisos.append(
            "🛑 El cuestionario de salud tiene algún 'Sí'. NO se marcan las casillas "
            "de salud automáticamente: este caso requiere gestión manual."
        )
    else:
        for casilla in ("No_310", "No_430", "No_530", "No_630", "No_630a"):
            v[casilla] = ON

    # --- Fechas de firma (pág. 1, 3 y 4) = HOY; firma vacía -------------
    dh, mh, ah = f"{hoy.day:02d}", f"{hoy.month:02d}", str(hoy.year)
    v["dia2 firma"], v["mes2 firma"], v["año2 firma"] = dh, mh, ah  # pág. 1
    v["día_3"], v["mes_4"], v["año_4"] = dh, mh, ah                 # pág. 3
    v["día_730"], v["mes_730"], v["año_730"] = dh, mh, ah           # pág. 4

    return {"valores": v, "avisos": avisos, "parar": parar}

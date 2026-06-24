# Estado del proyecto — AlumnusCare · Centro de Operaciones

Resumen para retomar el trabajo (o para un chat nuevo de Claude Code).
Fuente de la idea original: `CONTEXTO_PROYECTO.md`.

## Qué es
App (Streamlit) que convierte una **cotización** en la **solicitud** de la aseguradora:
- **Sanitas** → PDF rellenado (editable, sin firmar).
- **Nueva Mutua** → PDF rellenado por coordenadas (editable, sin firmar).
- **Generali / AlumnusCare** → correo (asunto + cuerpo).

Es un **Centro de Operaciones** con menú lateral: **Solicitudes** (Adjuntar formulario / Rellenar a mano / Historial), **Leads** y **WhatsApp**.

## Dónde vive
- **Código local:** `C:\Users\jochi\Desktop\generador-solicitudes`
- **GitHub:** https://github.com/joseignacio11166-art/PDF-Solicitudes (rama **master**)
- **Desplegado:** Google Cloud Run · servicio `pdf-solicitudes` · región `europe-west1`
- **Link (producción):** https://pdf-solicitudes-321150927024.europe-west1.run.app  (pide contraseña = `APP_PASSWORD`)
- **Acceso directo en el escritorio:** `AlumnusCare - Centro de Operaciones.url`

## Cómo desplegar cambios
`git add -A && git commit -m "..." && git push origin master` → Cloud Build reconstruye solo (~5 min). **El link nunca cambia.**

## Cómo ejecutar en local
- Doble clic en `Iniciar AlumnusCare.bat`, o
- `.venv/Scripts/python.exe -m streamlit run app.py` → http://localhost:8501
- En local NO pide contraseña (solo si `APP_PASSWORD` está en `.env`).

## Archivos clave
- `app.py` — interfaz (secciones y modos).
- `config.py` — valores FIJOS, rutas, dirección de OFICINA.
- `core/leer_cotizacion.py` — lee el PDF de cotización + **detecta la aseguradora** por el campo "Producto".
- `cerebro/prompt_extraccion.py` + `cerebro/cliente.py` — el "cerebro" (Claude): normaliza datos, parte nombre, teléfono, salud, avisos.
- `reglas/sanitas.py`, `reglas/nuevamutua.py`, `reglas/generali.py` — reglas/posiciones de cada aseguradora.
- `reglas/sanitas_campos_mapeo.json` — campos del PDF de Sanitas. `reglas/inspeccionar_sanitas.py` — herramienta dev.
- `core/rellenar_sanitas.py`, `core/rellenar_nuevamutua.py`, `core/generar_generali.py` — generan la salida.
- `core/historial.py` — guarda/lee el historial en **Firestore**.
- `plantillas/` — PDFs en blanco. `assets/` — logo + icono.
- `.env` — `ANTHROPIC_API_KEY`, `APP_PASSWORD` (local; **gitignored**).

## Google Cloud (proyecto "My First Project")
- **Cloud Run** `pdf-solicitudes`: variables de entorno `ANTHROPIC_API_KEY` y `APP_PASSWORD`. Despliegue continuo desde GitHub (rama master, Dockerfile).
- **Firestore** (Modo nativo, región Europa, base `(default)`) → colección `solicitudes`.
- **IAM:** el service account `321150927024-compute@developer.gserviceaccount.com` tiene el rol **Usuario de Cloud Datastore** (necesario para el Historial).

## Estado de cada parte
- **Solicitudes** ✅ funcionando (Generali, Sanitas, Nueva Mutua; por cotización y a mano).
- **Historial** ✅ guarda datos en Firestore y **regenera el PDF al descargar** (el PDF de Sanitas no cabe en Firestore, por eso se regenera). Botones de borrar.
- **Leads** ⏳ tabla de EJEMPLO (falta endpoint de "listar leads" del cotizador).
- **WhatsApp** ⏳ bandeja de EJEMPLO con resumen IA + estado, y **chat interactivo simulado** (abrir conversación, escribir, enviar, adjuntar foto/audio) para demo. Falta montar la conexión real (Meta + n8n).

## Pendiente / próximos pasos
1. **Jesús (cotizador):**
   - Generar una **apikey de PRECIOS para el mediador AlumnusCare** (`healt_hb_get_products_plans_coverages` da "Error validando apiKey, Acceso Denegado" con todas las claves).
   - Endpoint para **LISTAR leads** (hoy solo existe crear, `AddPreaffiliate`).
2. **WhatsApp (lo montamos nosotros, no Jesús):** decidido ir con **Meta Cloud API directo** (0 €/mes). Flujo: WhatsApp → **Meta webhook → n8n** → Firestore → Centro de Operaciones. Hay que: alta en Meta Business + verificación, número (dedicado o de empresa, se "migra"), webhook a n8n, y yo construyo la **pantalla de chat** + **switch on/off del bot** + "tomar el control" por conversación. Plan por fases (bot apagado → pruebas sin clientes → bot gradual).
3. Cuando haya precios: **PDF de cotización dinámico** (clicable, con enlaces a condiciones).

## API del cotizador (HiBroker Health)
- Endpoint: `POST https://iufyql1gh0.execute-api.us-east-2.amazonaws.com/dev/adminhealt` (se elige función con `functionName`).
- Funciona: `generate_temp_apikey`, `healt_hb_get_token_mediator`, crear lead (`AddPreaffiliate`).
- No funciona: `healt_hb_get_products_plans_coverages` (precios) → "Acceso Denegado".
- Las claves están en el Postman que pasó Jesús (no en el repo).

## Memoria de Claude Code
Un chat nuevo en esta carpeta carga automáticamente la memoria en:
`C:\Users\jochi\.claude\projects\C--Users-jochi-Desktop-generador-solicitudes\memory\`
(ficheros `proyecto-generador-solicitudes.md` y `entorno-dev-generador-solicitudes.md`).

# Estado del proyecto — AlumnusCare · Centro de Operaciones

Documento de **traspaso** para retomar el trabajo o para un **chat nuevo de Claude Code**.
Fuente de la idea original: `CONTEXTO_PROYECTO.md`. La memoria de Claude (abajo) se carga sola.

> **Para un chat nuevo:** lee este archivo entero y la memoria. La usuaria (Rose & Pagés /
> AlumnusCare) NO es técnica: hay que guiarla clic a clic, con enlaces, y desplegar por ella.

## Qué es
App (Streamlit) = **Centro de Operaciones** de AlumnusCare. Convierte una **cotización** en la
**solicitud** de la aseguradora, y centraliza la operativa.
- **Sanitas** → PDF rellenado (AcroForm editable, sin firmar).
- **Nueva Mutua** → PDF rellenado por coordenadas (overlay, editable). Usa la **solicitud v2 (2026)**.
- **Generali / AlumnusCare** → correo (asunto + cuerpo).
- **ASISA** → pedida pero SIN plantilla aún (no generable).

Menú lateral: **📄 Solicitudes**, **📧 Correo**, **📊 Leads**, **💬 WhatsApp**.

## Dónde vive
- **Código local:** `C:\Users\jochi\Desktop\generador-solicitudes`
- **GitHub:** https://github.com/joseignacio11166-art/PDF-Solicitudes (rama **master**)
- **Desplegado:** Google Cloud Run · servicio `pdf-solicitudes` · región `europe-west1` · proyecto "My First Project"
- **Link (producción):** https://pdf-solicitudes-321150927024.europe-west1.run.app  (pide contraseña = `APP_PASSWORD`)
- **Acceso directo en el escritorio:** `AlumnusCare - Centro de Operaciones.url`

## Cómo desplegar cambios
`git add -A && git commit -m "..." && git push origin master` → Cloud Build reconstruye solo (~5 min). **El link nunca cambia.** (git user ya configurado; los push usan credenciales guardadas.)

## Cómo ejecutar / probar en local
- Doble clic en `Iniciar AlumnusCare.bat`, o `.venv/Scripts/python.exe -m streamlit run app.py`.
- En local NO pide contraseña (solo si `APP_PASSWORD` está en `.env`).
- **No hay poppler ni LibreOffice.** Para "ver" PDFs: renderizar con **pypdfium2** a PNG y leer la imagen.
- Smoke test sin navegador: `streamlit.testing.v1.AppTest` (ver ejemplos en el historial de comandos).
- Python 3.14 + venv en `.venv/`. En Bash usar barras normales: `.venv/Scripts/python.exe`.

## Secciones y modos de la app
- **📄 Solicitudes** (5 modos):
  - **📎 Adjuntar formulario** — sube cotización → el cerebro (Claude) extrae datos → revisas → genera.
  - **✍️ Rellenar a mano** — formulario manual (sin IA). En Nueva Mutua: campos de **repatriación** + salud **Sí/No por pregunta**.
  - **✏️ Corregir un PDF** — sube una solicitud ya hecha (Sanitas/Nueva Mutua), cambia un dato y descarga corregido EN SITIO (conserva firma). `core/corregir.py`.
  - **🔁 Antigua → nueva** — sube una solicitud antigua de Nueva Mutua → la IA lee los datos → añades repatriación → genera v2. Opción **con/sin firma** (recorta la firma del PDF viejo y la estampa).
  - **🗂️ Historial** — solicitudes generadas, guardadas en Firestore; re-descarga (regenera el PDF); borrar.
- **📧 Correo** — lee Firestore colección `correos` (que volcará **n8n** desde el buzón `atencionestudiantes@`). **EN CURSO** (ver abajo).
- **📊 Leads** — tabla de EJEMPLO (falta endpoint "listar leads" del cotizador).
- **💬 WhatsApp** — bandeja de EJEMPLO + **chat interactivo simulado** (demo). Falta conexión real.

## Archivos clave
- `app.py` — interfaz (todas las secciones/modos).
- `config.py` — valores FIJOS, rutas, dirección de OFICINA (Hermosilla 80, 2A, Madrid, 28001).
- `core/leer_cotizacion.py` — lee cotización + **detecta aseguradora** por el campo "Producto".
- `cerebro/prompt_extraccion.py` + `cerebro/cliente.py` — el "cerebro" (Claude): nombre/apellidos, teléfono (+país), fechas, provincia, nacionalidad, resumen salud, avisos.
- `reglas/sanitas.py`, `reglas/nuevamutua.py` (v2), `reglas/generali.py` — reglas/posiciones por aseguradora.
- `reglas/sanitas_campos_mapeo.json`, `reglas/inspeccionar_sanitas.py` (dev).
- `core/rellenar_sanitas.py`, `core/rellenar_nuevamutua.py` (acepta `firma_png`), `core/generar_generali.py`.
- `core/historial.py`, `core/correos.py`, `core/corregir.py` — Firestore + corrección.
- `plantillas/` — PDFs en blanco (Nueva Mutua = v2). `assets/` — logo + icono.
- `.env` — `ANTHROPIC_API_KEY`, `APP_PASSWORD` (local; **gitignored**).

## Google Cloud
- **Cloud Run** `pdf-solicitudes`: vars `ANTHROPIC_API_KEY`, `APP_PASSWORD`. Despliegue continuo desde GitHub (master, Dockerfile). Memoria 1 GiB, puerto 8080, acceso público.
- **Firestore** (Modo nativo, Europa, base `(default)`) → colecciones `solicitudes` (historial) y `correos` (correos de n8n).
- **IAM:** el service account de Cloud Run `321150927024-compute@developer.gserviceaccount.com` tiene rol **Usuario de Cloud Datastore**.

## 🔧 TAREA EN CURSO: sección Correo vía n8n
La app ya lee Firestore `correos` (colección). Falta el **lado n8n** (puente).
Arquitectura: `atencionestudiantes@ (Outlook) → n8n → Firestore "correos" → app`.
Las solicitudes llegan como correo reenviado de **solicitudestudiantes@hi-broker.com**, asunto
"Fwd: Solicitud - Seguro de Salud", con un **adjunto .eml** (elemento de Outlook). Los de
**estudiante-asegurado@hi-broker.com** "Comparativa de precios" son **cotizaciones** (no solicitudes).
Buzón = Microsoft 365; Excel de seguimiento = SharePoint (`ALUMNUSCARE_2026_v3.xlsx`). NO hay admin de
Microsoft accesible → por eso se usa **n8n** (no Graph directo).

**Contrato de Firestore** (lo que n8n debe escribir en `correos`):
```
{ remitente, asunto, fecha (ISO), es_solicitud (bool), estudiante, resumen, estado:"Nuevo", adjuntos:[...] }
```

**Dónde se quedó la usuaria (Paso A):** creando una **cuenta de servicio** de Google para que n8n escriba
en Firestore: Consola Google Cloud → IAM → Cuentas de servicio → Crear `n8n-firestore` → rol **"Usuario de
Cloud Datastore"** → Claves → Crear clave **JSON** → descargar. (Estaba eligiendo el rol.)
Enlace: https://console.cloud.google.com/iam-admin/serviceaccounts

**Paso B (siguiente):** flujo NUEVO en n8n (no el del chatbot): **Outlook Trigger** (buzón
atencionestudiantes@) → **IF** (remitente/asunto = solicitud) → **Edit Fields** → **Google Cloud Firestore**
(Create Document, colección `correos`, con el .json de la cuenta de servicio). Se puede entregar como JSON
para importar. Pendiente decidir: ¿n8n abre el .eml y saca datos de dentro, o solo registra que llegó?

## Pendiente / próximos pasos
1. **Correo** (en curso, arriba): terminar cuenta de servicio + flujo n8n.
2. **Jesús (cotizador HiBroker Health):**
   - **apikey de PRECIOS para AlumnusCare** (`healt_hb_get_products_plans_coverages` da "Acceso Denegado" con todas las claves).
   - Endpoint para **LISTAR leads** (hoy solo crear, `AddPreaffiliate`).
   - Endpoint base: `POST https://iufyql1gh0.execute-api.us-east-2.amazonaws.com/dev/adminhealt` (función por `functionName`). Funciona: `generate_temp_apikey`, `healt_hb_get_token_mediator`, `healt_hb_add_preaffiliate`. Claves en el Postman de Jesús (no en el repo).
3. **WhatsApp:** decidir Meta Cloud API directo (0€, montamos bandeja propia + bot + n8n) vs Wati (cuota, bandeja lista). Se hizo una lámina comparativa. Número se "migra" (deja de usarse en la app normal).
4. Con precios: **PDF de cotización dinámico** (clicable, enlaces a condiciones) para sustituir el pantallazo.

## Memoria de Claude Code (se carga sola en esta carpeta)
`C:\Users\jochi\.claude\projects\C--Users-jochi-Desktop-generador-solicitudes\memory\`
(`proyecto-generador-solicitudes.md` = qué es + TODAS las decisiones confirmadas y gotchas;
`entorno-dev-generador-solicitudes.md` = entorno/cómo ejecutar). **Leerlos al empezar.**

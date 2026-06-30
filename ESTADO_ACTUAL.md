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
- **📄 Solicitudes** (4 modos):
  - **📎 Adjuntar formulario** — sube cotización → el cerebro (Claude) extrae datos → revisas → genera.
  - **✍️ Rellenar a mano** — formulario manual (sin IA). En Nueva Mutua: campos de **repatriación** + salud **Sí/No por pregunta**.
  - **✏️ Corregir un PDF** — sube una solicitud (Sanitas/Nueva Mutua), muestra **TODOS los campos** (rellenos los que tengan dato), cambias/rellenas lo que sea y descarga corregido EN SITIO. Opción **incluir firma o sin firma** (radio). `core/corregir.py`. NM corrige por coordenadas v2 (mediador, tel fijo, profesión, estado civil, fechas, sexo, repatriación, peso/altura); Sanitas por AcroForm. OJO: si el PDF tiene los datos como IMAGEN (escaneado/aplanado), la lectura sale vacía (no hay texto) → se rellenan a mano; la pintura del corregido sí cae bien.
  - **🗂️ Historial** — solicitudes generadas, guardadas en Firestore; re-descarga (regenera el PDF); borrar.
  - *(El modo "🔁 Antigua → nueva" se ELIMINÓ jun 2026 — ya no se usa.)*
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

## ✅ Sección Correo vía n8n — NIVEL 1 FUNCIONA (jun 2026, PUENTE GMAIL)
La app ya lee Firestore `correos` (colección). Falta terminar el **lado n8n**.
Las solicitudes reales llegan al buzón compartido **atencionestudiantes@pagesseguros.com** (Microsoft 365),
reenviadas de **solicitudestudiantes@hi-broker.com**, asunto "Fwd: Solicitud - Seguro de Salud". El adjunto
es UN **elemento de Outlook (.eml)** que DENTRO trae los **3 archivos**: documento de identidad + carta de
aceptación universidad + formulario/cotización (todos los datos). Los de **estudiante-asegurado@hi-broker.com**
"Comparativa de precios" son cotizaciones sueltas (no solicitudes). OJO: llegan VARIOS correos con la palabra
"solicitud" que NO lo son → filtrar **por remitente** (`solicitudestudiantes@hi-broker.com`), no por asunto.

**MURO Microsoft:** NO hay admin de M365 accesible. El Outlook Trigger de n8n pide "aprobación del
administrador" (consentimiento de organización) y NO se puede saltar. Tampoco se puede probar fácil enviando
correos a ese buzón. → **Se abandona leer Outlook directamente.**

**SOLUCIÓN ADOPTADA — puente Gmail:**
`atencionestudiantes@ → (regla Outlook: De = solicitudestudiantes@hi-broker.com → Reenviar a Gmail) → Gmail → n8n (Gmail Trigger) → Firestore "correos" → app`
- Gmail puente dedicado creado: **alumnuscareestudiantes@gmail.com** (solo para esto; todo lo que entre ahí = solicitud).
- n8n se conecta a Gmail con "Sign in with Google" (NO necesita admin, es Gmail propio).
- La regla de reenvío en Outlook se da por buena (confiar); de momento se PRACTICA mandando solicitudes de
  ejemplo directamente al Gmail. La regla hay que ponerla dentro del buzón compartido vía "Abrir otro buzón".

**Contrato de Firestore** (lo que n8n escribe en `correos`):
```
{ remitente, asunto, fecha (ISO), es_solicitud (bool), estudiante, resumen, estado:"Nuevo", adjuntos:[...] }
```

**Flujo n8n MONTADO Y FUNCIONANDO:** `n8n/correos_nivel1.json` — 2 nodos: **Gmail Trigger** → **HTTP Request**
(POST a Firestore REST `…/projects/project-d06489fe-0e21-4087-b1a/databases/(default)/documents/correos`).
Probado: correo de prueba reenviado al Gmail → aparece en la sección 📧 Correo de la app. ✅

**Detalles técnicos / GOTCHAS resueltos (importantes si se retoma):**
- **Cuenta de servicio para la clave:** la org `jochiignaciocruz-org` tiene la política
  `iam.disableServiceAccountKeyCreation` ACTIVA → en "My First Project" NO deja descargar claves .json. Se
  resolvió creando la SA en el **otro proyecto SIN organización** (`n8n-firestore-500717`): SA
  **`n8n-bridge@n8n-firestore-500717.iam.gserviceaccount.com`**, clave JSON descargada ahí, y luego se le dio
  el rol **Usuario de Cloud Datastore** en "My First Project" (IAM → Conceder acceso). NO borrar el proyecto
  `n8n-firestore-500717` (aloja la SA/clave). `project_id` de Firestore = **project-d06489fe-0e21-4087-b1a**.
- **Credencial n8n** = tipo "Google Service Account API" (googleApi), con "Set up for use in HTTP Request node"
  ON y Scope `https://www.googleapis.com/auth/datastore`. El nodo HTTP usa Authentication=Predefined → Google
  Service Account API.
- **GOTCHA de la clave privada:** el campo Private Key de n8n es de UNA línea → al pegar la PEM multilínea solo
  cogía el primer renglón → error `secretOrPrivateKey must be an asymmetric key (RS256)`. SOLUCIÓN: pegar la
  clave en **formato de una sola línea con `\n`** (tal cual viene en el .json). "Connection tested successfully" = OK.
- Campos del Gmail Trigger: `From`, `Subject`, `snippet`, `internalDate` (NO hay `date` → el campo `fecha` queda
  vacío de momento; mejora opcional: usar `internalDate`). Al reenviar desde Outlook el remitente es atencionestudiantes@.

**PENDIENTE:** (1) **ACTIVAR el workflow** en n8n (Inactive→Active) para que procese solo. (2) **Rotar la clave**
de servicio (se expuso en el chat al leer el .json): crear clave nueva, actualizar credencial n8n, borrar la
vieja; borrar también los .txt temporales de la clave. (3) **Nivel 2:** que n8n abra el .eml, saque los 3
adjuntos (identidad+carta+cotización) enlazados al correo y añadir botón "Generar solicitud" en 📧 Correo.

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

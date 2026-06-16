# Generador de Solicitudes de Seguro — AlumnusCare / Rose & Pagés

> Documento de contexto y especificación para construir el proyecto en **Claude Code**.
> Pégale este documento entero a Claude Code al abrir el proyecto, junto con los archivos
> que se indican en la sección **"QUÉ ADJUNTAR"**.

---

## 1. QUÉ ES ESTO Y POR QUÉ

En la oficina recibimos **cotizaciones** de un sistema (HiBroker / PAGÉS) en forma de PDF.
Con esos datos hay que generar la **solicitud oficial** de la aseguradora que corresponda.
Hoy esto se hace a mano, o con un flujo de n8n que da problemas (bucles de correo, rellena
plantilla equivocada, depende de un servidor que se duerme).

**Objetivo:** una herramienta **local y privada** (solo para la oficina, sin exponer a internet,
porque manejamos datos de salud — RGPD) donde:

1. Elijo la aseguradora: **Sanitas**, **Nueva Mutua** o **Generali**.
2. Subo el **PDF de cotización** (el de HiBroker con los datos del asegurado).
3. La herramienta **extrae** los datos, **propone** cómo va a rellenar los campos con criterio,
   yo **confirmo**, y entonces **genera el resultado final**.
4. Descargo el resultado.

**Importante — el resultado final NO es igual en las tres:**

| Aseguradora | Resultado final | Mecanismo |
|-------------|-----------------|-----------|
| **Sanitas** | PDF rellenado | Campos de formulario AcroForm (633 campos con nombre) |
| **Nueva Mutua** | PDF rellenado **menos la firma** (la firma la pone la persona después) | PDF plano → escribir texto encima por coordenadas (overlay) |
| **Generali** | **Un correo electrónico** (asunto + cuerpo), NO un PDF | Plantilla de texto |

### ⚠️ REQUISITO CRÍTICO: el PDF final debe quedar EDITABLE (NO aplanar)  ✅ CONFIRMADO
La usuaria necesita que el PDF de salida (Sanitas y Nueva Mutua) sea **editable**: que la persona
pueda **escribir/corregir campos Y firmar** sobre el propio PDF. La firma debe poder hacerse de
**dos formas**: (a) firma digital/dibujada dentro del PDF en ordenador o móvil, o (b) imprimir,
firmar a mano y escanear. Regla técnica que se deriva de esto:

- **NUNCA aplanar el PDF de salida.** (Aplanar = "quemar" el texto y perder la editabilidad.)
  ⚠️ Los ejemplos `sanitas_verificacion_v2.pdf` y `solicitud_seguro_Mariana_Wyss_Duarte_1.pdf`
  están APLANADOS (0 campos de formulario / texto pintado encima). Sirven como **modelo visual**
  de QUÉ rellenar y DÓNDE, pero el resultado real NO debe aplanarse así.
- **Sanitas:** rellenar los campos AcroForm con pypdf y **dejarlos editables** (no aplanar).
  → Queda editable sin problema. La persona ajusta y firma. ✅ caso fácil.
- **Nueva Mutua:** el PDF original NO tiene campos. Para lograr "editable" hay dos caminos
  (decisión técnica para Claude Code, según calidad del resultado):
  (a) **crear campos de formulario nuevos** por coordenadas y dejarlos editables, o
  (b) pintar el texto pero **añadir al menos un campo/espacio de firma editable**.
  → Lo honesto: Nueva Mutua requiere más ajuste que Sanitas para quedar igual de editable.
- **El espacio de firma SIEMPRE se deja vacío** (la persona firma). En Sanitas, además, la persona
  puede corregir cualquier campo porque quedan editables.

---

## 2. ARQUITECTURA: "CEREBRO" HÍBRIDO (lo más importante)

La clave de todo el proyecto es separar **lo fijo** de **lo variable**:

- **FIJO (determinista, lo hace el código, NUNCA la IA):** valores que son siempre iguales o
  que se calculan con una regla simple. El código no se equivoca ni inventa. Ej: el mediador
  siempre es "Rose & Pagés", el ramo Generali siempre es 16, etc.

- **VARIABLE (con criterio, lo razona Claude vía API y devuelve JSON):** decisiones que
  requieren interpretación. Ej: partir "ofoh Elozino" en nombre/apellido, mapear el cuestionario
  de salud a casillas Sí/No, normalizar una dirección, decidir el código de producto.

**Flujo con confirmación (requisito de la usuaria):**
1. Código extrae texto del PDF de cotización.
2. Claude API recibe el texto + las reglas, y devuelve un **JSON** con los campos variables
   ya razonados Y una lista de "dudas/avisos" si algo falta o es ambiguo.
3. La herramienta **muestra a la usuaria** lo que va a poner (fijo + variable juntos).
4. La usuaria **confirma o corrige**.
5. Recién entonces el código genera el PDF/correo final.

> Nota técnica: la llamada a Claude API ya se usaba en el flujo viejo de n8n para extracción
> estructurada. Aquí se reutiliza la misma idea, pero ordenada dentro del proyecto.

---

## 3. ESTRUCTURA DE PROYECTO SUGERIDA

```
generador-solicitudes/
├── CONTEXTO_PROYECTO.md          ← este documento
├── plantillas/
│   ├── sanitas_blanco.pdf        ← SS_castellano_editable (633 campos AcroForm)
│   ├── nuevamutua_blanco.pdf     ← SOLICITUDESTUDIANTES-TOMADOR (PDF plano)
│   └── (Generali no usa plantilla PDF, usa plantilla de correo en texto)
├── ejemplos/                     ← casos ya resueltos, como referencia (NO subir datos reales al repo)
│   ├── sanitas_isabella.pdf
│   ├── nuevamutua_celine.pdf
│   └── generali_correo_leyan.txt
├── reglas/
│   ├── sanitas.py                ← mapeo de campos + reglas fijas/variables
│   ├── nuevamutua.py             ← coordenadas overlay + reglas
│   └── generali.py               ← plantilla de correo + reglas
├── cerebro/
│   └── prompt_extraccion.py      ← el prompt que se manda a Claude API
├── core/
│   ├── leer_cotizacion.py        ← extrae texto del PDF HiBroker
│   ├── rellenar_sanitas.py       ← pypdf, rellena AcroForm
│   ├── rellenar_nuevamutua.py    ← reportlab overlay
│   └── generar_generali.py       ← arma asunto + cuerpo
├── app.py                        ← interfaz (ver sección 7)
└── requirements.txt
```

---

## 4. DATOS DE ENTRADA: EL PDF DE COTIZACIÓN (HiBroker)

Todas las cotizaciones tienen la misma estructura. Campos que SIEMPRE vienen:

- Nombre (completo, hay que partir en nombre/apellidos)
- Tipo y Número de Documento de Identidad (Pasaporte/NIE/NIF)
- Sexo, Peso (kg), Altura (cm), Fecha de nacimiento
- Teléfono móvil, Teléfono fijo, Correo electrónico
- Dirección, Número, Código Postal, Municipio, País
- **Producto** (esto decide la aseguradora — ver sección 5)
- **Cuestionario de salud** (4 preguntas, con posible detalle si alguna es "Sí")
- **Fecha de inicio de la póliza** / Fecha efecto
- **Método de pago**

### Cómo saber qué aseguradora es (regla de detección por PRODUCTO)
- Producto **ALUMNUSCARE** + logo Generali → **GENERALI**
- Producto **NUEVA_MUTUA_SANITARIA** o "SALUD PROFESIONAL FAMILIA" → **NUEVA MUTUA**
- Producto Sanitas / "Sanitas International Students" → **SANITAS**

> En la herramienta la usuaria igual elige la aseguradora a mano, pero conviene que el código
> AVISE si el producto detectado no coincide con la aseguradora elegida (esto evita justo el
> error que tenía el flujo viejo de mezclar Sanitas con Nueva Mutua).

---

## 5. REGLAS POR ASEGURADORA

### 5.A — GENERALI (resultado = CORREO)  ✅ CONFIRMADO POR LA USUARIA

**ASUNTO:**
```
Emisión: Salud Med: 17704 ({NOMBRE_COMPLETO})
```
- `Emisión: Salud Med: 17704` → **FIJO** (incluido el número 17704)
- `{NOMBRE_COMPLETO}` → **VARIABLE**

**CUERPO:**
```
1# Código Tipología: T1
2# Código Tipo de Petición: ST8
3# Código Entidad/Mediador: 17704
4# Código Peticionario:
5# Mail Peticionario: jcato@pagesseguros.com
6# Teléfono Peticionario:
7# Cliente (DNI) (Opcional):
8# Póliza (RamoCiaPóliza) (Opcional):
9# Aplicación (Opcional):
10# Agrupación Ramo: 16
11# Observaciones:

* Efecto: {FECHA_EFECTO}
* Pago: Anual TDC
* Correo: {CORREO_PERSONA}
* Teléfono: {TELEFONO_PERSONA}
* Dirección: {DIRECCION_PERSONA}

Nota: Emitir con certificado para extranjería.
```

**FIJO (confirmado):**
- Todas las líneas **1# a 10#** completas, tal cual (incluidos los códigos T1, ST8, 17704,
  el mail `jcato@pagesseguros.com`, Ramo 16, y los campos opcionales que van vacíos).
- `* Pago: Anual TDC` → **FIJO 100%**.
- `Nota: Emitir con certificado para extranjería.` → **FIJO**.

**VARIABLE (confirmado, sale de la cotización):**
- `{NOMBRE_COMPLETO}` (asunto)
- `{FECHA_EFECTO}` = **"Fecha de inicio de la póliza"** que aparece en la sección
  **Método de Pago** de la cotización. ⚠️ NO es la "Fecha efecto" de la cabecera.
  (En Leyan: la cabecera ponía 12-06-2026 pero el Efecto correcto es **01/08/2026**.)
- `{CORREO_PERSONA}`
- `{TELEFONO_PERSONA}`
- `{DIRECCION_PERSONA}` (dirección completa tal como viene)

**ADJUNTOS (manual por ahora):** al enviar el correo se adjuntan el **documento de identidad**
y la **carta de aceptación de la universidad**. En la primera versión esto lo hace la usuaria
**a mano**; la herramienta solo genera asunto + cuerpo. Posible automatización futura.

> Ejemplo real (Leyan Ardakani): Efecto 01/08/2026, correo layan.ardakani@gmail.com,
> teléfono +971 0505582131, dirección "Av. de Rodajos, 3, 28223 Pozuelo de Alarcón, Madrid, Spain".

---

### 5.B — NUEVA MUTUA (resultado = PDF plano relleno, SIN firma)  ✅ CONFIRMADO POR LA USUARIA

Producto a contratar: **"SALUD PROFESIONAL FAMILIA sin copago"** → **FIJO**.
Mediador: **ROSE & PAGES** → **FIJO**.
Método de pago: **PAGO POR TARJETA (pasarela, pago anual)** → marcar casilla "x" → **FIJO**.

El PDF NO tiene campos rellenables → hay que **escribir texto encima por coordenadas** (overlay
con reportlab, luego fusionar con pypdf). Calibrar coordenadas una vez con el PDF en blanco;
el ejemplo de Celine sirve de guía visual.

#### Cabecera
- **FECHA ALTA DESEADA** → **VARIABLE** = "Fecha de inicio de la póliza" del formulario
  (la misma lógica que Generali; va en día/mes/año).

#### DATOS DEL TOMADOR
- NOMBRE Y APELLIDOS → **VARIABLE**
- NIF / NIE (documento) → **VARIABLE**
- **DIRECCIÓN → REGLA ESPECIAL (dirección por defecto):**
  - Si el formulario/cotización trae dirección **en España** → se pone esa.
  - Si **NO** trae → valor por defecto de la **oficina**: `Calle Hermosilla 80, piso 2A`, **CP 28001**.
- **POBLACIÓN** → por defecto **Madrid**, pero si la persona estudia en otra ciudad y aparece
  en el formulario (ej. Burgos), se pone la del formulario. → **por defecto Madrid, no fijo absoluto**.
- **PROVINCIA** → mismo criterio (por defecto **Madrid**).
- **CÓDIGO POSTAL** → por defecto **28001**, o el del formulario si aparece otro.
- CORREO ELECTRÓNICO → **VARIABLE**
- TELÉFONO MÓVIL → **VARIABLE**
- TELÉFONO FIJO → solo si lo tiene; si no, **vacío**.
- PROFESIÓN DEL TOMADOR → **vacío** (no hace falta).

#### DIRECCIÓN DE PRESTACIÓN DEL SERVICIO EN ESPAÑA (bloque de abajo)
- Misma lógica que el bloque del tomador: dirección, población, provincia, CP, correo y teléfono.
  Si el formulario los trae, se ponen; si no, valores por defecto de la oficina (Hermosilla 80, 2A,
  Madrid, Madrid, 28001).

#### DATOS DEL ESTUDIANTE
- **TODO VARIABLE**, excepto:
  - **PARENTESCO CON EL TOMADOR** → **FIJO**, siempre escrito literal: **"el mismo"**.
- **SEXO** → marcar con una **X** en HOMBRE o MUJER (sobre las rayitas), según corresponda. (variable)
- NOMBRE Y APELLIDOS, NIF/NIE/PASAPORTE, FECHA DE NACIMIENTO → variables.

#### CUESTIONARIO DE SALUD
- **PESO (kg)** y **ESTATURA (cm)** → **VARIABLE** (vienen del formulario).
- **Casilla SI/NO de enfermedades graves → REGLA CRÍTICA:**
  - Si la persona **NO declaró nada** en el cuestionario de la cotización (las 4 preguntas en "No")
    → marcar **X en el NO** automáticamente.
  - Si la persona **SÍ declaró algo** (alguna pregunta en "Sí") → **NO marcar automáticamente**.
    El "cerebro" debe **DETECTAR el "Sí", AVISAR y PARAR** ese caso para gestión **manual** aparte.
    ⚠️ NUNCA marcar "No" a ciegas si hay algo declarado: marcar un "No" indebido puede perjudicar
    a la persona y dar pie a anulación de póliza por datos inexactos.
- "En caso afirmativo indique cuál" → solo se usa en el caso manual; el automatismo no lo toca.

#### FIRMA Y FECHA (última página)
- **FIRMA** → **VACÍA** (el PDF se envía a la persona para que la firme a mano).
- **FECHA** ("En Madrid, a __ de __ de __") → **VARIABLE** = **la fecha en que se hace la solicitud**
  (la fecha de generación/del día; ej. "Madrid, 12 de junio de 2026"). NO es la fecha de efecto.

---

### 5.C — SANITAS (resultado = PDF con 633 campos AcroForm)  ✅ CONFIRMADO POR LA USUARIA

Se rellena por **nombre de campo** con pypdf (`update_page_form_field_values`).
La plantilla en blanco y el ejemplo relleno comparten EXACTAMENTE los 633 nombres de campo
(verificado). **Solo importan las páginas 1 a 4.** Las páginas 5-9 son asegurados adicionales
(mismo patrón con sufijos distintos) y normalmente no se usan si hay un solo asegurado.

> ⚠️ USAR COMO MODELO VISUAL `sanitas_verificacion_v2.pdf` (NO el de Isabella). El v2 corrige
> los errores de Isabella: el producto "Sanitas International Students" está en su campo correcto
> ("Nombre del producto a contratar", arriba), no en póliza anterior; consentimientos marcados;
> cuestionario de salud todo en "No". PERO al v2 le FALTA rellenar las **preguntas a efectos
> estadísticos** de la página 4 (fumador "No", alcohol "No", calidad de sueño "Regular, depende
> del día"). Eso hay que añadirlo. (Nota: el v2 está aplanado; ver requisito de PDF editable arriba.)
> Los nombres internos de los 633 campos están en `sanitas_campos_mapeo.json`.

#### PÁGINA 1 — A rellenar por el mediador (FIJO)
- `asegurados` = **"1"** (número de asegurados a incluir) → FIJO
- **Nombre del producto a contratar** = **"Sanitas International Students"** → FIJO
  ⚠️ TAREA CLAUDE CODE: localizar el **campo interno correcto** de "Nombre del producto a contratar".
  En el ejemplo de Isabella estaba MAL puesto en el campo `pto. anterior` (póliza anterior).
  Hay que ponerlo en el campo de producto y dejar `pto. anterior` **vacío** (salvo póliza anterior real).
- `Nueva póliza` = "/On" → FIJO
- `mediador` = **"Rose & Pagés"** → FIJO
- `Corredor` = "/On" (tipo de mediador) → FIJO
- `codigo mediador` = **"30149"** → FIJO  (confirmado 30149, cinco dígitos)
- `Anual` = "/On" (frecuencia de pago) → FIJO
- **Datos bancarios** (IBAN/cuenta/BIC) → **VACÍO**, no se rellena nada.
- **Enviar documentación a** → `El Mediador` = "/On" → FIJO; el resto de ese bloque vacío.

#### PÁGINA 1 — Datos del tomador (VARIABLE)
- `nombre tomador`, `numero documento` + tipo (`Pasaporte`/`NIF`/`NIE` = "/On"),
  sexo (`Mujer`/`Hombre` = "/On"), nacimiento (`dia2`,`mes2`,`año2`), `nacionalidad`,
  `movil1`, `movil2`, `email` → VARIABLE.
- fecha efecto: `mes1`, `año1` (el día "01" viene preimpreso) → VARIABLE (de "Fecha inicio de póliza").
- **Domicilio** → MISMA REGLA que Nueva Mutua (dirección por defecto de oficina):
  `domicilio tomador` = "Calle Hermosilla 80", `domicilio tomador n` = "PISO 2 A",
  `municipio tomador` = "Madrid", `cp tomador` = "28001", `provincia tomador` = "Madrid"
  **SI no viene dirección en la cotización**. Si viene otra (ej. estudia en Burgos), se pone la del formulario.

#### PÁGINA 2 → NO se rellena NADA (solo información legal).

#### PÁGINA 3 — Consentimientos de datos → **MARCAR "No Consiento" en las TRES casillas**.
- En el ejemplo solo había 2 (`No Consiento`, `No Consiento_2`). La usuaria quiere **las tres**.
  ⚠️ TAREA CLAUDE CODE: identificar la tercera casilla "No Consiento" y marcarla también.

#### PÁGINA 4 — Datos del asegurado (lo importante)
- `nueva poliza30` = "/On" → FIJO
- `parentesco10` = **"el mismo"** → FIJO
- Datos del asegurado → VARIABLE: `nombre asegurado pag310`, sexo (`Mujer_210`/`Hombre…`),
  nacimiento (`día_410`,`mes_510`,`año_510`), `movil1 pag310`, `movil2 pag310`,
  `Teléfono 2_210` (email), `nacionalidado210`, `num doc10`, tipo doc (`Pasaporte_211`="/On"),
  `peso10`, `estatura10`, fecha efecto (`mes_610`,`año_610`).
- **Dos preguntas de la izquierda** (efectos estadísticos: fumador / alcohol) → marcar **NO** ambas → FIJO.
- **Preguntas a efectos estadísticos** → todas **No**; **calidad de sueño** → **"Regular, depende del día"** → FIJO.
- **Cuestionario de salud (6 preguntas Sí/No)** → **REGLA CRÍTICA igual que Nueva Mutua**:
  - Si NO declaró nada → marcar **No** en todas.
  - Si declaró algo (algún "Sí" en la cotización) → **NO marcar a ciegas; PARAR y AVISAR** para gestión manual.
  ⚠️ Los nombres internos de estas casillas son confusos (`Sí_510`, `Sís_510`, `Sí_x510`,
  `No_630a`, `No_6301`...): unos dicen "Sí" pero valen "/No". TAREA CLAUDE CODE: casar cada
  casilla con su pregunta REAL **por posición/coordenadas** abriendo el PDF, no fiarse del nombre.

#### Firma y fecha
- Firma → vacía (la firma la pone la persona; igual que Nueva Mutua — confirmar fecha con la usuaria
  cuando se implemente: en el ejemplo había fechas 12/06/2026 en `dia2 firma`/`mes2 firma`/`año2 firma`,
  `día_3`/`mes_4`/`año_4`, `día_730`/`mes_730`/`año_730` → probablemente la fecha de la solicitud).

---

## 6. EL "CEREBRO" — QUÉ LE PEDIMOS A CLAUDE API

`cerebro/prompt_extraccion.py` debe mandar a Claude API el **texto de la cotización** y pedir
un **JSON** con esta forma (ejemplo), incluyendo razonamiento sobre lo variable:

```json
{
  "aseguradora_detectada": "GENERALI | NUEVA_MUTUA | SANITAS",
  "nombre_completo": "Leyan Ardakani",
  "nombre": "Leyan",
  "apellidos": "Ardakani",
  "tipo_documento": "Pasaporte",
  "numero_documento": "U0628801",
  "sexo": "Mujer",
  "peso_kg": "64",
  "altura_cm": "163",
  "fecha_nacimiento": "12/02/2007",
  "telefono_movil": "+971 0505582131",
  "correo": "layan.ardakani@gmail.com",
  "direccion_origen": "Av. de Rodajos, 3, 28223 Pozuelo de Alarcón, Madrid, Spain",
  "direccion_espana": "...",
  "municipio": "Pozuelo de Alarcón",
  "provincia": "Madrid",
  "codigo_postal": "28223",
  "fecha_efecto": "01/08/2026",
  "metodo_pago": "Tarjeta de Débito/Crédito",
  "cuestionario_salud": {
    "tiene_algun_si": true,
    "resumen_para_formulario": "Cirugía a los 8 años por úlceras; 2 hospitalizaciones por infección bacteriana a los 13/14",
    "detalle_original": "At 8 years old i had a surgery..."
  },
  "avisos": [
    "La pregunta 2 del cuestionario es 'Sí' → en Nueva Mutua marcar SÍ y detallar.",
    "Falta teléfono peticionario (campo opcional de Generali)."
  ]
}
```

**Reglas que el prompt debe imponer a Claude:**
- No inventar datos. Si un campo no está, dejarlo vacío y añadir un aviso.
- Fechas siempre en dd/mm/aaaa.
- Separar nombre y apellidos con sentido (apellidos = lo último; ante la duda, avisar).
- Para Nueva Mutua, distinguir dirección de origen vs. dirección de prestación en España.
- Resumir el cuestionario de salud de forma fiel pero apta para una casilla corta.

---

## 7. INTERFAZ Y DÓNDE VIVE LA HERRAMIENTA  ✅ CONFIRMADO POR LA USUARIA

**Decisión:** aplicación **privada de escritorio**, **sin internet, sin dominio, sin servidor,
sin login complicado**. Cada persona del equipo (la usuaria y sus socios) debe poder usarla.
Nada sale del ordenador (importante por RGPD: datos de salud).

Dos formas posibles de distribución (que Claude Code decida/proponga cuando llegue el momento):
- **Forma 1 — instalada en el ordenador de cada socio.** Cada uno la abre localmente. 100% privada.
  Pega: actualizar una regla obliga a actualizar en cada equipo.
- **Forma 2 — en una carpeta compartida del equipo** (Google Drive / OneDrive / red de oficina).
  Cada uno la abre desde ahí; se actualiza en un solo sitio. Suele ser la más cómoda para equipo pequeño.

> NO desplegar como web pública. NO comprar dominio. NO montar servidor. Eso queda descartado
> por decisión de la usuaria. El "acceso para cada uno" se logra con la Forma 1 o 2, no con internet.

**Interfaz sugerida:** app local con **Streamlit** (`streamlit run app.py`, se abre en el navegador
en `localhost` — sigue siendo local, no es una web pública) o, si se prefiere algo instalable tipo
programa, una app de escritorio simple. Claude Code recomendará lo más fácil de mantener.

La pantalla de **confirmación** (paso 3 del flujo) es obligatoria: mostrar tabla
"Campo → Valor propuesto (fijo/variable)" y dejar editar antes de generar.

### Futuro (NO ahora, solo dejar la puerta abierta)
- **Chatbot** encima de la herramienta: se contempla MÁS ADELANTE. Primero que funcione el generador.
- Si algún día se quiere acceso remoto o el chatbot, se evaluará despliegue entonces. Construir
  ahora con código ordenado y modular es lo que permite añadir eso después sin rehacer nada.

---

## 8. SEGURIDAD / RGPD (importante)
- Todo local. No subir a internet. No commitear PDFs con datos reales al repositorio.
- La API key de Claude va en variable de entorno (`.env`), nunca en el código.
- Carpeta de salidas local; borrar lo que no haga falta.

---

## 9. ORDEN DE TRABAJO SUGERIDO PARA CLAUDE CODE
1. Montar estructura + `requirements.txt` (pypdf, reportlab, pdfplumber, anthropic, streamlit, python-dotenv).
2. `core/leer_cotizacion.py` + `cerebro/` → extraer JSON de una cotización y enseñarlo.
3. **Generali** primero (es el más fácil: solo texto de correo). Validar con el caso Leyan.
4. **Sanitas** (rellenar AcroForm con el mapeo de la sección 5.C). Validar contra Isabella.
5. **Nueva Mutua** (overlay por coordenadas, lo más laborioso). Validar contra Celine.
6. Interfaz Streamlit con el paso de confirmación.
7. Aviso de incoherencia producto↔aseguradora.

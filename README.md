# Control Fuerza — Juan

App en Streamlit para ayudar a Juan (PF de gimnasio, AFA Internacional / Santa
Perpètua) a armar la sesión de fuerza de cada categoría, a partir del
historial real de rutinas ya hechas.

## Qué hace

1. Arriba de todo, muestra qué categorías tienen gym programado hoy según la
   planilla de horarios ("GYM 26-27").
2. Juan elige una categoría (por defecto, una de las que le tocan hoy).
3. La app arma la propuesta de hoy repitiendo, para cada uno de los 4
   ejercicios, el mismo que se usó la última vez para esa categoría (no
   inventa ejercicios ni combinaciones nuevas — la variedad la decide Juan
   editando a mano cuando quiere cambiar algo).
4. Ajusta reps y kilos según una progresión ondulante semana a semana, pero
   **solo si el día de la semana coincide** con el de la última vez que se
   hizo esa rutina (si la categoría cambió de día, se trata como rutina
   nueva, sin ajuste):
   - Semana par (2, 4, 6...): +2 reps si el ejercicio es troncal, +1 si es
     auxiliar (según el patrón de movimiento, `src/catalog.py`), mismo
     kilaje.
   - Semana impar ≥ 3 (3, 5, 7...): las reps vuelven a la línea base de la
     semana 1, y sube el kilaje (+5%, redondeado a 2.5kg) — solo si la carga
     anterior es un peso claro en kg.
   - Este seguimiento es por ejercicio individual, no por pareja: si solo
     cambia el auxiliar, el troncal sigue su propia progresión sin cortarse.
5. Cada ejercicio muestra un cartel explicando el ajuste aplicado. Si Juan
   edita el ejercicio a mano en la tabla, ese cartel desaparece (la
   continuidad ya no aplica para ese ejercicio).
6. Cuando Juan confirma, la sesión ejecutada se guarda en un Google Sheet
   propio de la app (`registro_sesiones`), que después alimenta las próximas
   propuestas.

No usa IA generativa para decidir la propuesta: es lógica de reglas explícita
(ver `src/engine.py`), así el motivo de cada sugerencia es siempre trazable.

## Estructura

```
app.py                    # UI de Streamlit
src/parser.py             # Lee las hojas "MICRO N" del Sheet de gimnasio (historial)
src/schedule_parser.py    # Lee la planilla de horarios "GYM 26-27"
src/catalog.py            # Catálogo de ~100 ejercicios, tageados por patrón y troncal/auxiliar
src/engine.py             # Reglas de progresión semanal (reps/kilos) por ejercicio
src/data_source.py        # Conexión a Google Sheets (lectura y escritura)
src/ui.py                 # Overlay de carga (vidrio esmerilado)
tests/                    # Tests con datos reales de ejemplo
```

## Puesta en marcha (una sola vez)

### 1. Crear la cuenta de servicio de Google (gratis)

Esto le da a la app permiso para leer/escribir Sheets sin que Juan tenga que
loguearse con ninguna cuenta.

1. Entrá a https://console.cloud.google.com/ con la cuenta
   `nicolassanalitro@institutovelez.edu.ar`.
2. Creá un proyecto nuevo (arriba a la izquierda, selector de proyecto →
   "Proyecto nuevo"). Nombre sugerido: `control-fuerza-juan`.
3. Con el proyecto seleccionado, andá a **APIs y servicios → Biblioteca** y
   habilitá estas dos APIs (buscalas por nombre y tocá "Habilitar"):
   - **Google Sheets API**
   - **Google Drive API**
4. Andá a **APIs y servicios → Credenciales → Crear credenciales → Cuenta de
   servicio**.
   - Nombre: `control-fuerza-juan-app`
   - No hace falta asignarle ningún rol de proyecto — el acceso se maneja
     compartiendo cada Sheet directamente con ella (paso 3 de abajo).
5. Entrá a la cuenta de servicio recién creada → pestaña **Claves** → **Agregar
   clave → Crear clave nueva → JSON** → se descarga un archivo `.json`.
   - **No subas nunca este archivo a GitHub.**
6. Copiá el email de la cuenta de servicio (algo como
   `control-fuerza-juan-app@control-fuerza-juan.iam.gserviceaccount.com`,
   está tanto en la lista de cuentas de servicio como dentro del JSON, campo
   `client_email`).

### 2. Compartir los Google Sheets con la cuenta de servicio

- Abrí **PLANIFICACION FUERZA** (temporada 25-26, ya cerrada) → Compartir →
  pegá el email de la cuenta de servicio → permiso **Lector** (solo hace
  falta leerla).
- Abrí **PLANIFICACION DE FUERZA 26-27** (temporada actual) → Compartir →
  pegá el email de la cuenta de servicio → permiso **Editor**. La app va a
  leer las pestañas "MICRO N" igual que la anterior, y además va a crear ahí
  su propia pestaña nueva `registro_sesiones` la primera vez que Juan
  confirme una sesión — nunca toca las pestañas "MICRO N" que se llenan a
  mano.
- Abrí **GYM 26-27** (la planilla de horarios, hoja "GYM") → Compartir →
  pegá el email de la cuenta de servicio → permiso **Lector** (solo hace
  falta leerla, para el cartel de "a quién le toca hoy").

No hace falta crear ningún Google Sheet nuevo: todo queda dentro de las
planillas que ya existen.

### 3. Cargar los secretos

Copiá `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y
completá `[gcp_service_account]` con todos los campos del archivo `.json`
descargado en el paso 1 (es un copy-paste directo, campo por campo). Los IDs
de `[sheets]` ya vienen cargados correctamente, no hace falta tocarlos.

En Streamlit Community Cloud, este mismo contenido va en
**App → Settings → Secrets** (no se sube el archivo, se pega el texto).

### 4. Probar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Modo de desarrollo sin Google Sheets:** si en `.streamlit/secrets.toml` ponés
una sección `[dev] local_fixture_path = "tests/fixtures/micro40_sample.txt"`,
la app usa ese archivo local como historial en vez de conectarse a Google
(no hace falta `[gcp_service_account]` en ese caso). Sirve para probar
cambios en la propuesta sin tocar las planillas reales. No pongas esta
sección en los secrets de producción.

### 5. Desplegar gratis en Streamlit Community Cloud

1. Subí este repo a GitHub (puede ser privado).
2. Entrá a https://share.streamlit.io/ con tu cuenta de GitHub.
3. "New app" → elegí el repo, la rama, y `app.py` como archivo principal.
4. Pegá los secretos (paso 3) en Settings → Secrets antes o después del
   primer deploy.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Los tests corren contra fragmentos reales del historial (`tests/fixtures/`),
sin necesidad de conexión a Google Sheets.

## Roadmap (fuera del alcance de esta primera versión)

- Ejercicios de fuerza fuera del gimnasio.
- Sustituir automáticamente un ejercicio por otro del mismo patrón de
  movimiento cuando una categoría tiene muy poco historial propio (ya está el
  catálogo tageado en `src/catalog.py` con patrón y rol troncal/auxiliar,
  falta usarlo como fallback en el motor).

# Especificaciones — Sistema de Relevamiento Emaús

**Versión:** 1.0  
**Fecha:** Junio 2026  
**Estado:** Borrador para revisión

---

## 1. Contexto y objetivo

Reemplazar el sistema de relevamiento semestral basado en Google Sheets por una aplicación web centralizada. Actualmente cada Emaús recibe una planilla individual con cuatro secciones; los datos se consolidan manualmente para alimentar un tablero en Looker Studio.

El nuevo sistema debe:
- Centralizar la carga en un único formulario web por Emaús
- Gestionar estados del relevamiento (borrador → enviado → validado)
- Proveer un tablero propio con los mismos indicadores del tablero actual, más capacidad de filtrado granular
- Permitir actualización periódica del padrón de establecimientos educativos del Ministerio

---

## 2. Contexto del dominio

**Jerarquía organizacional:** Diócesis → Emaús → (Espacios Educativos + Pastoral PI + Talleres + Establecimientos)

- Hay aproximadamente **40 Emaús**
- Cada Emaús tiene **una sola Pastoral de Primera Infancia**
- Cada Emaús tiene **uno o más Espacios Educativos**
- Los talleres y establecimientos articulados se registran **a nivel Emaús**
- El relevamiento es **semestral** (snapshot completo por período)
- Los datos de infraestructura/ubicación persisten entre semestres; el resto se releva nuevamente

---

## 3. Alcance

### Dentro del alcance
- Formulario web de carga para ATLs (4 secciones por Emaús)
- Panel de validación para Responsables de grupo
- Panel de administración (Admin)
- Tablero de indicadores
- Carga y actualización del padrón de establecimientos (64.606 registros, actualización periódica vía Excel)
- Autenticación con roles

### Fuera del alcance (v1)
- App móvil
- Notificaciones automáticas por email
- Integración con Looker Studio (el tablero es propio)

---

## 4. Roles y permisos

| Rol | Descripción | Permisos |
|-----|-------------|----------|
| **ATL** | Asistente Técnico Local. Uno por Emaús. | Crear y editar el relevamiento de su Emaús hasta enviarlo. Ver su propio historial. |
| **Responsable** | Supervisa un grupo de Emaús (4 responsables en total). Sus Emaús asignados pueden cambiar esporádicamente (admin los reasigna). | Ver y validar relevamientos de sus Emaús asignados. Rechazar con comentario. |
| **Admin** | Gestión global del sistema. | Todo: usuarios, asignaciones, padrón, todos los relevamientos, tablero completo. |

---

## 5. Flujo principal

```
ATL abre relevamiento del período
  → completa las 4 secciones (puede guardar borrador)
  → envía (estado: borrador → enviado)

Responsable ve relevamientos enviados de sus Emaús
  → valida (estado: enviado → validado)
  → o rechaza con comentario (estado: enviado → borrador, ATL puede editar y reenviar)

Admin puede forzar cambio de estado en cualquier punto
```

**Regla de período:** solo puede haber un relevamiento por Emaús por período (semestre + año). El sistema impide crear un segundo relevamiento para el mismo período.

**Pre-carga de datos de base:** al iniciar un nuevo relevamiento, el sistema pre-carga los datos de infraestructura y ubicación del período anterior para que el ATL solo confirme o modifique lo que cambió.

---

## 6. Estructura del formulario

El formulario tiene 4 secciones, navegables con guardado parcial en cada una.

### 6.1 Pastoral Primera Infancia
Una por Emaús por período. Incluye:
- Años de desarrollo de la pastoral en la diócesis
- Si presentaron la metodología a otras comunidades
- Comunidades sin pastoral activa (cantidad)
- Cantidad de capacitadoras y líderes
- Personas acompañadas (por rango etario y condición)
- Enfermedades más frecuentes en niños/as y en embarazadas (selección de lista + campo libre "Otra")
- Alfabetización de líderes y madres
- Acciones de líderes (celebración de vida, visita domiciliaria, reunión de evaluación) con frecuencia y cantidad semestral
- Temáticas abordadas en el semestre (selección múltiple + cantidad de comunidades donde se abordó)
- Articulaciones con organizaciones e instituciones (selección múltiple)

### 6.2 Espacios Educativos
Uno o más por Emaús. Por cada espacio:

**Datos de base** (persisten entre semestres, pre-cargados desde el relevamiento anterior):
- Nombre, dirección, geolocalización, RENABAP
- Titularidad y nombre del titular
- Material de construcción, rampa de acceso, tipo de acceso principal
- Ambientes disponibles (cocina, salón comedor, despensa, baño, espacio de recreación)
- Servicios básicos (cloacas, electricidad, agua, residuos, telefonía, internet, combustible)
- Equipamiento de cocina (cocina industrial/familiar, mechero, heladeras, freezers)
- Equipamiento informático (monitores, PCs, notebooks, tablets, impresoras)
- Zona (urbana, periférica, rural, inundable, sin transporte)

**Datos semestrales:**
- Asistentes por rango etario (0-6, 7-14, 15-24, 25-35, 35-50, más de 50)
- Acciones por eje (Primera Infancia / Trayectorias educativas / Integración comunitaria / Nuevas tecnologías / Salud integral) — listado completo de acciones con checkbox ¿Tiene?
- Apoyo escolar primario (cantidad, frecuencia, contenidos)
- Apoyo escolar secundario (cantidad, frecuencia, contenidos)
- Becas Familiares (cantidad por nivel educativo, asignaciones, discapacidad, CUD)
- Becas Terciarias/Universitarias (regulares, egresados, abandonos y motivos)
- Propuesta de Alfabetización (cantidad por rango etario, alfabetizadores, frecuencia)
- Propuesta DALE (cantidad por rango etario, educadores, frecuencia semanal)
- Itinerancia (si se realizó, frecuencia, tipos de espacio, actividades, roles a cargo)
- Alfabetización digital (acceso a internet, talleres realizados por tipo)
- Grupo motor (cantidad, frecuencia de reunión, roles)
- Articulación con instituciones de nivel superior (nombre, tipo de acciones)
- Necesidades de infraestructura prioritarias (selección de hasta 3)
- Preocupaciones sobre adolescentes/jóvenes (ranking del 1 al 8)
- Adolescentes referentes (cantidad y frecuencia de reunión)

### 6.3 Talleres
Lista de talleres del semestre a nivel Emaús. Por cada taller:
- Eje temático
- Temática específica
- Cantidad de participantes
- Cantidad de EE involucrados
- Cantidad de comunidades PI involucradas
- Otras instituciones/espacios participantes
- Perfil de los capacitadores

### 6.4 Establecimientos educativos articulados
Selección de establecimientos del padrón oficial del Ministerio con los que el Emaús articuló en el semestre. Por cada establecimiento seleccionado:
- Tipo de acción (una o más): institución a la que asisten, articulación por alfabetización, seguimiento a estudiantes, intercambio por problemáticas barriales, otros (con detalle)

---

## 7. Modelo de datos

### Tablas maestras

```sql
diocesis (id, nombre, provincia)

emaus (id, diocesis_id, nombre, direccion, geolocalizacion, renabap, frecuencia_acciones, activo)

usuarios (id, emaus_id, nombre, apellido, email, password_hash, rol ENUM('atl','responsable','admin'), activo, creado_en)

responsable_emaus (responsable_id, emaus_id)
-- tabla de asignación; el admin gestiona esta relación

catalogo (id, categoria, valor, activo, orden)
-- gestión centralizada de listas desplegables desde admin
-- categorías: enfermedad_ninos, enfermedad_embarazadas, tematica_pi,
--             articulacion, eje_accion, necesidad_infra, preocupacion_joven
```

### Relevamiento

```sql
relevamiento (
  id, emaus_id, atl_id,
  anio INT,
  semestre ENUM('1','2'),
  estado ENUM('borrador','enviado','validado','rechazado'),
  comentario_rechazo TEXT,
  creado_en, enviado_en, validado_en
)
-- UNIQUE KEY (emaus_id, anio, semestre)
```

### Pastoral PI

```sql
pastoral_pi (
  id, relevamiento_id,
  anios_desarrollo INT,
  presento_metodologia BOOLEAN,
  comunidades_sin_pastoral INT,
  capacitadoras INT, lideres INT,
  madres_embarazadas_12_18 INT, madres_embarazadas_19_29 INT, madres_embarazadas_30_mas INT,
  madres_no_embarazadas INT, ninos_0_3 INT, ninos_4_6 INT, familias INT,
  lideres_todas_alfabetizadas BOOLEAN, lideres_no_alfabetizadas_cantidad INT, lideres_en_alfabetizacion BOOLEAN,
  madres_todas_alfabetizadas BOOLEAN, madres_no_alfabetizadas_cantidad INT, madres_en_alfabetizacion BOOLEAN
)

-- Tablas separadas para filtros/estadísticas en tablero:
pastoral_pi_enfermedad_ninos (id, pastoral_pi_id, enfermedad, enfermedad_otra, orden TINYINT)
pastoral_pi_enfermedad_embarazadas (id, pastoral_pi_id, enfermedad, enfermedad_otra, orden TINYINT)
pastoral_pi_accion_lider (id, pastoral_pi_id, accion ENUM('celebracion_vida','visita_domiciliaria','reunion_evaluacion'), realiza BOOLEAN, frecuencia, cantidad_semestre INT)
pastoral_pi_tematica (id, pastoral_pi_id, tematica, tematica_otra, comunidades_cantidad INT)
pastoral_pi_articulacion (id, pastoral_pi_id, organizacion, organizacion_otra)
```

### Espacios Educativos

```sql
-- Datos de base (persisten entre semestres)
espacio_educativo (
  id, emaus_id, nombre, direccion, geolocalizacion, renabap,
  titularidad, nombre_titular, construccion_material, rampa_acceso, acceso_principal, activo
)

-- Tablas de datos de base detallados (también persisten)
ee_ambiente (id, espacio_educativo_id, ambiente, tiene BOOLEAN, cantidad INT)
ee_servicio (id, espacio_educativo_id, servicio, valor)
ee_equipo_cocina (id, espacio_educativo_id, equipo, tiene BOOLEAN)
ee_equipo_informatico (id, espacio_educativo_id, equipo, cantidad INT)

-- Datos semestrales
relevamiento_ee (
  id, relevamiento_id, espacio_educativo_id,
  -- Asistentes por edad
  asistentes_0_6, asistentes_7_14, asistentes_15_24, asistentes_25_35, asistentes_35_50, asistentes_mas_50,
  -- Grupo motor
  grupo_motor_cantidad, grupo_motor_frecuencia,
  -- Adolescentes
  adolescentes_referentes, adolescentes_frecuencia,
  -- Itinerancia
  itinerancia_realizo BOOLEAN, itinerancia_frecuencia,
  -- Digital
  internet_acceso BOOLEAN, internet_falta_motivo, jornadas_formacion_digital BOOLEAN,
  -- Nivel superior
  articula_nivel_superior BOOLEAN, nivel_superior_cantidad,
  -- Becas Familiares
  bf_apoyo_escolar, bf_nivel_inicial, bf_primaria, bf_secundaria, bf_asignaciones, bf_discapacidad, bf_cud,
  -- Becas Terciarias
  btu_regulares, btu_egresados, btu_abandonaron,
  -- Apoyo escolar primario
  apoyo_primario_ninos, apoyo_primario_frecuencia, apoyo_primario_contenido_principal,
  -- Apoyo escolar secundario
  apoyo_secundario_adolescentes, apoyo_secundario_frecuencia, apoyo_secundario_contenido_principal,
  -- Alfabetización
  alfa_total, alfa_6_9, alfa_10_14, alfa_15_24, alfa_25_mas, alfa_alfabetizadores, alfa_frecuencia,
  -- DALE
  dale_total, dale_6_9, dale_10_14, dale_15_24, dale_25_mas, dale_educadores, dale_frecuencia_dias
)

-- Tablas separadas para filtros en tablero
relevamiento_ee_accion (id, relevamiento_ee_id, eje, accion, tiene BOOLEAN)
relevamiento_ee_necesidad_infra (id, relevamiento_ee_id, necesidad, orden TINYINT)
relevamiento_ee_preocupacion_joven (id, relevamiento_ee_id, preocupacion, ranking TINYINT)
relevamiento_ee_nivel_superior (id, relevamiento_ee_id, nombre_institucion, tipo_acciones)
relevamiento_ee_btu_abandono_motivo (id, relevamiento_ee_id, motivo)
relevamiento_ee_apoyo_primario_contenido (id, relevamiento_ee_id, contenido)
relevamiento_ee_apoyo_secundario_contenido (id, relevamiento_ee_id, contenido)
relevamiento_ee_itinerancia_espacio (id, relevamiento_ee_id, espacio, espacio_otro)
relevamiento_ee_itinerancia_actividad (id, relevamiento_ee_id, actividad)
relevamiento_ee_itinerancia_rol (id, relevamiento_ee_id, rol, rol_otro, cantidad)
relevamiento_ee_digital_taller (id, relevamiento_ee_id, taller)
relevamiento_ee_grupo_motor_rol (id, relevamiento_ee_id, rol, rol_otro, cantidad)
relevamiento_ee_ubicacion_zona (id, relevamiento_ee_id, zona)
```

### Talleres

```sql
taller (
  id, relevamiento_id, eje, tematica,
  cantidad_participantes, cantidad_ee, cantidad_comunidades_pi,
  otras_instituciones, perfil_capacitadores
)
```

### Establecimientos educativos

```sql
-- Padrón oficial del Ministerio de Educación
-- 64.606 registros, 24 jurisdicciones, todo el país
-- Actualización periódica: upsert por cueanexo desde panel admin
establecimiento_estado (
  id, cueanexo UNIQUE,
  jurisdiccion, sector, ambito,
  departamento, cod_departamento,
  localidad, cod_localidad,
  nombre, domicilio, codigo_postal, telefono, mail,
  nivel_inicial_maternal BOOLEAN, nivel_inicial_infantes BOOLEAN,
  primario BOOLEAN, secundario BOOLEAN, adultos BOOLEAN,
  formacion_profesional BOOLEAN, alfabetizacion BOOLEAN,
  actualizado_en DATE
)

-- Articulaciones por relevamiento
establecimiento_articulado (
  id, relevamiento_id, establecimiento_id,
  accion_institucion BOOLEAN, accion_articulacion_alfa BOOLEAN,
  accion_seguimiento BOOLEAN, accion_intercambio BOOLEAN,
  accion_otros BOOLEAN, detalle_otros TEXT
)
```

---

## 8. Stack técnico

| Capa | Tecnología |
|------|------------|
| Frontend | HTML + JS estático (sin framework) |
| Hosting frontend | Netlify → `emaus.netlify.app` |
| Backend | FastAPI + Mangum |
| Deploy backend | AWS Lambda + API Gateway |
| Base de datos | TiDB Cloud Starter (MySQL-compatible, free tier, 25GB) |
| ORM | SQLAlchemy + PyMySQL |
| Autenticación | JWT (python-jose) + bcrypt (passlib) |
| Tablero | Dashboard HTML estático servido desde la misma API |
| Cliente de DB | DBeaver (conexión vía driver MySQL a TiDB) |

---

## 9. API — endpoints principales

### Auth
```
POST /auth/login          → token JWT (OAuth2PasswordRequestForm)
```

### Relevamientos
```
GET  /relevamientos                          → lista según rol
POST /relevamientos                          → crear nuevo (valida unicidad período)
GET  /relevamientos/{id}                     → detalle completo
PUT  /relevamientos/{id}/estado              → enviar / validar / rechazar
```

### Secciones del formulario (guardado parcial por sección)
```
GET  /relevamientos/{id}/pastoral-pi
PUT  /relevamientos/{id}/pastoral-pi

GET  /relevamientos/{id}/espacios-educativos
POST /relevamientos/{id}/espacios-educativos
PUT  /relevamientos/{id}/espacios-educativos/{ee_id}

GET  /relevamientos/{id}/talleres
POST /relevamientos/{id}/talleres
PUT  /relevamientos/{id}/talleres/{taller_id}
DELETE /relevamientos/{id}/talleres/{taller_id}

GET  /relevamientos/{id}/establecimientos
PUT  /relevamientos/{id}/establecimientos
```

### Admin
```
GET  /admin/usuarios
POST /admin/usuarios
PUT  /admin/usuarios/{id}

GET  /admin/responsable-emaus
PUT  /admin/responsable-emaus/{responsable_id}

POST /admin/padron/importar        → upsert desde Excel por cueanexo
GET  /admin/padron/estado          → fecha última actualización, total registros

GET  /admin/catalogos/{categoria}
POST /admin/catalogos
PUT  /admin/catalogos/{id}
```

### Tablero
```
GET /tablero/resumen
GET /tablero/pastoral-pi
GET /tablero/espacios-educativos
GET /tablero/talleres
GET /tablero/establecimientos
```
Todos aceptan filtros: `?anio=&semestre=&diocesis_id=&emaus_id=`

---

## 10. Gestión del padrón de establecimientos

- **Fuente:** Padrón Oficial de Establecimientos Educativos (Ministerio de Educación Nacional)
- **Formato:** Excel con encabezados en fila 13 (fila 12 = categorías, fila 13 = columnas)
- **Registros:** 64.606 establecimientos, 24 jurisdicciones
- **Clave única:** `cueanexo` (identificador del Ministerio)
- **Actualización:** Admin sube nuevo Excel → upsert por `cueanexo` → nuevos se insertan, existentes se actualizan, ninguno se elimina automáticamente
- **Auditoría:** cada importación registra fecha, usuario, total procesados, insertados, actualizados

---

## 11. Tablero — indicadores principales

**Pastoral PI**
- Total de personas acompañadas por diócesis / Emaús / período
- Distribución por rango etario y condición
- Enfermedades más frecuentes (ranking)
- Cobertura de temáticas abordadas
- Articulaciones institucionales

**Espacios Educativos**
- Asistentes totales por rango etario
- Presencia de acciones por eje
- Becas familiares y terciarias: totales y evolución semestral
- Apoyo escolar: cobertura y contenidos más frecuentes
- Necesidades de infraestructura prioritarias (ranking agregado)
- Conectividad y equipamiento informático
- Preocupaciones sobre jóvenes (ranking agregado)

**Talleres**
- Talleres por eje y temática
- Total de participantes por período

**Establecimientos**
- Articulaciones por jurisdicción/localidad
- Tipo de acciones más frecuentes

---

## 12. Decisiones de diseño

**Catálogos en base de datos:** las listas desplegables del formulario se gestionan como registros en la tabla `catalogo`. Agregar o quitar una opción (ej: una enfermedad) es una operación de admin en el panel, sin modificar código ni hacer deploy.

**Datos de base vs. semestrales en EE:** `espacio_educativo` almacena datos que cambian raramente. `relevamiento_ee` almacena los datos semestrales. Al crear un nuevo relevamiento, el sistema pre-carga los datos de base del último relevamiento disponible.

**Tablas separadas en lugar de JSON:** los campos con múltiples valores (enfermedades, temáticas, articulaciones, acciones por eje, etc.) se almacenan en tablas separadas para facilitar filtros, conteos y estadísticas en el tablero.

**Upsert del padrón por `cueanexo`:** garantiza idempotencia en actualizaciones sucesivas.

**Unicidad de relevamiento:** `UNIQUE KEY (emaus_id, anio, semestre)` previene duplicados a nivel de base de datos.

**Estado `rechazado`:** vuelve el relevamiento a `borrador`; el comentario del Responsable queda visible para el ATL al reabrir el formulario.

**Seguridad (repo público):**
- Credenciales nunca en el código: `.env` local, variables de entorno en Lambda y Netlify
- CORS restringido a `emaus.netlify.app` en producción
- Docs de FastAPI (`/docs`) deshabilitados en producción
- JWT con expiración de 8 horas
- Passwords con bcrypt

---

## 13. Estado actual del desarrollo

### Completado
- [x] Estructura de carpetas (`backend/` + `frontend/`)
- [x] `backend/app/config.py` — configuración por variables de entorno
- [x] `backend/app/database.py` — conexión SQLAlchemy a TiDB
- [x] `backend/app/models/` — Usuario, Emaus, Diocesis, ResponsableEmaus, Relevamiento, PastoralPI, EspacioEducativo (+ subtablas), Taller, EstablecimientoEstado, Catalogo
- [x] `backend/app/routers/auth.py` — login JWT con roles
- [x] `backend/app/routers/relevamientos.py` — CRUD + ciclo de estados (borrador/enviado/validado/rechazado) con control por rol
- [x] `backend/app/main.py` — FastAPI con CORS
- [x] `backend/lambda_handler.py` — entrada para Mangum
- [x] `backend/migrations/001_tablas_base.sql` — tablas base + seed catálogos
- [x] `backend/migrations/002_relevamiento_secciones.sql` — Pastoral PI, Espacios Educativos, Talleres, Establecimientos
- [x] `backend/requirements.txt`
- [x] `frontend/index.html` — página de login
- [x] `frontend/js/api.js` — cliente HTTP centralizado con manejo de token
- [x] `frontend/js/login.js` — lógica de login y redirección por rol
- [x] `frontend/css/main.css`
- [x] `netlify.toml`
- [x] `.env.example`, `.gitignore`, `README.md`
- [x] Repo subido a https://github.com/vickyberenguer/emaus
- [x] TiDB Cloud Serverless configurado (`emaus_relevamiento`), migraciones 001 y 002 ejecutadas
- [x] Usuario admin creado
- [x] Netlify conectado (`relevamientoemaus.netlify.app` — `emaus.netlify.app` no estaba disponible)
- [x] Backend desplegado en AWS Lambda + API Gateway, verificado end-to-end (login real devuelve JWT)

### Pendiente
- [ ] Endpoints de secciones del formulario (pastoral-pi, espacios-educativos, talleres, establecimientos) — guardado parcial por sección
- [ ] Formulario ATL (4 secciones, frontend)
- [ ] Panel responsable (validación)
- [ ] Panel admin (usuarios, padrón, catálogos)
- [ ] Endpoint e importación del padrón de establecimientos
- [ ] Tablero de indicadores

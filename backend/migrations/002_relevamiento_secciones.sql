-- ============================================================
-- Migración 002 — Pastoral PI, Espacios Educativos, Talleres,
--                 Establecimientos educativos
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001
-- ============================================================

-- ----------------------------------------------------------------
-- Pastoral Primera Infancia (una por relevamiento)
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pastoral_pi (
    id                              INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_id                 INT NOT NULL UNIQUE,
    anios_desarrollo                INT,
    presento_metodologia            BOOLEAN,
    comunidades_sin_pastoral        INT,
    capacitadoras                   INT,
    lideres                         INT,
    madres_embarazadas_12_18        INT,
    madres_embarazadas_19_29        INT,
    madres_embarazadas_30_mas       INT,
    madres_no_embarazadas           INT,
    ninos_0_3                       INT,
    ninos_4_6                       INT,
    familias                        INT,
    lideres_todas_alfabetizadas     BOOLEAN,
    lideres_no_alfabetizadas_cantidad INT,
    lideres_en_alfabetizacion       BOOLEAN,
    madres_todas_alfabetizadas      BOOLEAN,
    madres_no_alfabetizadas_cantidad INT,
    madres_en_alfabetizacion        BOOLEAN,
    FOREIGN KEY (relevamiento_id) REFERENCES relevamiento(id)
);

CREATE TABLE IF NOT EXISTS pastoral_pi_enfermedad_ninos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    pastoral_pi_id  INT NOT NULL,
    enfermedad      VARCHAR(200) NOT NULL,
    enfermedad_otra VARCHAR(200),
    orden           TINYINT,
    FOREIGN KEY (pastoral_pi_id) REFERENCES pastoral_pi(id)
);

CREATE TABLE IF NOT EXISTS pastoral_pi_enfermedad_embarazadas (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    pastoral_pi_id  INT NOT NULL,
    enfermedad      VARCHAR(200) NOT NULL,
    enfermedad_otra VARCHAR(200),
    orden           TINYINT,
    FOREIGN KEY (pastoral_pi_id) REFERENCES pastoral_pi(id)
);

CREATE TABLE IF NOT EXISTS pastoral_pi_accion_lider (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    pastoral_pi_id      INT NOT NULL,
    accion              ENUM('celebracion_vida','visita_domiciliaria','reunion_evaluacion') NOT NULL,
    realiza              BOOLEAN DEFAULT FALSE,
    frecuencia           VARCHAR(100),
    cantidad_semestre    INT,
    FOREIGN KEY (pastoral_pi_id) REFERENCES pastoral_pi(id)
);

CREATE TABLE IF NOT EXISTS pastoral_pi_tematica (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    pastoral_pi_id      INT NOT NULL,
    tematica            VARCHAR(200) NOT NULL,
    tematica_otra       VARCHAR(200),
    comunidades_cantidad INT,
    FOREIGN KEY (pastoral_pi_id) REFERENCES pastoral_pi(id)
);

CREATE TABLE IF NOT EXISTS pastoral_pi_articulacion (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    pastoral_pi_id      INT NOT NULL,
    organizacion        VARCHAR(200) NOT NULL,
    organizacion_otra    VARCHAR(200),
    FOREIGN KEY (pastoral_pi_id) REFERENCES pastoral_pi(id)
);

-- ----------------------------------------------------------------
-- Espacios Educativos — datos de base (persisten entre semestres)
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS espacio_educativo (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    emaus_id                INT NOT NULL,
    nombre                  VARCHAR(200) NOT NULL,
    direccion               VARCHAR(500),
    geolocalizacion         VARCHAR(500),
    renabap                 BOOLEAN DEFAULT FALSE,
    titularidad             VARCHAR(100),
    nombre_titular          VARCHAR(200),
    construccion_material   VARCHAR(100),
    rampa_acceso            BOOLEAN DEFAULT FALSE,
    acceso_principal        VARCHAR(100),
    activo                  BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (emaus_id) REFERENCES emaus(id)
);

CREATE TABLE IF NOT EXISTS ee_ambiente (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    espacio_educativo_id INT NOT NULL,
    ambiente            VARCHAR(100) NOT NULL,
    tiene               BOOLEAN DEFAULT FALSE,
    cantidad            INT,
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

CREATE TABLE IF NOT EXISTS ee_servicio (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    espacio_educativo_id INT NOT NULL,
    servicio            VARCHAR(100) NOT NULL,
    valor               VARCHAR(200),
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

CREATE TABLE IF NOT EXISTS ee_equipo_cocina (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    espacio_educativo_id INT NOT NULL,
    equipo              VARCHAR(100) NOT NULL,
    tiene               BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

CREATE TABLE IF NOT EXISTS ee_equipo_informatico (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    espacio_educativo_id INT NOT NULL,
    equipo              VARCHAR(100) NOT NULL,
    cantidad            INT,
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

-- ----------------------------------------------------------------
-- Espacios Educativos — datos semestrales (por relevamiento)
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS relevamiento_ee (
    id                              INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_id                 INT NOT NULL,
    espacio_educativo_id            INT NOT NULL,
    asistentes_0_6                  INT,
    asistentes_7_14                 INT,
    asistentes_15_24                INT,
    asistentes_25_35                INT,
    asistentes_35_50                INT,
    asistentes_mas_50               INT,
    grupo_motor_cantidad            INT,
    grupo_motor_frecuencia          VARCHAR(100),
    adolescentes_referentes         INT,
    adolescentes_frecuencia         VARCHAR(100),
    itinerancia_realizo             BOOLEAN DEFAULT FALSE,
    itinerancia_frecuencia          VARCHAR(100),
    internet_acceso                 BOOLEAN DEFAULT FALSE,
    internet_falta_motivo           VARCHAR(200),
    jornadas_formacion_digital      BOOLEAN DEFAULT FALSE,
    articula_nivel_superior         BOOLEAN DEFAULT FALSE,
    nivel_superior_cantidad         INT,
    bf_apoyo_escolar                INT,
    bf_nivel_inicial                INT,
    bf_primaria                     INT,
    bf_secundaria                   INT,
    bf_asignaciones                 INT,
    bf_discapacidad                 INT,
    bf_cud                          INT,
    btu_regulares                   INT,
    btu_egresados                   INT,
    btu_abandonaron                 INT,
    apoyo_primario_ninos            INT,
    apoyo_primario_frecuencia       VARCHAR(100),
    apoyo_primario_contenido_principal VARCHAR(200),
    apoyo_secundario_adolescentes   INT,
    apoyo_secundario_frecuencia     VARCHAR(100),
    apoyo_secundario_contenido_principal VARCHAR(200),
    alfa_total                      INT,
    alfa_6_9                        INT,
    alfa_10_14                      INT,
    alfa_15_24                      INT,
    alfa_25_mas                     INT,
    alfa_alfabetizadores            INT,
    alfa_frecuencia                 VARCHAR(100),
    dale_total                      INT,
    dale_6_9                        INT,
    dale_10_14                      INT,
    dale_15_24                      INT,
    dale_25_mas                     INT,
    dale_educadores                 INT,
    dale_frecuencia_dias            INT,
    UNIQUE KEY uq_relevamiento_ee (relevamiento_id, espacio_educativo_id),
    FOREIGN KEY (relevamiento_id) REFERENCES relevamiento(id),
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_accion (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    eje                 VARCHAR(100) NOT NULL,
    accion              VARCHAR(200) NOT NULL,
    tiene               BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_necesidad_infra (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    necesidad           VARCHAR(200) NOT NULL,
    orden               TINYINT,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_preocupacion_joven (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    preocupacion        VARCHAR(200) NOT NULL,
    ranking             TINYINT,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_nivel_superior (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    nombre_institucion   VARCHAR(200) NOT NULL,
    tipo_acciones        VARCHAR(500),
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_btu_abandono_motivo (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    motivo              VARCHAR(200) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_apoyo_primario_contenido (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    contenido           VARCHAR(200) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_apoyo_secundario_contenido (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    contenido           VARCHAR(200) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_itinerancia_espacio (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    espacio             VARCHAR(200) NOT NULL,
    espacio_otro        VARCHAR(200),
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_itinerancia_actividad (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    actividad           VARCHAR(200) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_itinerancia_rol (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    rol                 VARCHAR(200) NOT NULL,
    rol_otro            VARCHAR(200),
    cantidad            INT,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_digital_taller (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    taller              VARCHAR(200) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_grupo_motor_rol (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    rol                 VARCHAR(200) NOT NULL,
    rol_otro            VARCHAR(200),
    cantidad            INT,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

CREATE TABLE IF NOT EXISTS relevamiento_ee_ubicacion_zona (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_ee_id  INT NOT NULL,
    zona                VARCHAR(100) NOT NULL,
    FOREIGN KEY (relevamiento_ee_id) REFERENCES relevamiento_ee(id)
);

-- ----------------------------------------------------------------
-- Talleres (a nivel Emaús, por relevamiento)
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS taller (
    id                          INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_id             INT NOT NULL,
    eje                         VARCHAR(100) NOT NULL,
    tematica                    VARCHAR(200) NOT NULL,
    cantidad_participantes      INT,
    cantidad_ee                 INT,
    cantidad_comunidades_pi     INT,
    otras_instituciones         VARCHAR(500),
    perfil_capacitadores        VARCHAR(500),
    FOREIGN KEY (relevamiento_id) REFERENCES relevamiento(id)
);

-- ----------------------------------------------------------------
-- Establecimientos educativos — padrón oficial del Ministerio
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS establecimiento_estado (
    id                          INT AUTO_INCREMENT PRIMARY KEY,
    cueanexo                    VARCHAR(50) NOT NULL UNIQUE,
    jurisdiccion                VARCHAR(100),
    sector                      VARCHAR(50),
    ambito                      VARCHAR(50),
    departamento                VARCHAR(200),
    cod_departamento            VARCHAR(50),
    localidad                   VARCHAR(200),
    cod_localidad                VARCHAR(50),
    nombre                      VARCHAR(300),
    domicilio                   VARCHAR(500),
    codigo_postal                VARCHAR(20),
    telefono                    VARCHAR(50),
    mail                        VARCHAR(200),
    nivel_inicial_maternal       BOOLEAN DEFAULT FALSE,
    nivel_inicial_infantes       BOOLEAN DEFAULT FALSE,
    primario                    BOOLEAN DEFAULT FALSE,
    secundario                  BOOLEAN DEFAULT FALSE,
    adultos                     BOOLEAN DEFAULT FALSE,
    formacion_profesional        BOOLEAN DEFAULT FALSE,
    alfabetizacion              BOOLEAN DEFAULT FALSE,
    actualizado_en              DATE,
    INDEX idx_establecimiento_jurisdiccion (jurisdiccion),
    INDEX idx_establecimiento_localidad (localidad)
);

CREATE TABLE IF NOT EXISTS establecimiento_articulado (
    id                          INT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_id             INT NOT NULL,
    establecimiento_id          INT NOT NULL,
    accion_institucion          BOOLEAN DEFAULT FALSE,
    accion_articulacion_alfa    BOOLEAN DEFAULT FALSE,
    accion_seguimiento          BOOLEAN DEFAULT FALSE,
    accion_intercambio          BOOLEAN DEFAULT FALSE,
    accion_otros                BOOLEAN DEFAULT FALSE,
    detalle_otros                TEXT,
    UNIQUE KEY uq_establecimiento_articulado (relevamiento_id, establecimiento_id),
    FOREIGN KEY (relevamiento_id) REFERENCES relevamiento(id),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento_estado(id)
);

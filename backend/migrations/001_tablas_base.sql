-- ============================================================
-- Migración 001 — Tablas base
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible)
-- ============================================================

CREATE TABLE IF NOT EXISTS diocesis (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(200) NOT NULL,
    provincia   VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS emaus (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    diocesis_id         INT NOT NULL,
    nombre              VARCHAR(200) NOT NULL,
    direccion           VARCHAR(500),
    geolocalizacion     VARCHAR(500),
    renabap             BOOLEAN DEFAULT FALSE,
    frecuencia_acciones VARCHAR(100),
    activo              BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (diocesis_id) REFERENCES diocesis(id)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    emaus_id      INT,                          -- NULL para admin y responsables
    nombre        VARCHAR(100) NOT NULL,
    apellido      VARCHAR(100) NOT NULL,
    email         VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    rol           ENUM('atl','responsable','admin') NOT NULL,
    activo        BOOLEAN DEFAULT TRUE,
    creado_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emaus_id) REFERENCES emaus(id)
);

CREATE TABLE IF NOT EXISTS responsable_emaus (
    responsable_id INT NOT NULL,
    emaus_id       INT NOT NULL,
    PRIMARY KEY (responsable_id, emaus_id),
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
    FOREIGN KEY (emaus_id)       REFERENCES emaus(id)
);

CREATE TABLE IF NOT EXISTS relevamiento (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    emaus_id            INT NOT NULL,
    atl_id              INT NOT NULL,
    anio                INT NOT NULL,
    semestre            ENUM('1','2') NOT NULL,
    estado              ENUM('borrador','enviado','validado','rechazado') DEFAULT 'borrador',
    comentario_rechazo  TEXT,
    creado_en           DATETIME DEFAULT CURRENT_TIMESTAMP,
    enviado_en          DATETIME,
    validado_en         DATETIME,
    UNIQUE KEY uq_relevamiento_periodo (emaus_id, anio, semestre),
    FOREIGN KEY (emaus_id) REFERENCES emaus(id),
    FOREIGN KEY (atl_id)   REFERENCES usuarios(id)
);

-- Catálogos para listas desplegables gestionadas desde admin
CREATE TABLE IF NOT EXISTS catalogo (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    categoria VARCHAR(100) NOT NULL,   -- 'enfermedad_ninos', 'tematica_pi', etc.
    valor     VARCHAR(200) NOT NULL,
    activo    BOOLEAN DEFAULT TRUE,
    orden     INT DEFAULT 0,
    INDEX idx_catalogo_categoria (categoria)
);

-- ============================================================
-- Seed: catálogos iniciales
-- ============================================================

INSERT INTO catalogo (categoria, valor, orden) VALUES
-- Enfermedades niños/as
('enfermedad_ninos', 'Anemia', 1),
('enfermedad_ninos', 'Desnutrición', 2),
('enfermedad_ninos', 'Parasitosis', 3),
('enfermedad_ninos', 'Infecciones respiratorias', 4),
('enfermedad_ninos', 'Diarrea / gastroenteritis', 5),
('enfermedad_ninos', 'Dermatitis / problemas de piel', 6),
('enfermedad_ninos', 'Otra', 99),
-- Enfermedades embarazadas
('enfermedad_embarazadas', 'Anemia', 1),
('enfermedad_embarazadas', 'Diabetes gestacional', 2),
('enfermedad_embarazadas', 'Hipertensión / preeclampsia', 3),
('enfermedad_embarazadas', 'Infecciones urinarias', 4),
('enfermedad_embarazadas', 'Desnutrición', 5),
('enfermedad_embarazadas', 'Otra', 99),
-- Temáticas PI
('tematica_pi', 'Vacunas', 1),
('tematica_pi', 'Higiene y cuidados de salud', 2),
('tematica_pi', 'Primeros auxilios', 3),
('tematica_pi', 'Estimulación adecuada', 4),
('tematica_pi', 'Lactancia y maternidad', 5),
('tematica_pi', 'Ternura, buen trato y prácticas de crianza', 6),
('tematica_pi', 'Alimentación saludable', 7),
('tematica_pi', 'Los derechos de las Infancias', 8),
('tematica_pi', 'Discriminación y/o violencia de género', 9),
('tematica_pi', 'Autoestima', 10),
('tematica_pi', 'Consumo problemático', 11),
('tematica_pi', 'Abuso y/o acoso infantil', 12),
('tematica_pi', 'Adecuación de espacios para la Primera Infancia', 13),
('tematica_pi', 'Cuidado del medio ambiente', 14),
('tematica_pi', 'Otras', 99),
-- Articulaciones
('articulacion', 'Centro de salud', 1),
('articulacion', 'Hospital', 2),
('articulacion', 'Municipio', 3),
('articulacion', 'Departamento de género', 4),
('articulacion', 'Departamento de servicio social', 5),
('articulacion', 'Parroquia', 6),
('articulacion', 'Hogar de Cristo', 7),
('articulacion', 'CECC', 8),
('articulacion', 'Espacios de Primera Infancia', 9),
('articulacion', 'Abrazo maternal', 10),
('articulacion', 'Gravida', 11),
('articulacion', 'Centro de formación profesional/de oficios', 12),
('articulacion', 'Escuela', 13),
('articulacion', 'Centros de terminalidad primaria/secundaria', 14),
('articulacion', 'Centro comunitario', 15),
('articulacion', 'Organizaciones barriales/sociales', 16),
('articulacion', 'Comedores/merenderos', 17),
('articulacion', 'Otro', 99),
-- Ejes de acción EE
('eje_accion', 'Primera infancia', 1),
('eje_accion', 'Apoyo a las trayectorias educativas', 2),
('eje_accion', 'Integración comunitaria', 3),
('eje_accion', 'Nuevas tecnologías', 4),
('eje_accion', 'Salud integral', 5),
-- Necesidades de infraestructura
('necesidad_infra', 'Pintura exterior', 1),
('necesidad_infra', 'Pintura interior', 2),
('necesidad_infra', 'Electricidad', 3),
('necesidad_infra', 'Agua (instalación interna)', 4),
('necesidad_infra', 'Gas (cocina / calefacción)', 5),
('necesidad_infra', 'Albañilería (arreglos)', 6),
('necesidad_infra', 'Albañilería (construcción)', 7),
('necesidad_infra', 'Climatización', 8),
('necesidad_infra', 'Baño (adecuación y/o instalación)', 9),
-- Preocupaciones jóvenes
('preocupacion_joven', 'Suicidio y conductas autolesivas', 1),
('preocupacion_joven', 'Falta de proyecto de vida', 2),
('preocupacion_joven', 'Consumos problemáticos (drogas y alcohol)', 3),
('preocupacion_joven', 'Apuestas online', 4),
('preocupacion_joven', 'Problemas de salud mental (ansiedad, depresión, etc.)', 5),
('preocupacion_joven', 'Violencia', 6),
('preocupacion_joven', 'Violencia digital y ciberacoso', 7),
('preocupacion_joven', 'Desvinculación escolar', 8);

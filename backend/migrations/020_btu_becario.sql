-- Datos individuales de becarios BTU (Becas Terciarias y Universitarias),
-- scrapeados de una carpeta de Drive separada del relevamiento (una planilla
-- por diócesis, hoja por año). No se muestra DNI/nombre en el tablero: se
-- guardan solo para poder identificar y actualizar (upsert) el mismo becario
-- entre corridas del scraper.

CREATE TABLE IF NOT EXISTS btu_becario (
    id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
    emaus_id                    INT NOT NULL,
    anio                        SMALLINT NOT NULL,
    diocesis_nombre_hoja        VARCHAR(100) NULL,
    nro                         VARCHAR(20)  NULL,
    observaciones               TEXT NULL,
    certificados                VARCHAR(100) NULL,
    apellido_nombres            VARCHAR(200) NOT NULL,
    dni                         VARCHAR(20)  NULL,
    sexo                        VARCHAR(20)  NULL,
    fecha_nacimiento            DATE NULL,
    edad                        SMALLINT NULL,
    percibe_progresar           BOOLEAN NULL,
    institucion                 VARCHAR(200) NULL,
    nivel                       VARCHAR(20)  NULL,
    ambito                      VARCHAR(20)  NULL,
    carrera                     VARCHAR(200) NULL,
    rama                        VARCHAR(50)  NULL,
    duracion_carrera            VARCHAR(20)  NULL,
    anio_comienzo_carrera       VARCHAR(10)  NULL,
    anio_comienzo_beca          VARCHAR(10)  NULL,
    anio_cursando               VARCHAR(10)  NULL,
    continua_periodo_siguiente  BOOLEAN NULL,
    motivo_baja                 VARCHAR(200) NULL,
    mes_comienzo_beca           VARCHAR(20)  NULL,
    mes_fin_beca                VARCHAR(20)  NULL,
    activo                      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en                   DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (emaus_id) REFERENCES emaus(id),
    UNIQUE KEY uq_btu_becario_dni_anio (dni, anio)
);

-- Valores mensuales (febrero..diciembre) por becario y año — tabla hija en vez
-- de columnas "febrero2026".."diciembre2026" para no migrar de nuevo cada año.
CREATE TABLE IF NOT EXISTS btu_becario_mes (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    btu_becario_id  BIGINT NOT NULL,
    mes             VARCHAR(20) NOT NULL,
    valor           VARCHAR(50) NULL,
    FOREIGN KEY (btu_becario_id) REFERENCES btu_becario(id) ON DELETE CASCADE,
    UNIQUE KEY uq_btu_becario_mes (btu_becario_id, mes)
);

-- Migración 008: Módulo de control de relevamiento
-- Agrega spreadsheet_id a emaus y crea las 3 tablas de control

ALTER TABLE emaus
    ADD COLUMN spreadsheet_id VARCHAR(200) NULL AFTER activo;

CREATE TABLE IF NOT EXISTS control_relevamiento (
    emaus_id            INT          NOT NULL,
    anio                SMALLINT     NOT NULL,
    semestre            CHAR(1)      NOT NULL,

    ee_count            INT          NOT NULL DEFAULT 0,
    ee_declarados_completos INT      NOT NULL DEFAULT 0,
    ee_pendientes       INT          NOT NULL DEFAULT 0,
    ee_con_errores      INT          NOT NULL DEFAULT 0,

    pi_existe           BOOLEAN      NOT NULL DEFAULT FALSE,
    pi_completa         BOOLEAN      NOT NULL DEFAULT FALSE,
    pi_con_errores      BOOLEAN      NOT NULL DEFAULT FALSE,

    talleres_completo       BOOLEAN  NOT NULL DEFAULT FALSE,
    establecimientos_completo BOOLEAN NOT NULL DEFAULT FALSE,

    total_asistentes_ee INT          NOT NULL DEFAULT 0,
    cantidad_talleres   INT          NOT NULL DEFAULT 0,
    cantidad_establecimientos INT    NOT NULL DEFAULT 0,

    ultimo_sync         DATETIME     NOT NULL,

    PRIMARY KEY (emaus_id, anio, semestre),
    CONSTRAINT fk_control_emaus FOREIGN KEY (emaus_id) REFERENCES emaus(id)
);

CREATE TABLE IF NOT EXISTS control_validacion_detalle (
    id              BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    emaus_id        INT          NOT NULL,
    anio            SMALLINT     NOT NULL,
    semestre        CHAR(1)      NOT NULL,
    hoja_nombre     VARCHAR(200) NOT NULL,
    validacion_id   VARCHAR(100) NOT NULL,
    severity        ENUM('error','warning') NOT NULL,
    mensaje         VARCHAR(500) NOT NULL,
    fecha           DATETIME     NOT NULL,
    resuelto        BOOLEAN      NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_detalle_control FOREIGN KEY (emaus_id, anio, semestre)
        REFERENCES control_relevamiento(emaus_id, anio, semestre)
);

CREATE TABLE IF NOT EXISTS control_aprobacion (
    emaus_id        INT          NOT NULL,
    anio            SMALLINT     NOT NULL,
    semestre        CHAR(1)      NOT NULL,
    estado          ENUM('pendiente','aprobado','rechazado') NOT NULL DEFAULT 'pendiente',
    aprobado_por    INT          NULL,
    observaciones   TEXT         NULL,
    fecha_aprobacion DATETIME    NULL,

    PRIMARY KEY (emaus_id, anio, semestre),
    CONSTRAINT fk_aprobacion_emaus FOREIGN KEY (emaus_id) REFERENCES emaus(id),
    CONSTRAINT fk_aprobacion_usuario FOREIGN KEY (aprobado_por) REFERENCES usuarios(id)
);

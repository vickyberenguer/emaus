-- Datos estructurados de la hoja "Talleres" (antes solo se contaban filas
-- llenas en cantidad_talleres, sin guardar el detalle). Una fila por taller;
-- rubro_tematico y los perfiles de capacitador se clasifican por palabras
-- clave a partir de texto libre (Tematica / Perfil de los capacitadores).

CREATE TABLE IF NOT EXISTS relevamiento_taller (
    id                            BIGINT AUTO_INCREMENT PRIMARY KEY,
    relevamiento_id               INT NOT NULL,
    eje                           VARCHAR(100) NULL,
    tematica                      VARCHAR(300) NULL,
    rubro_tematico                VARCHAR(100) NULL,
    cantidad_participantes        INT NULL,
    cantidad_espacios_educativos  INT NULL,
    cantidad_comunidades_pi       INT NULL,
    otras_instituciones           INT NULL,
    perfil_capacitadores_texto    VARCHAR(500) NULL,
    FOREIGN KEY (relevamiento_id) REFERENCES relevamiento(id)
);

-- Un taller puede tener varios perfiles de capacitador (texto separado por coma).
CREATE TABLE IF NOT EXISTS relevamiento_taller_perfil (
    id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    taller_id BIGINT NOT NULL,
    perfil    VARCHAR(100) NOT NULL,
    FOREIGN KEY (taller_id) REFERENCES relevamiento_taller(id) ON DELETE CASCADE
);

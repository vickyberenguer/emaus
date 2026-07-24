-- Guarda la fecha de última modificación de las planillas externas BTU y BF
-- para poder saltear su lectura si no hubo cambios desde el último sync.
CREATE TABLE IF NOT EXISTS sync_planilla_externa (
    nombre VARCHAR(20) PRIMARY KEY,
    ultima_modificacion DATETIME NULL
);

INSERT IGNORE INTO sync_planilla_externa (nombre) VALUES ('btu'), ('bf');

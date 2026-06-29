-- ============================================================
-- Migración 004 — Zona pasa a ser un dato de base del Espacio
--                 Educativo (no semestral)
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001-003
-- ============================================================

CREATE TABLE IF NOT EXISTS ee_zona (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    espacio_educativo_id INT NOT NULL,
    zona                 VARCHAR(100) NOT NULL,
    FOREIGN KEY (espacio_educativo_id) REFERENCES espacio_educativo(id)
);

-- Nota: la tabla relevamiento_ee_ubicacion_zona (migración 002) queda en desuso
-- a partir de esta migración; no se elimina para no perder datos ya cargados.

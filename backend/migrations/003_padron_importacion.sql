-- ============================================================
-- Migración 003 — Auditoría de importaciones del padrón
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001 y 002
-- ============================================================

CREATE TABLE IF NOT EXISTS padron_importacion (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id      INT NOT NULL,
    fecha           DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_procesados INT NOT NULL DEFAULT 0,
    insertados      INT NOT NULL DEFAULT 0,
    actualizados    INT NOT NULL DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

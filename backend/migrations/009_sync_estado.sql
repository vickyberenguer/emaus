-- Migración 009: Estado global del proceso de sync
CREATE TABLE IF NOT EXISTS sync_estado (
    id          INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    iniciado_en DATETIME    NOT NULL,
    finalizado_en DATETIME  NULL,
    estado      ENUM('corriendo','ok','error') NOT NULL DEFAULT 'corriendo',
    ok_count    INT         NOT NULL DEFAULT 0,
    err_count   INT         NOT NULL DEFAULT 0,
    skip_count  INT         NOT NULL DEFAULT 0,
    detalle     TEXT        NULL
);

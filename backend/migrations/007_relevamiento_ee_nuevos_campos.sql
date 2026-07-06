-- ============================================================
-- Migración 007 — Nuevos campos en relevamiento_ee
--   · dale_frecuencia_dias: INT → VARCHAR(100) (los valores son texto)
--   · internet_uso_social: nueva pregunta de alfabetización digital
--   · internet_uso_estudio: nueva pregunta de alfabetización digital
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001-006
-- ============================================================

ALTER TABLE relevamiento_ee MODIFY COLUMN dale_frecuencia_dias VARCHAR(100);


ALTER TABLE relevamiento_ee
    ADD COLUMN internet_uso_social  BOOLEAN NULL AFTER internet_falta_motivo;
ALTER TABLE relevamiento_ee
    ADD COLUMN internet_uso_estudio BOOLEAN NULL AFTER internet_uso_social;
    
    ALTER TABLE relevamiento_ee MODIFY COLUMN dale_frecuencia_dias VARCHAR(100);

ALTER TABLE relevamiento_ee
    ADD COLUMN internet_uso_social  BOOLEAN NULL AFTER internet_falta_motivo;
ALTER TABLE relevamiento_ee    
    ADD COLUMN internet_uso_estudio BOOLEAN NULL AFTER internet_uso_social;

-- ============================================================
-- Migración 006 — Ampliar columnas de establecimiento_estado
-- El archivo real del Ministerio tiene valores más largos de lo
-- esperado en teléfono (varios números juntos) y mail (varias
-- direcciones separadas por "/").
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001-005
-- ============================================================

ALTER TABLE establecimiento_estado MODIFY COLUMN telefono VARCHAR(500);
ALTER TABLE establecimiento_estado MODIFY COLUMN mail VARCHAR(500);
ALTER TABLE establecimiento_estado MODIFY COLUMN nombre VARCHAR(500);

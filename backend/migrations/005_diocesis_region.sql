-- ============================================================
-- Migración 005 — Agrega columna "region" a diocesis
-- Ejecutar en TiDB Cloud Starter (MySQL-compatible), después de 001-004
-- ============================================================

ALTER TABLE diocesis ADD COLUMN region VARCHAR(50);

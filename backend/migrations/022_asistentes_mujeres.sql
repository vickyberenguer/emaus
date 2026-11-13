-- Fin de término 2026: la tabla de asistentes por franja etaria suma la columna
-- "De ellas, cuántas son mujeres" (D10:D15 en la hoja EE).
ALTER TABLE relevamiento_ee
  ADD COLUMN asistentes_mujeres_0_6   INT NULL,
  ADD COLUMN asistentes_mujeres_7_14  INT NULL,
  ADD COLUMN asistentes_mujeres_15_24 INT NULL,
  ADD COLUMN asistentes_mujeres_25_35 INT NULL,
  ADD COLUMN asistentes_mujeres_35_50 INT NULL,
  ADD COLUMN asistentes_mujeres_mas_50 INT NULL;

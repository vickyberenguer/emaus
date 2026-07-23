-- Cantidad de comunidades en las que trabaja la Pastoral de Primera Infancia
-- (cuenta los campos Comunidad1-4 de la planilla que tienen nombre cargado)
ALTER TABLE pastoral_pi
  ADD COLUMN comunidades_total SMALLINT NULL;

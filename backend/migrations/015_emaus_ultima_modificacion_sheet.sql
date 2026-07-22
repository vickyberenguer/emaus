-- Guarda la fecha de última modificación de la planilla de Google Sheets de cada Emaús,
-- para poder saltear el scrapeo si no hubo cambios desde el último sync exitoso.
ALTER TABLE emaus
  ADD COLUMN ultima_modificacion_sheet DATETIME NULL;

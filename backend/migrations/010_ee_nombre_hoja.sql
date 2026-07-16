-- Agrega columna nombre_hoja a espacio_educativo para relacionar con la hoja de Google Sheets
ALTER TABLE espacio_educativo
  ADD COLUMN nombre_hoja VARCHAR(200) NULL COMMENT 'Nombre exacto de la hoja en la planilla Google Sheets';

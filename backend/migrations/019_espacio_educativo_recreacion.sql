-- "Espacio de recreación" no es sí/no como el resto de los ambientes: las
-- respuestas reales son "Cubierto"/"Descubierto"/"No tiene". Se guarda aparte
-- como texto en vez de forzarlo al booleano de ee_ambiente (que siempre daba 0%).
ALTER TABLE espacio_educativo ADD COLUMN espacio_recreacion VARCHAR(50) NULL;

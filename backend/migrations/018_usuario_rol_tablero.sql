-- Nuevo rol "tablero": acceso de solo lectura a todos los tabs del Tablero
-- excepto "Estado de carga" (ese tab sigue siendo admin/responsable).
ALTER TABLE usuarios
    MODIFY COLUMN rol ENUM('atl','responsable','admin','tablero') NOT NULL;

-- Eliminar duplicados manteniendo el registro más reciente (id mayor)
DELETE a FROM relevamiento_ee_accion a
INNER JOIN relevamiento_ee_accion b
  ON a.relevamiento_ee_id = b.relevamiento_ee_id
  AND a.eje = b.eje
  AND a.accion = b.accion
  AND a.id < b.id;

-- Agregar unique key para que ON DUPLICATE KEY UPDATE funcione
ALTER TABLE relevamiento_ee_accion
  ADD UNIQUE KEY uq_ree_eje_accion (relevamiento_ee_id, eje, accion);

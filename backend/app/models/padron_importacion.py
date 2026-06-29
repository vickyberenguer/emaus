from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class PadronImportacion(Base):
    __tablename__ = "padron_importacion"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha = Column(DateTime, server_default=func.now())
    total_procesados = Column(Integer, nullable=False, default=0)
    insertados = Column(Integer, nullable=False, default=0)
    actualizados = Column(Integer, nullable=False, default=0)

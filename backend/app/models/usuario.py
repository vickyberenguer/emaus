from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class RolEnum(str, enum.Enum):
    atl = "atl"
    responsable = "responsable"
    admin = "admin"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    emaus_id = Column(Integer, ForeignKey("emaus.id"), nullable=True)  # null para admin/responsable sin Emaus fijo
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    rol = Column(Enum(RolEnum), nullable=False)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, server_default=func.now())
    ultimo_ingreso = Column(DateTime, nullable=True)

    emaus = relationship("Emaus", back_populates="atl")
    emaus_responsable = relationship("ResponsableEmaus", back_populates="responsable")

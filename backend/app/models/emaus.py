from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Diocesis(Base):
    __tablename__ = "diocesis"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    provincia = Column(String(100), nullable=False)

    emaus_list = relationship("Emaus", back_populates="diocesis")


class Emaus(Base):
    __tablename__ = "emaus"

    id = Column(Integer, primary_key=True, index=True)
    diocesis_id = Column(Integer, ForeignKey("diocesis.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    direccion = Column(String(500))
    geolocalizacion = Column(String(500))
    renabap = Column(Boolean, default=False)
    frecuencia_acciones = Column(String(100))
    activo = Column(Boolean, default=True)

    diocesis = relationship("Diocesis", back_populates="emaus_list")
    atl = relationship("Usuario", back_populates="emaus")
    responsables = relationship("ResponsableEmaus", back_populates="emaus")
    # relevamientos y espacios_educativos se agregan cuando se implementen esos modelos


class ResponsableEmaus(Base):
    __tablename__ = "responsable_emaus"

    responsable_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    emaus_id = Column(Integer, ForeignKey("emaus.id"), primary_key=True)

    responsable = relationship("Usuario", back_populates="emaus_responsable")
    emaus = relationship("Emaus", back_populates="responsables")

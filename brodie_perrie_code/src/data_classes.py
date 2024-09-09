from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (Column, Integer, String, DateTime, Float, Table,
  ForeignKey)

# Provides the classes for sqlAlchemy to read the database into.
Base = declarative_base()


procedure_association_table = Table('procedure_association', Base.metadata,
  Column('surgeries_id', Integer, ForeignKey('surgeries.id')),
  Column('procedures_id', Integer, ForeignKey('procedures.id')))


class Surgery(Base):
  __tablename__ = 'surgeries'

  id = Column(Integer, primary_key=True)
  facility = Column(String)
  specialty_id = Column(Integer, ForeignKey('specialties.id'))
  surgical_consultant_id = Column(Integer)
  admission_type = Column(String)
  planned = Column(Integer)
  anaesthesia_type = Column(String)
  asa_rating = Column(Integer)
  primary_procedure_id = Column(Integer, ForeignKey('procedures.id'))
  primary_procedure = relationship('Procedure',
    back_populates='primary_surgeries')
  arrival_datetime = Column(DateTime)
  due_date_datetime = Column(DateTime)
  complete_date_datetime = Column(DateTime)
  scheduled_duration = Column(Float)
  total_duration = Column(Float)
  turn_around_time = Column(Float)
  predicted_duration = Column(Float)
  predicted_variance = Column(Float)

  def __repr__(self):
    return '<Surgery(id={0})>'.format(self.id)

  def GetSpecialtyName(self):
    return self.specialty.name


class SurgicalSession(Base):
  __tablename__ = 'sessions'

  id = Column(Integer, primary_key=True)
  specialty_id = Column(Integer, ForeignKey('specialties.id'))
  facility = Column(String)
  planned = Column(Integer)
  surgical_consultant_id = Column(Integer)
  start_time = Column(DateTime)
  duration = Column(Float)
  theatre_number = Column(Float)

  def __repr__(self):
    return '<Session(id={0})>'.format(self.id)

  def GetSpecialtyName(self):
    return self.specialty.name


class Specialty(Base):
  __tablename__ = 'specialties'

  id = Column(Integer, primary_key=True)
  name = Column(String)

  def __repr__(self):
    return '<Specialty(id={0}, name={1})>'.format(self.id, self.name)

  def GetName(self):
    return self.name


class Procedure(Base):
  __tablename__ = 'procedures'

  id = Column(Integer, primary_key=True)
  description = Column(String)
  code = Column(Float)

  primary_surgeries = relationship('Surgery',
    back_populates='primary_procedure')

  def __repr__(self):
    return '<Procedure(id={0})>'.format(self.id)

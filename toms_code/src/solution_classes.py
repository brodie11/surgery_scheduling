import pandas as pd
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (Column, Integer, String, DateTime, Float, Table,
  ForeignKey)

# Provides the classes for sqlAlchemy for the output database(s).
Base = declarative_base()


class Surgery(Base):
  __tablename__ = 'surgeries'

  id = Column(Integer, primary_key=True)
  duration = Column(Integer)
  priority = Column(Float)

  solution_assignments = relationship('SolutionAssignment',
    back_populates='surgery')

  def __repr__(self):
    return '<Surgery(id={0})>'.format(self.id)


class SurgicalSession(Base):
  __tablename__ = 'sessions'

  id = Column(Integer, primary_key=True)
  start_datetime = Column(DateTime)
  room = Column(Float)
  duration = Column(Float)

  solution_assignments = relationship('SolutionAssignment',
    back_populates='surgical_session')

  def __repr__(self):
    return '<Session(id={0})>'.format(self.id)


class Solution(Base):
  __tablename__ = 'solutions'

  id = Column(Integer, primary_key=True)
  strict_priority = Column(Integer)
  transfers_allowed = Column(Integer)
  min_undertime = Column(Integer)
  under_time = Column(Float)

  solution_assignments = relationship('SolutionAssignment',
    back_populates='solution')

  def __repr__(self):
    return '<Solution(id={0})>'.format(self.id)


class SolutionAssignment(Base):
  __tablename__ = 'solution_assignments'

  id = Column(Integer, primary_key=True)
  surgery_id = Column(Integer, ForeignKey('surgeries.id'))
  surgery = relationship('Surgery', back_populates='solution_assignments')
  session_id = Column(Integer, ForeignKey('sessions.id'))
  surgical_session = relationship('SurgicalSession',
    back_populates='solution_assignments')
  solution_id = Column(Integer, ForeignKey('solutions.id'))
  solution = relationship('Solution', back_populates='solution_assignments')

  def __repr__(self):
    return '<SolutionAssignment(id={0})>'.format(self.id)


class SolutionTransfer(Base):
  __tablename__ = 'solution_transfers'

  id = Column(Integer, primary_key=True)
  surgery_id = Column(Integer, ForeignKey('surgeries.id'))
  session_id = Column(Integer, ForeignKey('sessions.id'))
  solution_id = Column(Integer, ForeignKey('solutions.id'))
  transfer_justified = Column(Integer)

  def __repr__(self):
    return '<SolutionTransfer(id={0})>'.format(self.id)


def get_solution(db_ses, strict_priority, transfers_allowed, min_undertime):

  if transfers_allowed is not None:

    query = (db_ses.query(Solution)
      .where(Solution.strict_priority == strict_priority)
      .where(Solution.transfers_allowed == transfers_allowed)
      .where(Solution.min_undertime == min_undertime))

  elif min_undertime is not None:

    query = (db_ses.query(Solution)
      .where(Solution.strict_priority == strict_priority)
      .where(Solution.min_undertime == min_undertime))
    
  else:
    query = (db_ses.query(Solution)
      .where(Solution.strict_priority == strict_priority))

  return query.first()


def get_create_solution(db_ses, strict_priority, transfers_allowed,
  min_undertime, under_time):

  query = (db_ses.query(Solution)
    .where(Solution.strict_priority == strict_priority)
    .where(Solution.transfers_allowed == transfers_allowed)
    .where(Solution.min_undertime == min_undertime)
    .where(Solution.under_time == under_time))

  sol_obj = query.first()

  if sol_obj is None:

    sol_obj = Solution(strict_priority=strict_priority,
      transfers_allowed=transfers_allowed, min_undertime=min_undertime,
      under_time=under_time)
    db_ses.add(sol_obj)
    db_ses.commit()

  return sol_obj


def get_create_sur(db_ses, id_num, duration, priority):

  query = (db_ses.query(Surgery)
    .where(Surgery.id == id_num))

  sur_obj = query.first()

  if sur_obj is None:

    sur_obj = Surgery(id=id_num, duration=int(duration), priority=priority)
    db_ses.add(sur_obj)
    db_ses.commit()

  return sur_obj


def get_create_ses(db_ses, id_num, start_datetime, room, duration):

  query = (db_ses.query(SurgicalSession)
    .where(SurgicalSession.id == id_num))

  ses_obj = query.first()

  if ses_obj is None:

    ses_obj = SurgicalSession(id=id_num, start_datetime=start_datetime, room=room,
      duration=duration)
    db_ses.add(ses_obj)
    db_ses.commit()

  return ses_obj


def get_solution_session_surs(db_ses, sol_id, ses_id):
  query = (db_ses.query(Surgery)
    .join(SolutionAssignment)
    .where(SolutionAssignment.solution_id == sol_id)
    .where(SolutionAssignment.session_id == ses_id))

  return query.all()


def get_ses_sur_dict(db_ses, sol_id):

  sessions = get_sessions(db_ses)
  
  ses_sur_dict = {}

  for i, ses in sessions.iterrows():
    ses_sur_dict[i] = []
    ses_surs = get_solution_session_surs(db_ses, sol_id, i)
  
    for sur in ses_surs:

      ses_sur_dict[i].append(sur.id)

  return ses_sur_dict


def create_update_solution_assignments(db_ses, sol_id, ses_sur_dict):

  for ses in ses_sur_dict:
    for sur in ses_sur_dict[ses]:

      query = (db_ses.query(SolutionAssignment)
        .where(SolutionAssignment.surgery_id == sur)
        .where(SolutionAssignment.solution_id == sol_id))

      sol_assign = query.first()

      if sol_assign is None:
        sol_assign = SolutionAssignment(surgery_id=sur, session_id=ses,
          solution_id=sol_id)
        db_ses.add(sol_assign)

      else:
        sol_assign.session_id = ses

      db_ses.commit()

  return 0


def get_solution_assignments(db_ses, sol_id):

  query = (db_ses.query(SolutionAssignment)
    .where(SolutionAssignment.solution_id == sol_id))

  sol_assigns = pd.read_sql_query(query.statement, db_ses.bind,
    index_col='id')

  return sol_assigns


def get_solution_transfers(db_ses, sol_id):

  query = (db_ses.query(SolutionTransfer)
    .where(SolutionTransfer.solution_id == sol_id))

  sol_transfers = pd.read_sql_query(query.statement, db_ses.bind,
    index_col='id')

  return sol_transfers


def get_sessions(db_ses):
  query = (db_ses.query(SurgicalSession)
    .order_by(SurgicalSession.id))
  sessions = pd.read_sql_query(query.statement, db_ses.bind,
    index_col='id')

  return sessions


def get_surgeries(db_ses):
  query = (db_ses.query(Surgery)
    .order_by(Surgery.id))
  surgeries = pd.read_sql_query(query.statement, db_ses.bind,
    index_col='id')

  return surgeries


def create_update_solution_transfers(db_ses, sol_id, prob):

  for ses in prob.sess:
    for sur in prob.ops:

      query = (db_ses.query(SolutionTransfer)
        .where(SolutionTransfer.surgery_id == sur.n)
        .where(SolutionTransfer.surgery_id == ses.n)
        .where(SolutionTransfer.solution_id == sol_id))

      sol_transfer = query.first()

      if sol_transfer is None:
        sol_transfer = SolutionTransfer(surgery_id=sur.n, session_id=ses.n,
          solution_id=sol_id, transfer_justified=prob.y[sur.n, ses.n].X)
        db_ses.add(sol_transfer)

      else:
        sol_transfer.transfer_justified = prob.y[sur.n, ses.n].X
        sol_transfer.assigned_or_earlier = prob.a[sur.n, ses.n].X

      db_ses.commit()

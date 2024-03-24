from operator import attrgetter
import numpy as np
import pandas as pd

from datetime import timedelta

from .data_classes import (Surgery, SurgicalSession, Specialty)
from .scheduler_classes import (schedSurgery, schedSession)
from .solution_classes import get_create_sur, get_create_ses


# Reads in the surgeries, sessions, and specialties from the database, and
# filters based on the start and end date.
def read_database(session, start_date, end_date):

  query = (session.query(Surgery)
    .filter(Surgery.planned == 1)
    .filter(Surgery.arrival_datetime < start_date)
    .filter(Surgery.complete_date_datetime >= start_date)
    .order_by(Surgery.id))
  surgeries = pd.read_sql_query(query.statement, session.bind, index_col='id')

  query = (session.query(Surgery.id.label('surgeries_id'),
    Specialty.id.label('specialties_id'), Specialty.name)
    .filter(Surgery.planned == 1)
    .filter(Surgery.arrival_datetime < start_date)
    .filter(Surgery.complete_date_datetime >= start_date)
    .join(Specialty)
    .order_by(Surgery.id))
  specialty_names = pd.read_sql_query(query.statement, session.bind)

  surgeries = surgeries.assign(
    specialty_name=specialty_names['name'].values)

  query = (session.query(SurgicalSession)
    .filter(SurgicalSession.planned == 1)
    .filter(SurgicalSession.start_time >= start_date)
    .filter(SurgicalSession.start_time < end_date)
    .order_by(SurgicalSession.id))
  surgical_sessions = pd.read_sql_query(query.statement, session.bind,
    index_col='id')

  query = (session.query(SurgicalSession.id.label('sessions_id'),
    Specialty.id.label('specialties_id'), Specialty.name)
    .filter(SurgicalSession.planned == 1)
    .filter(SurgicalSession.start_time >= start_date)
    .filter(SurgicalSession.start_time < end_date)
    .join(Specialty)
    .order_by(SurgicalSession.id))
  specialty_names = pd.read_sql_query(query.statement, session.bind)
  surgical_sessions = surgical_sessions.assign(
    specialty_name=specialty_names['name'].values)

  query = session.query(Specialty).order_by(Specialty.id)
  specialties = pd.read_sql_query(query.statement, session.bind, index_col='id')

  return surgeries, surgical_sessions, specialties


# Prepares the data by removing any surgeries that don't have predictions for
# the duration.
def prepare_data(session, start_date, end_date):

  surgeries, surgical_sessions, specialties = read_database(session,
    start_date, end_date)

  valid_prediction = ~np.isnan(surgeries['predicted_duration'])
  surgeries = surgeries.loc[valid_prediction]

  return surgeries, surgical_sessions, specialties


# Takes the surgeries from the database and creates the objects used in
# scheduling.
def create_schedule_surs(partition_surs, session):

  surs = []

  for part_sur in partition_surs.itertuples():

    surs.append(schedSurgery(part_sur.Index, part_sur.predicted_duration,
      part_sur.predicted_variance, part_sur.arrival_datetime,
      part_sur.due_date_datetime))
    get_create_sur(session, part_sur.Index, part_sur.predicted_duration,
      surs[-1].priority)

  return surs

# Takes the sessions from the database and creates the objects used in
# scheduling. Also adds a large session at the end to ensure the problem is
# feasible.
def create_schedule_sess(partition_sess, session):

  sess = []

  for part_ses in partition_sess.itertuples():
  
    sess.append(schedSession(part_ses.Index, part_ses.start_time,
      part_ses.duration, part_ses.theatre_number))
    get_create_ses(session, part_ses.Index, part_ses.start_time,
      part_ses.theatre_number, part_ses.duration)

  last_sess = max(sess, key=attrgetter('sdt'))
  extra_sess_start = last_sess.sdt + timedelta(days=28)
  sess.append(schedSession(-1, extra_sess_start, 999999, 0))
  get_create_ses(session, -1, extra_sess_start, 0, 999999)

  return sess

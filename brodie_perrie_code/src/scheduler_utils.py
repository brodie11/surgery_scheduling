from operator import attrgetter
import numpy as np
import pandas as pd
import math

from datetime import timedelta

from data_classes import (Surgery, SurgicalSession, Specialty)
from scheduler_classes import (schedSurgery, schedSession)
from solution_classes import get_create_sur, get_create_ses


# Reads in the surgeries, sessions, and specialties from the database, and
# filters based on the start and end date.
def read_database(session, start_date, end_date):

  query = (session.query(Surgery)
    .filter(Surgery.planned == 1)
    .filter(Surgery.arrival_datetime < end_date)
    .filter(Surgery.complete_date_datetime >= start_date)
    .order_by(Surgery.id))
  surgeries = pd.read_sql_query(query.statement, session.bind, index_col='id')

  query = (session.query(Surgery.id.label('surgeries_id'),
    Specialty.id.label('specialties_id'), Specialty.name)
    .filter(Surgery.planned == 1)
    .filter(Surgery.arrival_datetime < end_date)
    .filter(Surgery.complete_date_datetime >= start_date)
    .join(Specialty)
    .order_by(Surgery.id))
  specialty_names = pd.read_sql_query(query.statement, session.bind)

  surgeries = surgeries.assign(
    specialty_name=specialty_names['name'].values)

  query = (session.query(SurgicalSession)
    .filter(SurgicalSession.planned == 1)
    .filter(SurgicalSession.start_time >= start_date)
    .order_by(SurgicalSession.id))
  surgical_sessions = pd.read_sql_query(query.statement, session.bind,
    index_col='id')

  query = (session.query(SurgicalSession.id.label('sessions_id'),
    Specialty.id.label('specialties_id'), Specialty.name)
    .filter(SurgicalSession.planned == 1)
    .filter(SurgicalSession.start_time >= start_date)
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
def create_schedule_partition_surs(partition_surs, simulation_start_date, simulation_end_date, days_considered_tardy, cdi):

  surs = []

  for part_sur in partition_surs.itertuples():

    #turn dates into integer repressenting dayss since simulation starts
    arrival_datetime_integer = (part_sur.arrival_datetime - simulation_start_date).days

    #create surgery objects
    surs.append(schedSurgery(part_sur.Index, part_sur.predicted_duration,
      part_sur.predicted_variance, arrival_datetime_integer,
      arrival_datetime_integer + days_considered_tardy, cdi=cdi))
    # get_create_sur(session, part_sur.Index, part_sur.predicted_duration,
    #   surs[-1].priority)
  

  #select every surgery who entered the system before start date but left after and put them in initial waitlist
  #store these in surgery objects
  initial_waitlist = list(filter(lambda x: x.ad <= 0, surs))
  #select every surgery who entered the system after start date and before (end date + horizon) and put them
  #in the to_arrive list
  to_arrive_sorted = sorted(list(filter(lambda x: x.ad > 0, surs)), key=lambda x: x.ad)
  #partition the list by week
  number_of_weeks = (simulation_end_date - simulation_start_date).days // 7
  to_arrive_partitioned = []
  for x in range(1, number_of_weeks + 1):
    week_x = list(filter(lambda surgery: surgery.ad // 7 <= x, to_arrive_sorted))
    to_arrive_sorted = list(filter(lambda surgery: surgery.ad // 7 > x, to_arrive_sorted))
    to_arrive_partitioned.append(week_x)

  return initial_waitlist, to_arrive_partitioned

# Takes the sessions from the database and creates the objects used in
# scheduling. Also adds a large session at the end to ensure the problem is
# feasible.
def create_schedule_partition_sess(partition_sess, simulation_start_date, simulation_end_date):

  #select every session ever (after start date and put that in seperate list)
  all_sess = []
  for part_ses in partition_sess.itertuples():

    start_time_integer = (part_ses.start_time - simulation_start_date).days
  
    all_sess.append(schedSession(part_ses.Index, start_time_integer,
      part_ses.duration, part_ses.theatre_number))
    # get_create_ses(session, part_ses.Index, part_ses.start_time,
    #   part_ses.theatre_number, part_ses.duration)
  
  #sort all_sess
  all_sess = sorted(all_sess, key=lambda x: x.sdt)
  
  #select every session between start and end date and add to sessions_to_arrive_partitioned by week
  number_of_days = (simulation_end_date - simulation_start_date).days
  sessions_to_schedule_for = list(filter(lambda x: x.sdt < number_of_days, all_sess))
  sessions_to_schedule_for_sorted = sorted(sessions_to_schedule_for, key = lambda x: x.sdt)
  number_of_weeks = number_of_days//7
  sessions_to_arrive_partitioned = []
  for x in range(1, number_of_weeks + 1):
    week_x = list(filter(lambda session: math.floor(session.sdt / 7) <= x, sessions_to_schedule_for_sorted))
    sessions_to_schedule_for_sorted = list(filter(lambda session: math.floor(session.sdt / 7) > x, sessions_to_schedule_for_sorted))
    sessions_to_arrive_partitioned.append(week_x)


  return all_sess, sessions_to_arrive_partitioned

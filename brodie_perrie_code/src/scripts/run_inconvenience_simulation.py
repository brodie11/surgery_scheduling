import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

from ..configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from ..scheduler_utils import (
  prepare_data, create_schedule_surs, create_schedule_sess)
from ..scheduler_classes import (schedProb, priorityProb)
from ..solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers)
from ..visualise import create_session_graph
from ..classes import (schedSurgery, schedSession)
from ..helper_funcs import (inconvenienceProb)


#choose specialty, faclility, turn_around, etc.
specialty_id = 4
facility = "A"
turn_around = 15
#set days_considered_tardy eg. 4 months
days_considered_tardy = round(4*(365/12))
#choose start date and end date
#pick start and end periods for simulation
period_start_year = 2015 #can go 2015-3 earliest
period_start_month = 3
period_end_year = 2015 #can go 2016-12 latest
period_end_month = 9
simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 
# Create a list of pd.Timestamp objects for the first day of each month
week_starts = week_starts = pd.date_range(start=simulation_start_date, end=simulation_end_date, freq='W-MON').tolist()
#remove last week
week_starts = week_starts[0:-1]

engine = create_engine('sqlite:///' + DATA_FILE)
Session = sessionmaker(bind=engine)

# Get all sessions after start date and all surgeries that haven't left by start_date and arrive before end_date
with Session() as session:
    surgeries, surgical_sessions, specialties = prepare_data(session,
        simulation_start_date, simulation_end_date)

# Filter surgeries and sessions to the specialty and facility of interest.
surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
    (surgeries['facility'] == facility)]
surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
    (surgical_sessions['facility'] == facility)]

#ensure everything is pd.date_time
surgeries['arrival_datetime'] = pd.to_datetime(surgeries['arrival_datetime'])
surgical_sessions['start_time'] = pd.to_datetime(surgical_sessions['start_time'])

#partition data as required
surgeries_initial_waitlist, surgeries_to_arrive_partitioned = create_schedule_surs(surgeries, simulation_start_date, simulation_end_date, days_considered_tardy)
all_sess, sessions_to_arrive_partitioned = create_schedule_sess(surgical_sessions, simulation_start_date, simulation_end_date)

number_patients_tardy = len(list(filter(lambda surgery: surgery.dd < 0, surgeries_initial_waitlist)))
print(f"number of patients already tardy: {number_patients_tardy}")

#loop through each week in weeks:
waitlist = surgeries_initial_waitlist
print(waitlist)

weeks = (simulation_end_date - simulation_start_date).days // 7
for week in range(1, weeks + 1):
    #move new surgeries from new_arrivals to waitlist #TODO discuss maybe adding in overtime cancelled surgeries later?
    new_sessions = sessions_to_arrive_partitioned.pop(0)
    new_surgeries = surgeries_to_arrive_partitioned.pop(0)
    if new_sessions.empty():
        continue #continue if no new sessions this week
    waitlist = waitlist + new_sessions
    #create schedules
    perfect_info_schedule = inconvenienceProb(waitlist, all_sess, turn_around, perfect_information=True)
    imperfect_info_schedule = inconvenienceProb(waitlist, all_sess, turn_around, perfect_information=False)

    #TODO count how many surgeries were cancelled due to patient preference

    sess_sur_dict = perfect_info_schedule.ses_sur_dict
    #move first 2 weeks of schedule to scheduled if first week, otherwise move first 1 week to scheduled
    if week == 1:
        scheduled_sessions = new_sessions + sessions_to_arrive_partitioned.pop(0)
    else:
        scheduled_sessions = new_sessions

    #remove sessions from all_sess and surgeries from waitlist
    for scheduled_session in scheduled_sessions:
        ids_of_surgery_scheduled = sess_sur_dict[scheduled_session]
        waitlist = [surgery for surgery in waitlist if surgery.n not in ids_of_surgery_scheduled]
    all_sess = [session for session in all_sess if session.n not in scheduled_sessions]
#compare the two schedules



#PREPARE DATA(start_date, end_date, horizon)

#select every surgery who entered the system before start date but left after and put them in waitlist
#store these in surgery objects

#select every surgery who entered the system after start date and before (end date) and put them
#in the to_arrive list
#store these in surgery objects

#select every session ever (after start date and put that in seperate list)

#select every session between start and end date and add to session_list
#select every session between end date and end date + rolling horizon and add to session_list_to_arrive
#store these in session objects

#generate random preferences for months, days, and weeks that don't work for people. store in surgery object
#TODO add times later maybve


#CREATE_SCHEDULE(week, end_date, perfect_information)

#TODO maybe don't consider disruption parameter for now? if so only need to generate for either 2 weeks or one week
#TODO in that vain - could use a warm start?

#obj function: #TODO agree on this with Perrie

#subject to:
#each surgery assigned to just one session
#sum of surgery duration percentiles within each session less than session duration
#tardiness > assigned session date - (entry_date + 4 months) 
#TODO set the -1 (not assigned) variable to have session date of end of session
#

#if perfect information
    #add constraints that say what days certain patients can't do
#solve LP
#if imperfect_information
    #check whether schedule clashes with any patient preferences (each surgery will have info on days/weeks/months/times that are banned)
    #TODO add times in later
    #if clash
        #remove from schedule. add back in to waitlist #TODO (enforce that they have to be solved first week?)

#TODO think abt diff facilityies and specs
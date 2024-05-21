import os
import sys

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Perrie's path 
repo_path = Path("/Users/perriemacdonald/Library/CloudStorage/OneDrive-TheUniversityofAuckland/University/ENGEN700/surgery_scheduling/brodie_perrie_code/src")

# Brodie;s path 
# TODO: add path to src directory and comment out my path. You can then run and debug. 

sys.path.append(str(repo_path))
from configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from scheduler_utils import (
  prepare_data, create_schedule_partition_surs, create_schedule_partition_sess)
from scheduler_classes import (schedProb, priorityProb)
from solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers)
from visualise import create_session_graph
from classes import (schedSurgery, schedSession)
from helper_funcs import (inconvenienceProb, is_surgery_inconvenient)
from solution_classes import get_create_sur, get_create_ses


#choose specialty, faclility, turn_around, etc.
specialty_id = 4
facility = "A"
turn_around = 15
chance_of_inconvenience_for_each_day_month_week = 0.083
#set to true if you want to manually resolve each gurobi problem and ignore stored solutions
solve_anyway = True
#set how long it takes for someone to be considered tardy
days_considered_tardy = round(4*(365/12))
#pick start and end periods for simulation
period_start_year = 2015 #can go 2015-3 earliest
period_start_month = 3
period_end_year = 2015 #can go 2016-12 latest
period_end_month = 9
simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 

#create session for reacing in data like Tom did
engine = create_engine('sqlite:///' + DATA_FILE)
Session = sessionmaker(bind=engine)

# Get all sessions after start date and all surgeries that haven't left by start_date and arrive before end_date
# I modified tom's prepare data function so this works
with Session() as session:
    surgeries, surgical_sessions, specialties = prepare_data(session,
        simulation_start_date, simulation_end_date)

# Filter surgeries and sessions to the specialty and facility of interest.
surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
    (surgeries['facility'] == facility)]
surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
    (surgical_sessions['facility'] == facility)]

#partition data
surgeries_initial_waitlist, surgeries_to_arrive_partitioned = create_schedule_partition_surs(surgeries, simulation_start_date, simulation_end_date, days_considered_tardy, chance_of_inconvenience_for_each_day_month_week)
all_sess, sessions_to_arrive_partitioned = create_schedule_partition_sess(surgical_sessions, simulation_start_date, simulation_end_date)

#count patients already tardy at start
number_patients_tardy = len(list(filter(lambda surgery: surgery.dd < 0, surgeries_initial_waitlist)))
print(f"number of patients already tardy at start: {number_patients_tardy}")

#MAIN LOOP
waitlist = surgeries_initial_waitlist
#loop through each week in weeks:
weeks = (simulation_end_date - simulation_start_date).days // 7
for week in range(1, weeks + 1):

    perfect_info_bool = True #eventually run for both at once

    #move new surgeries from new_arrivals to waitlist #TODO discuss maybe adding in overtime cancelled surgeries later?
    new_sessions = []
    new_surgeries = []
    if week == 1:
        new_sessions = sessions_to_arrive_partitioned.pop(0) + sessions_to_arrive_partitioned.pop(0)
        new_surgeries = surgeries_to_arrive_partitioned.pop(0) + surgeries_to_arrive_partitioned.pop(0)
    else:
        if sessions_to_arrive_partitioned:
            new_sessions = sessions_to_arrive_partitioned.pop(0)
            new_surgeries = surgeries_to_arrive_partitioned.pop(0)

    if not new_sessions:
        continue #continue if no new sessions this week

    waitlist = waitlist + new_surgeries
    
    #CREATE SCHEDULES

    #set up session to store specific week
    perfect_info_string = "False"
    if perfect_info_bool == True: perfect_info_string = "True"

    db_name = 'specialty_{0}_start_{1}_end_{2}_week_{3}_prob_type_{4}_imperfect_info_{5}.db'.format(specialty_id,
    simulation_start_date.date(), simulation_end_date.date(), week, "tardiness",  perfect_info_string)
    db_name = os.path.join(OUTPUT_DB_DIR, db_name)

    engine = create_engine('sqlite:///' + db_name)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:

        #get solution and check if already been solved
        inconvenience_sol = get_solution(session, 10, 10, 10) #fudge a little bit so I don't have to rewrite Tom's code
        if inconvenience_sol is None or solve_anyway == True:

            for surgery in waitlist:
                get_create_sur(session, surgery.n, surgery.ed, surgery.priority)
            for sess in all_sess:
                get_create_ses(session, sess.n, simulation_start_date + pd.Timedelta(days=sess.sdt), sess.tn, sess.sd)

            #otherwise, solve it
            #this is the class that solves the linear program
            # perfect_info_schedule = inconvenienceProb(waitlist, all_sess, turn_around, perfect_information=True, time_lim=300)
            imperfect_info_schedule = inconvenienceProb(waitlist, all_sess, turn_around, perfect_information=False, time_lim=300) 

            #TODO solve the imperfect information problem also
            for imperfect_sessions in imperfect_info_schedule.ses_sur_dict.keys():
                if imperfect_sessions == -1:
                    break
                sess_sched_obj = list(filter(lambda obj: obj.n == imperfect_sessions, all_sess))[0]
                # get surgeries in session
                surgeries_in_session = imperfect_info_schedule.ses_sur_dict[imperfect_sessions]
                for surgery in surgeries_in_session:
                    surgery_sched_obj = list(filter(lambda obj: obj.n == surgery, waitlist))[0]
                    # check if inconvenient
                    inconvenient = is_surgery_inconvenient(sess_sched_obj.sdt, simulation_start_date, surgery_sched_obj)
                    if inconvenient:
                        # cancel surgery
                        imperfect_info_schedule.ses_sur_dict[imperfect_sessions].remove(surgery)
                        # Need to check if more needs to be done to cancel a surgery
                        

            #store solution in fudged way so don't have to rewrite Tom's code
            inconvenience_sol = get_create_solution(session, 10,
            10, 10, 0)

            #update database
            create_update_solution_assignments(session, inconvenience_sol.id,
            imperfect_info_schedule.ses_sur_dict)
            # sess_sur_dict = perfect_info_schedule.ses_sur_dict
        # else:
        sess_sur_dict = get_ses_sur_dict(session, inconvenience_sol.id) #TODO test if this works

        print(sess_sur_dict)

        #graph
        graph_name = 'specialty_{0}_start_{1}_end_{2}_week_{3}_prob_type_{4}_perfect_info_{5}.db'.format(specialty_id,
        simulation_start_date.date(), simulation_end_date.date(), week, "tardiness",  perfect_info_string)
        create_session_graph(inconvenience_sol, session, graph_name)

    #TODO count how many surgeries were cancelled due to patient preference

    #move first 2 weeks of schedule to scheduled if first week, otherwise move first 1 week to scheduled
    scheduled_sessions = new_sessions

    #remove scheduled sessions from all_sess and scheduled surgeries from waitlist
    for scheduled_session in scheduled_sessions:
        ids_of_surgery_scheduled = sess_sur_dict[scheduled_session.n]
        waitlist = [surgery for surgery in waitlist if surgery.n not in ids_of_surgery_scheduled]
    all_sess = [session for session in all_sess if session.n not in scheduled_sessions]


#TODO compare the two schedules



#OLD PSEUDODCODE:
# - - - - - - - - - -- - - - - - - - - -- - - - - - - - - -- - - - - - - - - -- - - - - - - - - -- - - - - - - - - -


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
import os
import sys

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Perrie's path 
# repo_path = Path("/Users/perriemacdonald/Library/CloudStorage/OneDrive-TheUniversityofAuckland/University/ENGEN700/surgery_scheduling/brodie_perrie_code/src")

# Brodie's path path 
repo_path = Path("C:/Users/Grant Dye/Documents/Uni/Engsci/4th year/part4project/surgery_scheduling/brodie_perrie_code/src")

sys.path.append(str(repo_path))
from configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE, OUTPUT_DB_DIR_TEST
from scheduler_utils import (
  prepare_data, create_schedule_partition_surs, create_schedule_partition_sess)
from scheduler_classes import (schedProb, priorityProb)
from solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers)
from visualise import create_session_graph
from classes import (schedSurgery, schedSession)
from helper_funcs import (inconvenienceProb, compute_metrics, print_detailed_ses_sur_dict,is_surgery_inconvenient, get_plenty_of_sess)
from solution_classes import get_create_sur, get_create_ses

#choose specialty, faclility, turn_around, etc.
specialty_id = 0
facility = "A"
time_lim_first_week = 600
time_lim_other_weeks = 60
print_verbose = False
turn_around = 15
chance_of_inconvenience_for_each_day_month_week = 0.083
obj_type = "t&p matrix"
#set to true if you want to manually resolve each gurobi problem and ignore stored solutions
solve_anyway = False
#set how long it takes for someone to be considered tardy
days_considered_tardy = round(3*(365/12))
#pick start and end periods for simulation
period_start_year = 2015 #can go 2015-3 earliest
period_start_month = 3
period_end_year = 2016 #can go 2016-12 latest
period_end_month = 3
simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 
#make testing = true if running a test or something else where you don't mind the databases being 
#deleted after. Make testing = false otherwise
testing = False
output_db_location_to_use = OUTPUT_DB_DIR
if testing == True:
    output_db_location_to_use = OUTPUT_DB_DIR_TEST

#data to collect
columns = ['objective type', 'perfect_information_bool', 'days_considered_tardy', 'week', 'total tardiness', 'number of patients tardy', 'average wait time (priority < 0.33)', 
           'average wait_time (0.33 < priority < 0.66)', 'average wait time 0.66 < priority',
           'number of surgeries scheduled', 'num sessions', 'num surgeries cancelled', "cancelation proportion",]
metrics_df = pd.DataFrame(columns=columns)
total_tardiness = number_patients_tardy = average_waittime_p33 = average_waittime_p66 = average_waittime_p100 = num_surs_scheduled = avg_session_utilisation = 0


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

# Convert start_time to datetime if it's not already in datetime format
surgical_sessions['start_time'] = pd.to_datetime(surgical_sessions['start_time'])

current_solution = None
week_1_solution = None

#loop through each week in weeks:
weeks = (simulation_end_date - simulation_start_date).days // 7
for perfect_info_bool in [True, False]:

    #partition data
    surgeries_initial_waitlist, surgeries_to_arrive_partitioned = create_schedule_partition_surs(surgeries, simulation_start_date, simulation_end_date, days_considered_tardy, chance_of_inconvenience_for_each_day_month_week)
    all_sess, sessions_to_arrive_partitioned = create_schedule_partition_sess(surgical_sessions, simulation_start_date, simulation_end_date)

    #count patients already tardy at start
    number_patients_tardy = len(list(filter(lambda surgery: surgery.dd < 0, surgeries_initial_waitlist)))
    if print_verbose: print(f"number of patients already tardy at start: {number_patients_tardy}")

    #MAIN LOOP
    waitlist = surgeries_initial_waitlist

    for week in range(1, weeks + 1):

        if print_verbose: print(f"\n\nWeek {week}\n------------------------------------------------")

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

        # print(f"new sessions: {new_sessions}")

        waitlist = waitlist + new_surgeries

        # print(f"len waaitlist {len(waitlist)}")

        plenty_of_sess = get_plenty_of_sess(all_sess, waitlist) #make sure there's enough sessions but not too many
        
        #CREATE SCHEDULES

        #make string version of perfect_info_bool
        perfect_info_string = "False"
        if perfect_info_bool == True: perfect_info_string = "True"

        #set up session to store specific week
        db_name = 'specialty_{0}_start_{1}_end_{2}_week_{3}_prob_type_{4}_pi_{5}_dct_{6}.db'.format(specialty_id,
        simulation_start_date.date(), simulation_end_date.date(), week, obj_type.replace(" ", ""),  perfect_info_string, str(days_considered_tardy))
        db_name = os.path.join(output_db_location_to_use, db_name)

        if print_verbose: print(f"db name {db_name}")

        engine = create_engine('sqlite:///' + db_name)

        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        with Session() as session:

            #get solution and check if already been solved
            inconvenience_sol = get_solution(session, 10, 10, 10) #fudge a little bit so I don't have to rewrite Tom's code
            cancelled_surgeries = []
            if inconvenience_sol is None or solve_anyway == True:

                for surgery in waitlist:
                    get_create_sur(session, surgery.n, surgery.ed, surgery.priority)
                for sess in plenty_of_sess:
                    get_create_ses(session, sess.n, simulation_start_date + pd.Timedelta(days=sess.sdt), sess.tn, sess.sd)

                #otherwise, solve it
                #this is the class that solves the linear program
                #perfect_info_schedule = inconvenienceProb(waitlist, plenty_of_sess, turn_around, obj_type=obj_type, perfect_information=True, time_lim=30)
                if week == 1:
                    schedule = inconvenienceProb(waitlist, all_sess, turn_around, obj_type, init_assign = week_1_solution, perfect_information=perfect_info_bool, time_lim=time_lim_first_week) #TODO change to a longer time 
                    week_1_solution = schedule.ses_sur_dict
                else:
                    schedule = inconvenienceProb(waitlist, all_sess, turn_around, obj_type, init_assign = current_solution, perfect_information=perfect_info_bool, time_lim=time_lim_other_weeks)                         

                #store solution in fudged way so don't have to rewrite Tom's code
                inconvenience_sol = get_create_solution(session, 10,
                10, 10, 0)

                #update database
                create_update_solution_assignments(session, inconvenience_sol.id,
                schedule.ses_sur_dict)
                
            # else:
            sess_sur_dict = get_ses_sur_dict(session, inconvenience_sol.id)

            #store week's current solution for next week warm start
            current_solution = sess_sur_dict

            # print(sess_sur_dict)
            # print_detailed_ses_sur_dict(sess_sur_dict, waitlist, plenty_of_sess, turn_around)

            num_sessions_to_plot = 40
            #graph
            create_session_graph(inconvenience_sol, session, db_name, num_sessions_to_plot)

        # count how many surgeries were cancelled due to patient preference
        if perfect_info_bool == False:
            #cancel the surgeries that were inconvenient before solution created (they will stay on waitlist)
            for imperfect_sessions in new_sessions:
                imperfect_sessions = imperfect_sessions.n
                if imperfect_sessions == -1:
                    continue
                sess_sched_obj = list(filter(lambda obj: obj.n == imperfect_sessions, all_sess))[0]
                # get surgeries in session
                surgeries_in_session = sess_sur_dict[imperfect_sessions]
                for surgery in surgeries_in_session:
                    surgery_sched_obj = list(filter(lambda obj: obj.n == surgery, waitlist))[0]
                    # check if inconvenient
                    inconvenient = is_surgery_inconvenient(sess_sched_obj.sdt, simulation_start_date, surgery_sched_obj)
                    if inconvenient:
                        # cancel surgery
                        sess_sur_dict[imperfect_sessions].remove(surgery)
                        cancelled_surgeries.append(surgery)

        #move first 2 weeks of schedule to scheduled if first week, otherwise move first 1 week to scheduled
        scheduled_sessions = new_sessions

        #compute important metrics
        metrics = compute_metrics(waitlist, scheduled_sessions, week, sess_sur_dict, cancelled_surgeries)
        total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100, num_surs_scheduled, num_sessions, num_cancelled, proportion_cancelled = metrics
        metrics_df.loc[len(metrics_df.index)] = [obj_type, perfect_info_string, days_considered_tardy, week, total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100, num_surs_scheduled,num_sessions,num_cancelled, proportion_cancelled]

        #remove scheduled sessions from all_sess and scheduled surgeries from waitlist
        ids_of_surgery_scheduled = []
        for scheduled_session in scheduled_sessions:
            ids_of_surgery_scheduled = ids_of_surgery_scheduled + sess_sur_dict[scheduled_session.n]

        # print(f"len(waitlist){len(waitlist)}")
        # print(f"len(waitlist){len(all_sess)}")
        waitlist = [surgery for surgery in waitlist if surgery.n not in ids_of_surgery_scheduled]
        all_sess = [session for session in all_sess if session not in scheduled_sessions]
        # print(f"len(waitlist){len(waitlist)}")
        # print(f"len(waitlist){len(all_sess)}")

        metrics_df.to_csv(os.path.join(output_db_location_to_use, obj_type.replace(" ", "") + "_specialty_" + str(specialty_id).replace(" ", "") + "_metrics.csv"))


#TODO compare the two schedules

columns_to_summarise=['total tardiness',	'number of patients tardy',	'average wait time (priority < 0.33)',	'average wait_time (0.33 < priority < 0.66)',	'average wait time 0.66 < priority',	'number of surgeries scheduled',	'num surgeries cancelled',	'cancelation proportion']

average_values = metrics_df.groupby('perfect_information_bool')[columns_to_summarise].mean().reset_index()
average_values.to_csv(os.path.join(output_db_location_to_use,"average_values_specialty_{0}.csv".format(str(specialty_id))))
if print_verbose: print(average_values)



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
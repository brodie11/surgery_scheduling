import os
import sys

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd


import pickle

seed = 10

# Perrie's path 
# repo_path = Path("/Users/perriemacdonald/Library/CloudStorage/OneDrive-TheUniversityofAuckland/University/ENGEN700/surgery_scheduling/brodie_perrie_code/src")

# Brodie's path path 
repo_path = Path("C:/Users/Grant Dye/Documents/Uni/Engsci/4th year/part4project/surgery_scheduling/brodie_perrie_code/src")

sys.path.append(str(repo_path))
from configs import OUTPUT_DB_DIR, DATA_FILE, OUTPUT_DB_DIR_TEST
from scheduler_utils import (
  prepare_data, create_schedule_partition_surs, create_schedule_partition_sess)
from solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict)
from visualise import create_session_graph
from solution_classes import get_create_sur, get_create_ses
from helper_funcs import (inconvenienceProb, BetterScheduleObj, compute_metrics, print_detailed_ses_sur_dict,is_surgery_inconvenient, 
                          get_plenty_of_sess, get_operations_which_changed, get_disruption_count_cv, get_priority_and_warning_time_for_all_surgeries_df)
from classes import (schedSurgery, schedSession)
from percentile_functions import (replace_ev_with_percentile, simulate_durations, execute_schedule)

suffix_for_csvs = ""

#choose specialty, faclility, turn_around, etc.
specialty_id = 0
facility = "A"
time_lim_first_week = 200
time_lim_other_weeks = 20
optimality_gap = 0.01
print_verbose = False
turn_around = 15
allowed_overtime = 30
solve_percentiles = True # set to false if want to use the mean and no uncertainty

chance_of_inconvenience_for_each_day_month_week = 0.069
obj_type = "t&p matrix"
#set to true if you want to manually resolve each gurobi problem and ignore stored solutions
solve_anyway = False
#set how long it takes for someone to be considered tardy
months_considered_tardy = 3
days_considered_tardy = round(months_considered_tardy*(365/12)) #try 2 months for next disruption comparison run
#pick start and end periods for simulation
period_start_year = 2015 #can go 2015-3 earliest
period_start_month = 3
period_end_year = 2016 #can go 2016-12 latest
period_end_month = 3
simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 
#make testing = true if running a test or something else where you don't mind the databases being 
#deleted after. Make testing = false otherwise
testing = True
output_db_location_to_use = OUTPUT_DB_DIR
if testing == True: output_db_location_to_use = OUTPUT_DB_DIR_TEST  

#data to collect for simulations
columns = ['iteration','objective type', 'disruptions?', 'perfect_information_bool', 'days_considered_tardy', 'week','num_sessions', 'total tardiness', 'number of patients tardy', 'average wait time (priority < 0.33)', 
           'average wait_time (0.33 < priority < 0.66)', 'average wait time 0.66 < priority',
           'number of surgeries scheduled', 'num sessions', 'num surgeries cancelled', "cancelation proportion",
           ]
metrics_df = pd.DataFrame(columns=columns)
total_tardiness = number_patients_tardy = average_waittime_p33 = average_waittime_p66 = average_waittime_p100 = num_surs_scheduled = avg_session_utilisation = 0

locked_in_dict = {} #for storing ACTUAL assignments of surgeries

#create session for reacing in data like Tom did
engine = create_engine('sqlite:///' + DATA_FILE)
Session = sessionmaker(bind=engine)

# Get all sessions after start date and all surgeries that haven't left by start_date and arrive before end_date
# I modified tom's prepare data function so this works
with Session() as session:
    surgeries, surgical_sessions, specialties = prepare_data(session,
        simulation_start_date, simulation_end_date)

# Filter surgeries and sessions to the specialty and facility of interest.
surgeries_master = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
    (surgeries['facility'] == facility) & (surgeries['planned'] == 1)]
surgical_sessions_master = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
    (surgical_sessions['facility'] == facility) & surgeries['planned'] == 1]

# Convert start_time to datetime if it's not already in datetime format
surgical_sessions_master['start_time'] = pd.to_datetime(surgical_sessions['start_time'])

#whether there are disruption constraints for a given run
is_disruption_considered = True
solve_percentile = False

percentile_value=50

#disruption parameter
#defined as total number of operation-session assignments which can be changed between weeks (this means we can tell people their approximate date with some certainty)
max_disruption_parameter = 14
#max disruption shift
#defined as the maximum amount of days a surgery date can be shifted by in a given week
max_disruption_shift = 14

#these will store disruption metrics
disruption_count_df_csv = None
priority_and_warning_times__csv = None

#do you want graphs each week?
create_graphs = True

#calculate number of weeks:
weeks = (simulation_end_date - simulation_start_date).days // 7

#set up desired number of runs
num_runs = 1
loop = False #set to true to run multiple times with different priority assignments for averaging purposes
for iter in range(num_runs):

    #run both with and without perfect_info_bool
    for perfect_info_bool in [True, False]:

        #list for keeping track of swaps/disruption
        all_swapped_surgery_ids = [[]]

        #for keeping track of when each operation is actually scheduled
        actual_schedule = BetterScheduleObj()

        #for warm starts
        last_week_solution = None
        week_1_solution = None

        #use same patients for both perfect and imperfect info
        surgeries_initial_waitlist, surgeries_to_arrive_partitioned_master = create_schedule_partition_surs(surgeries_master, 
                                    simulation_start_date, simulation_end_date, days_considered_tardy, 
                                    chance_of_inconvenience_for_each_day_month_week,seed=seed)
        all_sess_master, sessions_to_arrive_partitioned_master = create_schedule_partition_sess(surgical_sessions_master, 
                                    simulation_start_date, simulation_end_date)

        #count patients already tardy at start
        number_patients_tardy = len(list(filter(lambda surgery: surgery.dd < 0, surgeries_initial_waitlist)))
        if print_verbose: print(f"number of patients already tardy at start: {number_patients_tardy}")

        #re-load same patients as used for perfect info and non-perfect info by loading in the unchanged master copies
        surgeries = surgeries_master.copy()
        surgical_sessions = surgical_sessions_master.copy()
        waitlist = surgeries_initial_waitlist.copy()
        surgeries_to_arrive_partitioned = surgeries_to_arrive_partitioned_master.copy()
        sessions_to_arrive_partitioned = sessions_to_arrive_partitioned_master.copy()
        all_sess = all_sess_master.copy()

        recently_cancelled_surgeries = []

        for week in range(1, weeks + 1):
            print(f"week: {week}")

            if print_verbose: print(f"\n\nWeek {week}\n------------------------------------------------")

            #collect these so we know which switches between weeks count as disruptions
            new_sessions = []
            new_surgeries = []
            
            #get current week's sessions and surgeries
            if week == 1:
                new_sessions = sessions_to_arrive_partitioned.pop(0) + sessions_to_arrive_partitioned.pop(0)
                new_surgeries = surgeries_to_arrive_partitioned.pop(0) + surgeries_to_arrive_partitioned.pop(0)
            else:
                if sessions_to_arrive_partitioned:
                    new_sessions = sessions_to_arrive_partitioned.pop(0)
                    new_surgeries = surgeries_to_arrive_partitioned.pop(0)

            if not new_sessions and is_disruption_considered==False:
                all_swapped_surgery_ids.append([]) #no ssurgeries swapped this week because no surgeries scheduled
                continue #continue if no new sessions this week and disruption param is false

            #add new surgeries to waitlist
            waitlist = waitlist + new_surgeries

            plenty_of_sess = get_plenty_of_sess(all_sess, waitlist) #make sure there's enough sessions so every surgery scheduled but not too many
            
            #CREATE SCHEDULES

            #make string version of perfect_info_bool
            perfect_info_string = "False"
            if perfect_info_bool == True: perfect_info_string = "True"

            #make string version of is_disruption_considered
            is_disruption_considered_string = "False"
            if is_disruption_considered == True: is_disruption_considered_string = "True"

            #SUFFIXs for experiments
            #use this suffix in the name of any csv output from an experiment over 15 iterations
            suffix_for_csvs = f"s_{specialty_id}_f_{facility}_sd_{simulation_start_date.date()}_ed_{simulation_end_date.date()}_"
            suffix_for_csvs += f"pi_{'T' if perfect_info_string == 'True' else 'F'}_idc_{'T' if is_disruption_considered else 'F'}_mdp_{max_disruption_parameter}_"
            suffix_for_csvs += f"mds_{max_disruption_shift}_ipc_{'T' if solve_percentile else 'F'}_pv_{percentile_value}_ao_{allowed_overtime}_dct_{days_considered_tardy}_"
            suffix_for_csvs += f"tl_{time_lim_other_weeks}_og_{optimality_gap}"
            #use this suffix for any one itertion run
            suffix_for_iter = f"i_{iter}_" + suffix_for_csvs
            #use this suffix for storing solutions in databases for a given week
            suffix_for_week = f"w_{week}_" + suffix_for_iter

            #set up session to store specific week
            # db_name = 'specialty_{0}_start_{1}_end_{2}_week_{3}_prob_type_{4}_pi_{5}_dct_{6}_disrup_{7}_dp_{8}_ds_{9}_l_{10}.db'.format(specialty_id,
            # simulation_start_date.date(), simulation_end_date.date(), week, obj_type.replace(" ", ""),  perfect_info_string, str(days_considered_tardy), 
            # is_disruption_considered_string, str(max_disruption_parameter), str(max_disruption_shift), str(iter))
            db_name = os.path.join(output_db_location_to_use, suffix_for_week + ".db")

            if print_verbose: print(f"db name {db_name}")

            engine = create_engine('sqlite:///' + db_name)

            Base.metadata.create_all(engine)

            Session = sessionmaker(bind=engine)
            with Session() as session:

                #get solution and check if already been solved
                # TODO: check if solution has been solved for specified percentile
                inconvenience_sol = get_solution(session, 10, 10, 10) #fudge a little bit so I don't have to rewrite Tom's code
                if inconvenience_sol is None or solve_anyway:
                    # change ed to percentile value if using percentiles
                    if solve_percentiles:
                        waitlist = replace_ev_with_percentile(waitlist, percentile_value)
                    for surgery in waitlist:
                        get_create_sur(session, surgery.n, surgery.ed, surgery.priority)
                    for sess in plenty_of_sess:
                        get_create_ses(session, sess.n, simulation_start_date + pd.Timedelta(days=sess.sdt), sess.tn, sess.sd)

                    #otherwise, solve it  
                    #this is the class that solves the linear program
                    #perfect_info_schedule = inconvenienceProb(waitlist, plenty_of_sess, turn_around, obj_type=obj_type, perfect_information=True, time_lim=30)
                    if week == 1:
                        print(f"iter{iter}")
                        schedule = inconvenienceProb(iter, waitlist, all_sess, turn_around, obj_type, 
                                                     is_disruption_considered, max_disruption_parameter, 
                                                     max_disruption_shift, init_assign = week_1_solution, 
                                                     perfect_information=perfect_info_bool, time_lim=time_lim_first_week,
                                                     optimality_gap=optimality_gap, seed=seed) #TODO change to MIPGap rather than timelim
                        week_1_solution = schedule.ses_sur_dict
                    else:
                        schedule = inconvenienceProb(iter, waitlist, all_sess, turn_around, obj_type, 
                                                        is_disruption_considered, max_disruption_parameter, 
                                                        max_disruption_shift, init_assign = last_week_solution, 
                                                        perfect_information=perfect_info_bool, 
                                                        time_lim=time_lim_other_weeks, new_sessions=new_sessions, 
                                                        optimality_gap=optimality_gap,seed=seed)

                    #store solution in fudged way so don't have to rewrite Tom's code
                    inconvenience_sol = get_create_solution(session, 10,
                    10, 10, 0)

                    #update database
                    create_update_solution_assignments(session, inconvenience_sol.id,
                    schedule.ses_sur_dict)
                    
                # else:
                sess_sur_dict = get_ses_sur_dict(session, inconvenience_sol.id)
 
                #collect list of all surgeries that were swpped between weeks
                if last_week_solution != None:     

                    # for Brodie debugging
                    if week >= 5:
                        print("yo")

                    list_of_swapped_surgey_ids = get_operations_which_changed(last_week_solution, sess_sur_dict, new_surgeries, recently_cancelled_surgeries)
                    all_swapped_surgery_ids.append(list_of_swapped_surgey_ids)

                    for list_of_swapped_surgery_id in list_of_swapped_surgey_ids:
                        if list_of_swapped_surgery_id == 5886:
                            print("huh?")
                        print(f"Considering surgery {list_of_swapped_surgery_id}")
                        for ses_1_id, surgeries_1 in last_week_solution.items():
                            for surgery_1 in surgeries_1:
                                if surgery_1 == list_of_swapped_surgery_id:
                                    print(f"surgery{surgery_1} in session{ses_1_id} in oldschedule and ")
                        for ses_2_id, surgeries_2 in sess_sur_dict.items():
                            for surgery_2 in surgeries_2:
                                if surgery_2 == list_of_swapped_surgery_id:
                                    print(f"surgery{surgery_2} in session{ses_2_id} in newschedule and ")
                        print("------------------------------------")

                
                last_week_solution = sess_sur_dict

                #limit number of sessions to plot to 40
                num_sessions_to_plot = len(plenty_of_sess) + 10

                #graph
                if create_graphs: create_session_graph(inconvenience_sol, session, db_name, num_sessions_to_plot)

            simulated_durations = simulate_durations(new_sessions, waitlist, sess_sur_dict)

            # execute the schedule
            utilisation, overtime, num_cancelled_over, num_cancelled_pref, time_operating, completed_surgeries, cancelled_surgeries = execute_schedule(simulated_durations, sess_sur_dict, new_sessions, waitlist, turn_around, allowed_overtime, simulation_start_date)
            # get number of surgeries cancelled for each reason
            total_cancelled_over = sum(num_cancelled_over)
            total_cancelled_pref = sum(num_cancelled_pref)
            # # count how many surgeries were cancelled due to patient preference
            # if perfect_info_bool == False:
            #     #cancel the surgeries that were inconvenient before solution created (they will stay on waitlist)
            #     for imperfect_sessions in new_sessions:
            #         imperfect_sessions = imperfect_sessions.n
            #         if imperfect_sessions == -1:
            #             continue
            #         sess_sched_obj = list(filter(lambda obj: obj.n == imperfect_sessions, all_sess))[0]
            #         # get surgeries in session
            #         surgeries_in_session = sess_sur_dict[imperfect_sessions]
            #         for surgery in surgeries_in_session:
            #             surgery_sched_obj = list(filter(lambda obj: obj.n == surgery, waitlist))[0]
            #             # check if inconvenient
            #             inconvenient = is_surgery_inconvenient(sess_sched_obj.sdt, simulation_start_date, surgery_sched_obj)
            #             if inconvenient:
            #                 # cancel surgery
            #                 sess_sur_dict[imperfect_sessions].remove(surgery)
            #                 cancelled_surgeries.append(surgery)

            #move first 2 weeks of schedule to scheduled if first week, otherwise move first 1 week to scheduled
            scheduled_sessions = new_sessions

            #compute important metrics (cancelled due to preferences)
            metrics = compute_metrics(waitlist, scheduled_sessions, week, completed_surgeries, total_cancelled_pref)
            num_sessions, total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100, num_surs_scheduled, num_sessions, num_cancelled, proportion_cancelled = metrics
            metrics_df.loc[len(metrics_df.index)] = [iter, obj_type, is_disruption_considered_string, perfect_info_string, days_considered_tardy, week, num_sessions, total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100, num_surs_scheduled,num_sessions,num_cancelled, proportion_cancelled]
            metrics_df_file_name = "{0}_specialty_{1}_metrics_disruption{2}_mds_{3}_mdp_{4}.csv".format(obj_type.replace(" ", ""), str(specialty_id), is_disruption_considered_string, max_disruption_shift, max_disruption_parameter)
            metrics_df.to_csv(os.path.join(output_db_location_to_use, metrics_df_file_name))
            
            for scheduled_session in scheduled_sessions:
                #add to master schedule
                surgery_ids = sess_sur_dict[scheduled_session.n]
                actual_schedule.fill_session(scheduled_session, [surgery for surgery in waitlist if surgery.n in surgery_ids])
            
            all_sess = [session for session in all_sess if session not in scheduled_sessions]
            waitlist = [surgery for surgery in waitlist if surgery.n not in completed_surgeries]

        recently_cancelled_surgeries = cancelled_surgeries
        #CALCULATE DISCRUPTION PARAMATERS - Brodie's don't delete

    #     #get disruption count
    #     disruption_count_df_current = get_disruption_count_cv(all_swapped_surgery_ids)
    #     disruption_count_df_current['iter'] = iter
    #     disruption_count_df_current['perfect_information_bool'] = perfect_info_bool

    #     #get disrupton count and priority and warning time dfs
    #     disruption_count_df_current_iter = get_disruption_count_cv(all_swapped_surgery_ids)
    #     priority_and_warning_times_df_current_iter = get_priority_and_warning_time_for_all_surgeries_df(all_swapped_surgery_ids, disruption_count_df_current_iter , actual_schedule)

    #     #store concatonations of these for csv purposes
    #     if iter == 1 and perfect_info_bool == True:
    #         disruption_count_df_csv = disruption_count_df_current_iter
    #         priority_and_warning_times__csv = priority_and_warning_times_df_current_iter
    #     else:
    #         disruption_count_df_csv = pd.concat([disruption_count_df_csv, disruption_count_df_current_iter], axis=0)
    #         priority_and_warning_times_df_csv = pd.concat([priority_and_warning_times_df_csv, priority_and_warning_times_df_current_iter], axis = 0)
        

    # #save variable
    # with open('all_swapped_surgery_ids.pkl', 'wb') as file:
    #     pickle.dump(all_swapped_surgery_ids, file)



    if loop == False:
        break



#get count

#add dictionary to list

#TODO compare the two schedules
columns_to_summarise=['num_sessions', 'total tardiness','number of patients tardy',	'average wait time (priority < 0.33)',	
                      'average wait_time (0.33 < priority < 0.66)',	'average wait time 0.66 < priority',	
                      'number of surgeries scheduled',	'num surgeries cancelled',	'cancelation proportion']

average_values = metrics_df.groupby('perfect_information_bool')[columns_to_summarise].mean().reset_index()
average_values.to_csv(os.path.join(output_db_location_to_use,"average_values_" + suffix_for_csvs))
if print_verbose: print(average_values)

#For Brodie don't delete
# #make disruption count and priority and waittimes csvs
# disruption_filename = "discruption_count_mds_{0}_mdp_{1}.csv".format(max_disruption_shift, max_disruption_parameter)
# disruption_count_df_csv.to_csv(os.path.join(output_db_location_to_use, disruption_filename))

# pwt_filename = "priority_and_warning_times_mds_{0}_mdp_{1}.csv".format(max_disruption_shift, max_disruption_parameter)
# priority_and_warning_times_df_csv.to_csv(os.path.join(output_db_location_to_use, pwt_filename))



#NEXT STEPS
#think about adding different disruption parameters for different specialties
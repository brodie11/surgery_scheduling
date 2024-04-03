#imports
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd
import math

from ..configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from ..scheduler_utils import (
  prepare_data, create_schedule_surs, create_schedule_sess)
from ..scheduler_classes import (schedProb, priorityProb)
from ..solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers, 
  get_sessions, get_surgeries, get_solution_assignments, get_solution_transfers)
from ..visualise import create_session_graph



def generate_schedule_that_minimises_transfers_and_undertime(start_date, end_date, turn_around = 15, specialty_id = 4,facility = 'A',time_lim = 300, solve_first_time=False):
    
    min_under_lex_dict = None

    engine = create_engine('sqlite:///' + DATA_FILE)
    Session = sessionmaker(bind=engine)

    # Read in data from the database.
    with Session() as session:
        surgeries, surgical_sessions, specialties = prepare_data(session,
        start_date, end_date)
        
    # Filter surgeries and sessions to the specialty and facility of interest.
    surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
        (surgeries['facility'] == facility)]
    surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
        (surgical_sessions['facility'] == facility)]

    # Use the parameters to set the name of the output database, and create it
    # if it deosn't already exist.
    db_name = 'specialty_{0}_start_{1}_end_{2}.db'.format(specialty_id,
        start_date.date(), end_date.date())
    db_name = os.path.join(OUTPUT_DB_DIR, db_name)

    engine = create_engine('sqlite:///' + db_name)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Create the objects (surgeries and sessions) that the scheduling code
        # uses, from the data. Sort according to priority and start time.
        sched_surs = create_schedule_surs(surgeries, session)
        sched_sess = create_schedule_sess(surgical_sessions, session)

        sched_surs = sorted(sched_surs, key=lambda x: x.priority, reverse=True)
        sched_sess = sorted(sched_sess, key=lambda x: x.sdt)

        session.commit()

        # Create and solve the problem where priority is strictly enforced, no-one
        # can go ahead of someone if they are lower priority that them.
        priority_prob = priorityProb(sched_surs, sched_sess, turn_around)
        pri_sol = get_create_solution(session, 1, 0, 0, priority_prob.obj)
        create_update_solution_assignments(session, pri_sol.id,
        priority_prob.ses_sur_dict)
        graph_name = 'specialty_{0}_start_{1}_end_{2}_strict_priority'.format(specialty_id,
        start_date.date(), end_date.date())
        create_session_graph(pri_sol, session, graph_name)

        # Create and solve the problem where there are no justified transfers,
        # people can go ahead of others that are higher priority than them, but
        # only if the higher priority patient can't fit in the session.
        no_transfer_prob = schedProb(sched_surs, sched_sess, turn_around, time_lim,
        0, 0, priority_prob.ses_sur_dict, None)
        no_transfer_sol = get_create_solution(session, -1,
            0, 0, no_transfer_prob.prob.obj_val)
        create_update_solution_assignments(session, no_transfer_sol.id,
        no_transfer_prob.ses_sur_dict)
        graph_name = 'specialty_{0}_start_{1}_end_{2}_transfer_0'.format(specialty_id,
        start_date.date(), end_date.date())
        create_session_graph(no_transfer_sol, session, graph_name)
        
        # Check if the lexicograhoic solution has been found already. If it has we
        # don't want to spend time finding it again.
        min_under_lex_sol = get_solution(session, -1, None, 1)

        if min_under_lex_sol is None or solve_first_time==True:
        # If we don't have it we need to find the solution that has the fewest
        # transfers while still minimising the undertime. First we solve the
        # problem of just minimising undertime. Then given this minimum undertime
        # value we minimise the number of transfers subject to the minimum
        # undertime as a constraint.
            min_under_prob = schedProb(sched_surs, sched_sess, turn_around,
                time_lim, 0, None)
            util_obj = min_under_prob.prob.obj_val

            min_under_prob_lex = schedProb(sched_surs, sched_sess, turn_around,
                time_lim, 0, -1, min_under_prob.ses_sur_dict, util_obj)

            min_under_lex_sol = get_create_solution(session, -1,
                min_under_prob_lex.prob.obj_val, 1, util_obj)

            create_update_solution_assignments(session, min_under_lex_sol.id,
                min_under_prob_lex.ses_sur_dict)
            create_update_solution_transfers(session, min_under_lex_sol.id,
                min_under_prob_lex)
            
            min_under_lex_dict = min_under_prob.ses_sur_dict

        else:
            min_under_lex_dict = get_ses_sur_dict(session, min_under_lex_sol.id)

        graph_name = 'specialty_{0}_start_{1}_end_{2}_min_under'.format(specialty_id,
        start_date.date(), end_date.date())
        create_session_graph(min_under_lex_sol, session, graph_name)

        return min_under_lex_dict
    
def get_all_sessions_and_surgeries(start_date, end_date, specialty_id = 4, facility = 'A', time_lim = 300):
    #get list of all sessions
    # Set the value of the parameters.
    engine = create_engine('sqlite:///' + DATA_FILE)
    Session = sessionmaker(bind=engine)
    # Read in data from the database.
    with Session() as session:
        surgeries, surgical_sessions, specialties = prepare_data(session,
        start_date, end_date)
    # Filter surgeries and sessions to the specialty and facility of interest.
    surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
        (surgeries['facility'] == facility)]
    surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
        (surgical_sessions['facility'] == facility)]
    
     # Use the parameters to set the name of the output database, and create it
    # if it deosn't already exist.
    db_name = 'specialty_{0}_start_{1}_end_{2}.db'.format(specialty_id,
        start_date.date(), end_date.date())
    db_name = os.path.join(OUTPUT_DB_DIR, db_name)
    
    engine = create_engine('sqlite:///' + db_name)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Create the objects (surgeries and sessions) that the scheduling code
        # uses, from the data. Sort according to priority and start time.
        sched_surs = create_schedule_surs(surgeries, session)
        sched_sess = create_schedule_sess(surgical_sessions, session)

        sched_surs = sorted(sched_surs, key=lambda x: x.priority, reverse=True)
        sched_sess = sorted(sched_sess, key=lambda x: x.sdt)
    
    return sched_surs, sched_sess

def simulate_stochastic_durations(percentile, schedDict:dict, simulation_start_date, simulation_end_date, specialty_id = 4, facility="A"):
    print("\n Session surgery dictionary")
    print(schedSurgery_for_percentile)
    print("\n")

    #initialise return values
    total_mins_overtime, num_overtime, num_surgeries_completed, total_surgery_utilisation = 0,0,0,0

    #get all sessions and surgeries
    sched_surs, sched_sess = get_all_sessions_and_surgeries(simulation_start_date, simulation_end_date, )

    #for each session in dictionary
    for session_id, surgery_array in schedDict.items():
        #get info about this session such as duration
        sess = [session for session in sched_sess if session.n == session_id]
        session_duration = sess.sd

        combined_surgery_duration = 0
        #for each surgery in session
        for sur in surgery_array:
            #get duration randomly from lognormal distribution and add to total duration
            duration_mean = sur.ed
            duration_variance = sur.dv
            #SIMULATE DURATION
            # Calculate the shape parameter (s) of the lognormal distribution
            s = np.sqrt(np.log(1 + variance / ev**2))
            # Calculate the scale parameter (scale) of the lognormal distribution
            scale = np.exp(ev - 0.5 * s**2)
            # Generate random values from the lognormal distribution
            random_values = lognorm.rvs(s, scale=scale, size=size)


            #increment number of surgeries completed
        
        #calculate surgery utilisation
        #increment num_overtime and add to total_mins_overtime if appropriate

    return total_mins_overtime,num_overtime, num_surgeries_completed, total_surgery_utilisation

#set up pandas dataframe to store everything
best_percentile_df = pd.DataFrame(columns=['Percentile Value', 'Month from start', 'Number of Surgeries that ran overtime', 'Number of surgeries completed', 'Surgery Utilisation', 'Total Mins Overtime'])

# Pick a few different percentile values to use as mean surgery duration eg. (45,50,55,60,65)
percentile_values = [45,50,55,60,65]
# Calculate percentile value based on distribution to use instead of mean when scheduling
# For each percentile value:
percentile_column_names = ['duration_45th_percentile', 'duration_50th_percentile', 'duration_55th_percentile', 'duration_60th_percentile', 'duration_65th_percentile']
# Use tom’s code to generate a schedule for each month

#TODO figure out which facility is best to use
#TODO figure out the valid date range for that facility eg. March 2014 - Feb 2016
#TODO pick trainign months and testing months

#pick start and end periods for simulation
period_start_year = 2015
period_start_month = 6
period_end_year = 2016
period_end_month = 12
simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 
# Create a list of pd.Timestamp objects for the first day of each month
month_starts = [pd.Timestamp(year=year, month=month, day=1) 
                   for year in range(period_start_year, period_end_year + 1) 
                   for month in range(period_start_month if year == period_start_year else 1, 
                                       period_end_month + 1 if year == period_end_year else 13)]

#remove last month
month_starts = month_starts[0:-1]

#set up specialty and facility
specialty = 4
facility = 'A'

# For each Month:
schedules = [] #array of tuples (start_date, ses_sur_dict)

for month_start in month_starts: #and each month
    #Find the solution that has the fewest transfers while still minimising the undertime
    schedSurgery_for_percentile = generate_schedule_that_minimises_transfers_and_undertime(
        start_date=month_start,end_date=month_start + pd.DateOffset(months=1),
        turn_around = 15, specialty_id = specialty, facility = facility, time_lim = 300, 
        solve_first_time=True)
    schedules.append((month_start, schedSurgery_for_percentile))

    break #TODO remove this

for i,percentile_column_name in enumerate(percentile_column_names): #for each percentile
    percentile_value = percentile_values[i]
    for month_from_start, schedules_tuple in enumerate(schedules):
        total_mins_overtime_avg,num_overtime_avg, num_surgeries_completed_avg, total_surgery_utilisation_avg = (0,0,0,0)
        for i in range(100):
            #simulate 100 runs of sched_surgery_for_percentile
            total_mins_overtime,num_overtime, num_surgeries_completed, total_surgery_utilisation = simulate_stochastic_durations(
                percentile_value, schedSurgery_for_percentile, simulation_start_date,
                simulation_end_date, specialty_id=4)
            #take average values
            total_mins_overtime_avg += total_mins_overtime / 100
            num_overtime_avg += num_overtime / 100
            num_surgeries_completed_avg += num_surgeries_completed / 100
            total_surgery_utilisation_avg += total_surgery_utilisation / 100

        # append data to df
        new_row = [percentile_column_name, month_from_start, num_overtime_avg, num_surgeries_completed_avg, total_surgery_utilisation_avg, total_mins_overtime_avg]
        best_percentile_df.loc[len(best_percentile_df.index)] = new_row
    #...
        
# Count how many surgeries are completed without running overtime (c) and how many run overtime (o)
# Average c and o across each month and plot against percentile values

#TODO evenutally run for different specialties and surgeries

#test
print(len(best_percentile_df))
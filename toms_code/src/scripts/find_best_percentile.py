#imports
import os
import sys
import numpy as np
from scipy.stats import lognorm

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

def replace_ev_with_percentile(sched_surs, percentile):
    """
    replaces the expected value of sched_surs object used to represent surgeries in scheduling with 
    percentile value specified

    input: array of sched_surs, percentile value eg. 60
    output: array of equal length with ev in sched_surs replaced with percentile value
    """

    for sched_sur in sched_surs:
        #get ev and variance
        ed = sched_sur.ed
        dv = sched_sur.dv
        # Calculate the scale parameter (s) and shape parameter (sigma) of the lognormal distribution
        s = ed
        sigma = dv ** 0.5
        
        # Calculate the percentile value using the lognorm module
        percentile_value = lognorm.ppf(percentile / 100, s=s, scale=np.exp(sigma))
        sched_sur.ev = percentile_value

    return sched_surs


def generate_schedule_that_minimises_transfers_and_undertime(percentile_value,start_date, end_date, turn_around = 15, specialty_id = 4,facility = 'A',time_lim = 300, solve_first_time=False):
    """
    Generates schedule for a given percentile value, month, facility, specialty, etc.

    output: session_surgery_dictionary with session id as keys and array of surgery ids as values
    """


    min_under_lex_dict = None

    #get sessions and surgeries in given timeframe, facility, etc.

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
    
    #set up storage of solutions so don't have to resolve

    # Use the parameters to set the name of the output database, and create it
    # if it deosn't already exist.
    db_name = 'specialty_{0}_start_{1}_end_{2}_percentile{3}.db'.format(specialty_id, #TODO make it so this stores each percentile value as well as each month
        start_date.date(), end_date.date(), percentile_value)
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

        #replace mean with percentile

        sched_surs = replace_ev_with_percentile(sched_surs, percentile_value)

        #solve

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

        #solve if never solved before for a given month and percentile

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
            
            #get dictionary

            min_under_lex_dict = min_under_prob.ses_sur_dict

        else:
            #otherwise simply get dictionary from solution object

            min_under_lex_dict = get_ses_sur_dict(session, min_under_lex_sol.id)

        #graph
        graph_name = 'specialty_{0}_start_{1}_end_{2}_min_under_percentile{3}'.format(specialty_id,
        start_date.date(), end_date.date(), percentile_value)
        create_session_graph(min_under_lex_sol, session, graph_name)

    return min_under_lex_dict
    
def get_all_sessions_and_surgeries(simulation_start_date, simulation_end_date, percentile_value, specialty_id = 4, facility = 'A', time_lim = 300):
    
    """
    Return all sessions and surgeries as sched_sess and shed_sur for purposes of relating them to session id and surgery id

    input: simulation_start_date (start of whole period simulating over),simulation_end_date (end of whole period simulating over)
    output: array of schedSurgery and schedSession objects

    """
    #get list of all sessions
    # Set the value of the parameters.
    engine = create_engine('sqlite:///' + DATA_FILE)
    Session = sessionmaker(bind=engine)
    # Read in data from the database.
    with Session() as session:
        surgeries, surgical_sessions, specialties = prepare_data(session,
        simulation_start_date, simulation_end_date)
    # Filter surgeries and sessions to the specialty and facility of interest.
    surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
        (surgeries['facility'] == facility)]
    surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
        (surgical_sessions['facility'] == facility)]
     # Use the parameters to set the name of the output database, and create it
    # if it deosn't already exist.
    db_name = 'specialty_{0}_start_{1}_end_{2}_percentile_{3}.db'.format(specialty_id,
        simulation_start_date.date(), simulation_end_date.date(), percentile_value)
    db_name = os.path.join(OUTPUT_DB_DIR, db_name)
    engine = create_engine('sqlite:///' + db_name)
    Base.metadata.create_all(engine)
    sched_surs, sched_sess = None, None
    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Create the objects (surgeries and sessions) that the scheduling code
        # uses, from the data. Sort according to priority and start time.
        sched_surs = create_schedule_surs(surgeries, session)
        sched_sess = create_schedule_sess(surgical_sessions, session)
        sched_surs = sorted(sched_surs, key=lambda x: x.priority, reverse=True)
        sched_sess = sorted(sched_sess, key=lambda x: x.sdt)
    return sched_surs, sched_sess

def simulate_stochastic_durations(schedDict:dict, simulation_start_date, simulation_end_date, percentile_value,turn_around=15):
    """
    does one simulation run of surgery durations 
    based on their lognormal distribution. Calculates metrics
    of interest like total_mins_overtime, 
    num_sessions_that_run_overtime, 
    num_sessions_with_cancelled_surgeries, 
    num_surgeries_completed, 
    average_surgery_utilisation.

    Note: We assume a surgery is allowed to go ahead so long
    as its expected time won't put the session overtime by 
    more than 30 min. Otherwise, the surgery is cancelled

    output:
    num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled
    
    """

    #setup

    #initialise return values
    num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled = 0,0,0,0,0,0
    average_surgery_utilisation_array = []
    #get all sessions and surgeries
    sched_surs, sched_sess = get_all_sessions_and_surgeries(simulation_start_date, simulation_end_date, percentile_value, specialty_id = 4, facility = 'A', time_lim = 300)

    #simulation

    #for each session in dictionary
    for session_id, surgery_array in schedDict.items():
        if session_id == -1:
            continue
        # print(f"Session id: {session_id}")
        #get info about this session such as duration

        sess_matches = [session for session in sched_sess if session.n == session_id]
        sess = sess_matches[0]
        session_duration = sess.sd
        # print(f"Session duration: {session_duration}")
        combined_surgery_duration = 0
        ran_overtime = False
        #for each surgery in session
        for surgery_id in surgery_array:
            # print(f"    surgery_id: {surgery_id}")
            #find surgery object
            
            try:
                sur = [sur for sur in sched_surs if sur.n == surgery_id][0]
            except Exception as e:
                print("An error occurred:", e)
                return -1, -1, -1, -1, -1, -1
            #get duration randomly from lognormal distribution and add to total duration
            duration_mean = sur.ed
            # print(f"    surgery_duration_mean: {duration_mean}")
            duration_variance = sur.dv
            #SIMULATE DURATION
            # Calculate the mean (mu) and standard deviation (sigma) of the corresponding normal distribution
            mu = np.log(duration_mean / np.sqrt(1 + duration_variance / duration_mean**2))
            sigma = np.sqrt(np.log(1 + duration_variance / duration_mean**2))
            duration = np.random.lognormal(mean=mu, sigma=sigma, size=1)[0]
            # print(f"    surgery_duration_simulated: {duration}")
            #check if there's time left for this surgery
            if combined_surgery_duration + duration_mean + turn_around < session_duration + 30:
                #if not first surgery, add turn_around_time
                if surgery_id != surgery_array[0]:
                    combined_surgery_duration += turn_around
                #perform surgery
                combined_surgery_duration += duration
                num_surgeries_completed += 1
            else:
                #if surgery will probably take more than 30 mins overtime then increment cancellation metrics accordingly and stop surgeries for day
                cancelled_surgery_index = surgery_array.index(surgery_id)
                num_surgeries_cancelled += len(surgery_array[cancelled_surgery_index:])
                # print(f"Surgeries cancelled! num_surgeries_cancelled = {num_surgeries_cancelled}")
                # print(f"All surgeries: {surgery_array}")
                num_sessions_with_cancelled_surgeries += 1
                break
        # print(f"Combined surgery duration: {combined_surgery_duration}")
        #if ran overtime then record overtime metrics accordingly
        if combined_surgery_duration > session_duration:
            total_mins_overtime += combined_surgery_duration - session_duration
            num_sessions_that_run_overtime += 1
        #caclulate utilisation
        average_surgery_utilisation_array.append(combined_surgery_duration / session_duration)
    average_surgery_utilisation = sum(average_surgery_utilisation_array)/len(average_surgery_utilisation_array)

    #return metrics
    return num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled


if __name__ == '__main__':

    #set up pandas dataframe to store everything
    best_percentile_df = pd.DataFrame(columns = ["i", "percentile_column_name", "month_start", "num_surgeries_completed", "average_surgery_utilisation", "total_mins_overtime", "num_sessions_that_run_overtime", "num_sessions_with_cancelled_surgeries", "num_surgeries_cancelled"]
    )

    # Pick a few different percentile values to simulate for eg. (45,50,55,60,65)
    percentile_values = [45]
    percentile_column_names = ['duration_45th_percentile', 'duration_50th_percentile', 'duration_55th_percentile', 'duration_60th_percentile', 'duration_65th_percentile']
    percentile_column_names = ['duration_45th_percentile'] #TODO remove

    #TODO figure out which facility is best to use
    #TODO figure out the valid date range for that facility eg. March 2014 - Feb 2016
    #TODO pick trainign months and testing months

    #pick start and end periods for simulation
    period_start_year = 2016 #can go 2015-3 earliest
    period_start_month = 2
    period_end_year = 2016 #can go 2016-12 latest
    period_end_month = 5
    simulation_start_date = pd.Timestamp(year=period_start_year, month=period_start_month, day=1) 
    simulation_end_date = pd.Timestamp(year=period_end_year, month=period_end_month, day=1) 
    # Create a list of pd.Timestamp objects for the first day of each month
    month_starts = [pd.Timestamp(year=year, month=month, day=1) 
                    for year in range(period_start_year, period_end_year + 1) 
                    for month in range(period_start_month if year == period_start_year else 1, 
                                        period_end_month + 1 if year == period_end_year else 13)]

    #remove last month
    month_starts = month_starts[0:-1]

    #set up specialty and facility to simulate for
    specialty = 4
    facility = 'A'

    #store schedules in here as well as dataframe
    schedules = [] #array of tuples (start_date, percentile_value, ses_sur_dict)

    # For each percentile value and month find the schedules. Then simulate the durations 100 times and calculate 
    # key metrics

    for i,percentile_column_name in enumerate(percentile_column_names): #for each percentile
        percentile_value = percentile_values[i]
        for month_start in month_starts: #and each month
            #Find the solution that has the fewest transfers while still minimising the undertime for given month and percentile
            sched_sur_dict = generate_schedule_that_minimises_transfers_and_undertime(
                percentile_value, month_start,month_start + pd.DateOffset(months=1),
                turn_around = 15, specialty_id = specialty, facility = facility, time_lim = 300, 
                solve_first_time=False)
            schedules.append((month_start,percentile_column_name,sched_sur_dict))

            #simulate durations 100 times
            num_runs = 100
            for j in range(num_runs):
                #simulate 100 runs of sched_surgery_for_percentile
                result = simulate_stochastic_durations(
                    sched_sur_dict, simulation_start_date,
                    simulation_end_date, percentile_value)
                #get metrics from temporary result variable
                num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled = result
                    # append data to df
                new_row = [j, percentile_column_name, month_start, num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled]
                best_percentile_df.loc[len(best_percentile_df.index)] = new_row

    print(best_percentile_df)
        
    # Count how many surgeries are completed without running overtime (c) and how many run overtime (o)
    # Average c and o across each month and plot against percentile values

    #TODO evenutally run for different specialties and surgeries
    best_percentile_df.to_csv(os.path.join(OUTPUT_DB_DIR, "percentile_metrics.csv"), index=False)
    
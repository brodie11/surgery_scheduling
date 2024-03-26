#imports
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

from ..configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from ..scheduler_utils import (
  prepare_data, create_schedule_surs, create_schedule_sess)
from ..scheduler_classes import (schedProb, priorityProb)
from ..solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers, 
  get_sessions, get_surgeries, get_solution_assignments, get_solution_transfers)
from ..visualise import create_session_graph

def data_setup(start_date, end_date, specialty_id):
    engine = create_engine('sqlite:///' + DATA_FILE)
    Session = sessionmaker(bind=engine)

    # Read in data from the database.
    with Session() as session:
        surgeries, surgical_sessions, specialties = prepare_data(session,
        start_date, end_date)

    # Use the parameters to set the name of the output database, and create it
    # if it deosn't already exist.
    db_name = 'specialty_{0}_start_{1}_end_{2}.db'.format(specialty_id,
        start_date.date(), end_date.date())
    db_name = os.path.join(OUTPUT_DB_DIR, db_name)

    engine = create_engine('sqlite:///' + db_name)
    Base.metadata.create_all(engine)
    
    return engine,surgeries, surgical_sessions, specialties

def generate_schedule_that_minimises_transfers_and_undertime(surgeries, schedules, turn_around = 15, specialty_id = 4, facility = 'A',start_date, end_date, time_lim = 300):
    #inputs: surgeries,schedules -- pandas dataframes; (everything else slef-explanatory)
    #outputs: sschedProb
    engine, surgeries, surgical_sessions, specialties = data_setup(start_date, end_date, specialty_id)
    # Filter surgeries and sessions to the specialty and facility of interest.
    surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
        (surgeries['facility'] == facility)]
    surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
        (surgical_sessions['facility'] == facility)]

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Create the objects (surgeries and sessions) that the scheduling code
        # uses, from the data. Sort according to priority and start time.
        sched_surs = create_schedule_surs(surgeries, session)
        sched_sess = create_schedule_sess(surgical_sessions, session)

        sched_surs = sorted(sched_surs, key=lambda x: x.priority, reverse=True)
        sched_sess = sorted(sched_sess, key=lambda x: x.sdt)

        session.commit()
    
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

        # We should never need more than the number of transfers needed here
        max_transfers = min_under_lex_sol.transfers_allowed

        sol_assigns = get_solution_assignments(session, min_under_lex_sol.id)
        sol_transfers = get_solution_transfers(session, min_under_lex_sol.id)

        sessions = get_sessions(session)
        sessions = sessions.sort_values('start_datetime')
        surgeries = get_surgeries(session)

        ses_num = 0
        for i, ses in sessions.iterrows():
            ses_assigns = surgeries.loc[sol_assigns.loc[
                sol_assigns['session_id'] == ses.name, 'surgery_id'], ]
            ses_assigns = ses_assigns.sort_values('priority', ascending=False)

            for j, sur in ses_assigns.iterrows():
                print(sur)




    return min_under_lex_sol.id, min_under_lex_sol.


#set up pandas dataframe to store everything
best_percentile_df = pd.DataFrame(columns=['Percentile Value', 'Number of Surgeries that ran overtime', 'Number of surgeries completed', 'Surgery Utilisation'])

# Pick a few different percentile values to use as mean surgery duration eg. (45,50,55,60,65)
percentile_values = [45,50,55,60,65]
# Calculate percentile value based on distribution to use instead of mean when scheduling
# For each percentile value:
percentile_column_names = ['duration_45th_percentile', 'duration_50th_percentile', 'duration_55th_percentile', 'duration_60th_percentile', 'duration_65th_percentile']
# Use tom’s code to generate a schedule for each month

#TODO figure out which facility is best to use
#TODO figure out the valid date range for that facility eg. March 2014 - Feb 2016
#TODO pick trainign months and testing months

schedules = [] #array of tuples (percentile_column_name, schedSurgery object)
month_starts = []
# For each Month:
for month_start in month_starts:
    # Simulate surgery durations using distribution 100 times
    for i,percentile_column_name in enumerate(percentile_column_names):
        percentile_value = percentile_values[i]
        #...
        #Find the solution that has the fewest transfers while still minimising the undertime
        schedSurgery_for_percentile = generate_schedule_that_minimises_transfers_and_undertime()
        schedules.append((percentile_column_name, schedSurgery_for_percentile))
        for i in range(100):
            #simulate 100 runs of sched_surgery_for_percentile
            num_overtime, num_surgeries_completed, surgery_utilisation = simulate_stochastic_durations(schedSurgery_for_percentile)
            # append data to df
            new_row = {'Percentile Value': percentile_column_name, 'Number of Surgeries that ran overtime': num_overtime, 'Number of surgeries completed': num_surgeries_completed, 'Surgery Utilisation': surgery_utilisation}
            best_percentile_df = best_percentile_df.append(new_row, ignore_index=True)
    #...
        
# Count how many surgeries are completed without running overtime (c) and how many run overtime (o)
# Average c and o across each month and plot against percentile values

#TODO evenutally run for different specialties and surgeries
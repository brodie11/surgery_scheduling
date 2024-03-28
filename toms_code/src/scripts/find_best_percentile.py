#imports
import os

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
    
    return engine,surgeries,surgical_sessions, specialties

def generate_schedule_that_minimises_transfers_and_undertime(start_date, end_date, turn_around = 15, specialty_id = 4,facility = 'A',time_lim = 300):
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
        

    return min_under_prob_lex

def simulate_stochastic_durations(schedSurgery_for_percentile):
    return 0,0,0,0

#set up pandas dataframe to store everything
best_percentile_df = pd.DataFrame(columns=['Percentile Value', 'Number of Surgeries that ran overtime', 'Number of surgeries completed', 'Surgery Utilisation', 'Total Mins Overtime'])

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

#pick start and end periods for simulation
period_start_year = 2015
period_start_month = 3
period_end_year = 2016
period_end_month = 12
# Create a list of pd.Timestamp objects for the first day of each month
month_starts = [pd.Timestamp(year=year, month=month, day=1) 
                   for year in range(period_start_year, period_end_year + 1) 
                   for month in range(period_start_month if year == period_start_year else 1, 
                                       period_end_month + 1 if year == period_end_year else 13)]
month_starts = [pd.Timestamp(year=2016, month=1, day=1)]

print(month_starts)

#set up specialty and facility
specialty = 4
facility = 'A'

# For each Month:
for i,percentile_column_name in enumerate(percentile_column_names): #for each percentile
    percentile_value = percentile_values[i]
    for month_start in month_starts: #and each month
        #Find the solution that has the fewest transfers while still minimising the undertime
        schedSurgery_for_percentile = generate_schedule_that_minimises_transfers_and_undertime(start_date=month_start,end_date=month_start + pd.DateOffset(months=1),turn_around = 15, specialty_id = specialty, facility = facility, time_lim = 300)
        schedules.append((percentile_column_name,month_start, schedSurgery_for_percentile))
        total_mins_overtime_avg,num_overtime_avg, num_surgeries_completed_avg, total_surgery_utilisation_avg = (0,0,0,0)
        for i in range(100):
            #simulate 100 runs of sched_surgery_for_percentile
            total_mins_overtime,num_overtime, num_surgeries_completed, total_surgery_utilisation = simulate_stochastic_durations(schedSurgery_for_percentile)
            #take average values
            total_mins_overtime_avg += total_mins_overtime / 100
            num_overtime_avg += num_overtime / 100
            num_surgeries_completed_avg += num_surgeries_completed / 100
            total_surgery_utilisation_avg += total_surgery_utilisation / 100
        # append data to df
        new_row = [percentile_column_name, num_overtime_avg, num_surgeries_completed_avg, total_surgery_utilisation_avg, total_mins_overtime_avg]
        best_percentile_df = best_percentile_df.append(new_row, ignore_index=True)
        best_percentile_df.loc[len(best_percentile_df.index)] = new_row
    #...
        
# Count how many surgeries are completed without running overtime (c) and how many run overtime (o)
# Average c and o across each month and plot against percentile values

#TODO evenutally run for different specialties and surgeries

#test
print(best_percentile_df.head())
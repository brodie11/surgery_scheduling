#imports
import pandas as pd

def generate_schedule_that_minimises_transfers_and_undertime(surgeries, schedules, turn_around = 15, specialty_id = 4, facility = 'A',start_date = pd.Timestamp(year=2016, month=1, day=1), end_date = pd.Timestamp(year=2016, month=3, day=1)):
    #inputs: surgeries,schedules -- pandas dataframes; (everything else slef-explanatory)
    #outputs: sschedProb


# Pick a few different percentile values to use as mean surgery duration eg. (45,50,55,60,65)
percentile_values = [45,50,55,60,65]
# Calculate percentile value based on distribution to use instead of mean when scheduling
# For each percentile value:
percentile_column_names = ['duration_45th_percentile', 'duration_50th_percentile', 'duration_55th_percentile', 'duration_60th_percentile', 'duration_65th_percentile']
# Use tom’s code to generate a schedule for each month

#TODO figure out which facility is best to use
#TODO figure out the valid date range for that facility eg. March 2014 - Feb 2016

schedules = [] #array of tuples (percentile_column_name, schedSurgery object)
for percentile_column_name in percentile_column_names:

    #...
    #Find the solution that has the fewest transfers while still minimising the undertime
    schedSurgery_for_percentile = generate_schedule_that_minimises_transfers_and_undertime()
    schedules.append((percentile_column_name, schedSurgery_for_percentile))
    #...

month_starts = []
# For each Month:
for month_start in month_starts:
    # Simulate surgery durations using distribution 100 times
    for i in range(100):
        
# Count how many surgeries are completed without running overtime (c) and how many run overtime (o)
# Average c and o across each month and plot against percentile values


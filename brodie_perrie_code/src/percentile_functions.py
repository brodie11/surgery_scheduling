from scipy.stats import lognorm
import numpy as np

def lognormal_to_normal(y_mean, y_var):
    # Convert mean and variance of lognormal distribution to mean and standard deviation of normal distribution
    X_mean = np.log(y_mean / ((1 + y_var/y_mean**2)**0.5))
    X_var = np.log(1 + y_var/y_mean**2)

    return X_mean, X_var

def replace_ev_with_percentile(sched_surs, percentile):
    """
    replaces the expected value of sched_surs object used to represent surgeries in scheduling with 
    percentile value specified

    input: array of sched_surs, percentile value eg. 60
    output: array of equal length with ev in sched_surs replaced with percentile value
    """

    new_sched_surs = []
    
    i = 0
    for sched_sur in sched_surs:

        #get ev and variance
        ed = sched_sur.ed
        dv = sched_sur.dv
        # Convert mean and variance of lognormal distribution to mean and standard deviation of normal distribution
        x_mean, x_var = lognormal_to_normal(ed, dv)
        # Calculate percentile value of normal distribution
        percentile_value = lognorm.ppf(percentile / 100, s=np.sqrt(x_var), scale=np.exp(x_mean))
        # verifying mean calculation
        # percentile_value = np.exp(x_mean+0.5*(x_var)) 

        sched_sur.actual_mean = ed
        sched_sur.ed = percentile_value

        new_sched_surs.append(sched_sur)

    return new_sched_surs

def simulate_stochastic_durations(schedDict:dict, start_date, end_date, complete_surg_list, percentile_value,turn_around=15, specialty_id = 4, facility = 'A', time_lim = 300, allowed_overtime=0):
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

    #initialise return values
    num_surgeries_completed, average_surgery_utilisation, total_mins_overtime, total_surgery_time, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled = 0,0,0,0,0,0,0
    average_session_utilisation_array = []
    #get all sessions and surgeries
    # sched_surs, sched_sess = get_all_sessions_and_surgeries(start_date, end_date, percentile_value, specialty_id, facility, time_lim)
    sched_surs = []
    sched_sess = []

    #simulation
    simulated_durations = {}
    for surg_id in complete_surg_list:
        # create array of simulated times
        surgery = [sur for sur in sched_surs if sur.n == surg_id][0]
        actual_mean = surgery.actual_mean
        actual_variance = surgery.dv
        # Calculate the mean (mu) and standard deviation (sigma) of the corresponding normal distribution
        mu = np.log(actual_mean / np.sqrt(1 + ((actual_variance/actual_mean**2))))
        sigma = np.sqrt(np.log(1 + (actual_variance / actual_mean**2)))
        simulated_durations[surg_id] = np.random.lognormal(mean=mu, sigma=sigma, size=1)[0]

    #for each session in dictionary
    for session_id, surgery_array in schedDict.items():
        if session_id == -1:
            continue

        sess_matches = [session for session in sched_sess if session.n == session_id]
        sess = sess_matches[0]
        session_duration = sess.sd
        combined_surgery_duration = 0
        # ran_overtime = False

        #get surgeries and order them from biggest to smallest
        surgeries = []

        for surgery_id in surgery_array:
            #find surgery object
            try:
                sur = [sur for sur in sched_surs if sur.n == surgery_id][0]
            except Exception as e:
                print("An error occurred:", e)
                return -1, -1, -1, -1, -1, -1
            
            surgeries.append(sur)

        #sort surgeries from smallest to biggest for consistency in cancellations
        surgeries = sorted(surgeries, key=lambda sur: sur.ed, reverse=False)
        
        for sur in surgeries:
            simulated_duration = simulated_durations[sur.n]

            if combined_surgery_duration + actual_mean + turn_around < session_duration + allowed_overtime:
                #if not first surgery, add turn_around_time
                if surgery_id != surgery_array[0]:
                    combined_surgery_duration += turn_around
                #perform surgery
                combined_surgery_duration += simulated_duration
                num_surgeries_completed += 1
            else:
                #if surgery will probably take more than allowed overtime then increment cancellation metrics accordingly and stop surgeries for day
                cancelled_surgery_index = surgeries.index(sur)
                num_surgeries_cancelled += (len(surgery_array[cancelled_surgery_index:]))
                num_sessions_with_cancelled_surgeries += 1
                break
       
        #if ran overtime then record overtime metrics accordingly
        if combined_surgery_duration > session_duration:
            total_mins_overtime += combined_surgery_duration - session_duration
            num_sessions_that_run_overtime += 1
        #caclulate utilisation - make sure it's not greater than 1
        calculated_utilisation = combined_surgery_duration / session_duration
        if calculated_utilisation > 1:
            calculated_utilisation = 1
        average_session_utilisation_array.append(calculated_utilisation)
        total_surgery_time += combined_surgery_duration

    average_session_utilisation = sum(average_session_utilisation_array)/len(average_session_utilisation_array)

    #return metrics
    return num_surgeries_completed, average_session_utilisation, total_mins_overtime, total_surgery_time, num_sessions_that_run_overtime, num_sessions_with_cancelled_surgeries, num_surgeries_cancelled

def this_weeks_schedule(week, sess_sur_dict, start_date, specialty_id = 4, facility = 'A'):
    """
    Takes the schedule, and returns the sessions and surgeries for the current week. 
    """

    return
from scipy.stats import lognorm
import numpy as np
from helper_funcs import is_surgery_inconvenient

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
    for sched_sur in sched_surs:
        # check if percentile already found
        if sched_sur.actual_mean == sched_sur.ed:
            #get ev and variance
            ed = sched_sur.ed
            dv = sched_sur.dv
            # Convert mean and variance of lognormal distribution to mean and standard deviation of normal distribution
            x_mean, x_var = lognormal_to_normal(ed, dv)
            # Calculate percentile value of normal distribution
            percentile_value = lognorm.ppf(percentile / 100, s=np.sqrt(x_var), scale=np.exp(x_mean))

            sched_sur.actual_mean = ed
            sched_sur.ed = percentile_value

            new_sched_surs.append(sched_sur)
        else:
            new_sched_surs.append(sched_sur)
            continue



    return new_sched_surs

def simulate_durations(weeks_sessions, weeks_surgeries, sess_surg_dict):
    """
    does one simulation run of surgery durations 
    based on their lognormal distribution. 

    output:
    realisation of durations
    
    """

    # simulation
    simulated_durations = {}
    for session in weeks_sessions:
        # get list of surgery objects in session
        session_id = session.n
        session_surgeries_id = sess_surg_dict[session_id]
        session_surgeries = [surgery for surgery in weeks_surgeries if surgery.n in session_surgeries_id]
        # loop through each surgery in session
        for surgery in session_surgeries:
            actual_mean = surgery.actual_mean
            actual_variance = surgery.dv
            # Calculate the mean (mu) and standard deviation (sigma) of the corresponding normal distribution
            mu = np.log(actual_mean / np.sqrt(1 + ((actual_variance/actual_mean**2))))
            sigma = np.sqrt(np.log(1 + (actual_variance / actual_mean**2)))
            simulated_durations[surgery.n] = np.random.lognormal(mean=mu, sigma=sigma, size=1)[0]

    return simulated_durations

def simulate_durations_2(surgeries):
    """
    does one simulation run of surgery durations 
    based on their lognormal distribution. 
    This version takes the datadrame of all surgeries rather than a list of objects and gets a realisation for all of them. 

    output:
    realisation of durations
    
    """

    # simulation
    simulated_durations = {}
    # loop through each surgery
    for index, surgery in surgeries.iterrows():
        actual_mean = surgery['predicted_duration']
        actual_variance = surgery['predicted_variance']
        # Calculate the mean (mu) and standard deviation (sigma) of the corresponding normal distribution
        mu = np.log(actual_mean / np.sqrt(1 + ((actual_variance/actual_mean**2))))
        sigma = np.sqrt(np.log(1 + (actual_variance / actual_mean**2)))
        simulated_durations[index] = np.random.lognormal(mean=mu, sigma=sigma, size=1)[0]

    return simulated_durations


def execute_schedule(simulated_durations, sess_surg_dict, weeks_sessions, waitlist, turn_around, allowed_overtime, sim_start_date):
    """
    Takes the realisation of simulated surgeries and executes the schedule. 

    Note: We assume a surgery is allowed to go ahead so long
    as its expected time won't put the session overtime by 
    more than specified overtime. Otherwise, the surgery is cancelled

    Returns the utilisation, overtime, number of cancellations, time spent operating for each session and a list completed surgeries ids.
    """
    # initialize return values
    utilisation_array = []
    overtime_array = []
    number_cancelled_over_array = []
    number_cancelled_pref_array = []
    time_operating_array = []
    completed_surgeries = []
    cancelled_surgeries = []
    number_overtime_sessions = 0

    for session in weeks_sessions:
        # get list of surgery objects in session
        session_id = session.n
        session_surgeries_id = sess_surg_dict[session_id]
        session_surgeries = [surgery for surgery in waitlist if surgery.n in session_surgeries_id]

        # sort surgeries from smallest to biggest for consistency in cancellations
        session_surgeries = sorted(session_surgeries, key=lambda sur: sur.ed, reverse=True)

        # initialise session
        time_elapsed = 0
        time_spent_operating = 0
        number_cancelled_over = 0
        number_cancelled_pref = 0
        scheduled_finish_time = 0

        # loop through each surgery in session
        for surgery in session_surgeries:
            scheduled_finish_time += surgery.ed
            # check if inconvenient
            inconvenient = is_surgery_inconvenient(session.sdt, sim_start_date, surgery) 
            if inconvenient:
                # cancel surgery
                number_cancelled_pref += 1
                # can't start the next surgery until when it was scheduled
                time_elapsed = max(time_elapsed, scheduled_finish_time)
            else: 
                duration = simulated_durations[surgery.n]
                 # check if enough time left
                if time_elapsed + surgery.ed + turn_around < session.sd + allowed_overtime:
                    # if not first surgery, add turn_around_time
                    if surgery.n != session_surgeries[0].n:
                        time_elapsed += turn_around
                        time_spent_operating += turn_around
                    # perform surgery
                    time_elapsed += duration
                    time_spent_operating += duration
                    completed_surgeries.append(surgery.n)
                else:
                    # if surgery will probably take more than allowed overtime then increment cancellation metrics accordingly
                    number_cancelled_over += 1
                    cancelled_surgeries.append(surgery.n)
                    # can't start the next surgery until when it was scheduled
                    time_elapsed = max(time_elapsed, scheduled_finish_time)

        # calculate session metrics
        utilisation = time_spent_operating / session.sd
        # only allow utilisation to go up to 1
        if utilisation > 1:
            utilisation = 1
        utilisation_array.append(utilisation)
        # calculate overtime
        overtime = max(time_elapsed - session.sd, 0)
        overtime_array.append(overtime)
        number_cancelled_over_array.append(number_cancelled_over)
        number_cancelled_pref_array.append(number_cancelled_pref)  
        time_operating_array.append(time_spent_operating)

        # increment numner of overtime sessions
        if overtime > 0:
            number_overtime_sessions += 1
        

    return utilisation_array, overtime_array, number_cancelled_over_array, number_cancelled_pref_array, time_operating_array, completed_surgeries, cancelled_surgeries, number_overtime_sessions
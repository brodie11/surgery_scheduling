#MAIN

#choose specialty, faclility, turn_around, etc.

#choose start date and end date 
#TODO (I reckon 6 months of simulation with a 6 month horizon so there's still room to schedule 6 months ahead on last day of end_date)

#prepareData(start_date, end_date, horizon)

#loop through each week in weeks:


    #move new sessions from sessions_to_arrive to sessions
    #move new surgeries from new_arrivals to waitlist #TODO discuss maybe adding in overtime cancelled surgeries later?
    #create_schedule(wait_list, surgeries, perfect_information)
    #create_schedule(wait_list, surgeries, imperfect_information)
    #move first 2 weeks of schedule to scheduled if first week, otherwise move first 1 week to scheduled
    #remove anything scheduled from waitlist

#compare the two schedules



#PREPARE DATA(start_date, end_date, horizon)

#select every surgery who entered the system before start date but left after and put them in waitlist
#store these in surgery objects
#OR
#could start from scratch but only simulate once steady state is reached #TODO decide with Perrie

#select every surgery who entered the system after start date and before (end date + horizon) and put them
#in the to_arrive list
#store these in surgery objects

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
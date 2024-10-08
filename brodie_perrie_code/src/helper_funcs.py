import sys

from copy import deepcopy
from gurobipy import Model, GRB, quicksum
from operator import attrgetter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import math
from datetime import timedelta
# from classes import *
# from .solution_classes import (get_sessions, get_surgeries,
#   get_solution_assignments)
from scheduler_utils import (read_database)
from classes import (schedSession, schedSurgery) #TODO make sure this down the bottom

# def create_schedule_surs(surgeries):
#   surs = []

#   for part_sur in surgeries.itertuples():
#     surs.append(schedSurgery(part_sur.Index, part_sur.predicted_duration,
#       part_sur.predicted_variance, part_sur.arrival_datetime,
#       part_sur.due_date_datetime))

#   return surs

# def create_schedule_sess(surgical_sessions, simulation_start_date):
#   sess = []

#   for part_ses in surgical_sessions.itertuples():

#     #TODO make it so sdt is an integer
  
#     sess.append(schedSession(part_ses.Index, part_ses.start_time,
#       part_ses.duration, part_ses.theatre_number))

#   return sess

# def prepare_data(simulation_start_date, simulation_end_date, specialty_id, facility, horizon):

#   this_path = os.path.abspath(os.path.dirname(__file__))
#   DATABASE_DIR = os.path.abspath(os.path.join(this_path, os.pardir, 'data'))
#   DATA_FILE = os.path.join(DATABASE_DIR, 'surgery_data.db')

#   engine = create_engine('sqlite:///' + DATA_FILE)
#   Session = sessionmaker(bind=engine)
#   # Read in data from the database.
#   with Session() as session:

#       surgeries, surgical_sessions, specialties = read_database(session,
#         simulation_start_date, simulation_end_date)

#       valid_prediction = ~np.isnan(surgeries['predicted_duration'])
#       surgeries = surgeries.loc[valid_prediction]
  
#   # Filter surgeries and sessions to the specialty and facility of interest.
#   surgeries = surgeries.loc[(surgeries['specialty_id'] == specialty_id) &
#     (surgeries['facility'] == facility)]
#   surgical_sessions = surgical_sessions.loc[(surgical_sessions['specialty_id'] == specialty_id) &
#     (surgical_sessions['facility'] == facility)]
  
#   sched_surs = create_schedule_surs(surgeries, session)
#   sched_sess = create_schedule_sess(surgical_sessions, session)
  
#   # surgeries.drop(columns=['anaesthesia_type', 'asa_rating', 'primary_procedure_id'], inplace=True)
#   # print(f"surgeries.columns.tolist() {surgeries.columns.tolist()}")
#   # print(f"surgical_sessions.columns.tolist() {surgical_sessions.columns.tolist()}")

#   return surgeries, surgical_sessions, specialties

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import pandas as pd

# def plot_cost(cost_dict):
#     # Convert the 2D dictionary to a pandas DataFrame
#     cost_df = pd.DataFrame(cost_dict).T  # Transpose to get sessions as rows and operations as columns
    
#     # Create a heatmap using seaborn
#     plt.figure(figsize=(10, 8))
#     sns.heatmap(cost_df, annot=True, fmt=".2f", cmap="RdYlGn_r", linewidths=0.5, linecolor='black')
    
#     # Add labels and title
#     plt.xlabel('Operations')
#     plt.ylabel('Sessions')
#     plt.title('Cost Heatmap')
    
#     # Show the plot
#     plt.show()

#get priority and amount of time patient knew about session for before being locked in
def get_priority_and_warning_time_for_all_surgeries_df(all_swapped_surgery_ids, disruption_count_df , actual_schedule, perfect_info=False, iter=1):

    priority_and_warning_time_for_all_surgeries_df = pd.DataFrame(columns=['session_id', 'count', 'priority', 'warning time', 'time in system'], data={})

    all_surgeries = actual_schedule.get_all_surgeries()
    for surgery in all_surgeries:
          filtered_df = disruption_count_df[disruption_count_df['surgery_id'] == surgery.n]
          filtered_df = filtered_df[filtered_df['iter'] == iter]
          if len(filtered_df) == 0:
            count = 0
          else:
            count = filtered_df.iloc[0]['disruption count']
          priority = surgery.priority
          weeks_since_last_disruption = 0
          arrival_week = 0 if surgery.ad <= 0 else surgery.ad//7
          departure_week = 0 if surgery.ad <= 0 else surgery.ld//7
          relevent_swapped_surgery_ids = all_swapped_surgery_ids[arrival_week:departure_week]                                
          for weeks_cancellations in reversed(relevent_swapped_surgery_ids):
              if surgery.n not in weeks_cancellations:
                  weeks_since_last_disruption += 1
              else:
                  break
          time_in_system = None
          if departure_week == arrival_week:
             percent_spent_knowing = 1
             time_in_system = 1
          else:
            time_in_system = departure_week-arrival_week
            percent_spent_knowing = weeks_since_last_disruption/(time_in_system)
          priority_and_warning_time_for_all_surgeries_df.loc[len(priority_and_warning_time_for_all_surgeries_df)] = [surgery.n, count, priority, percent_spent_knowing, time_in_system]

    return priority_and_warning_time_for_all_surgeries_df

class BetterScheduleObj():

#stores a dict of session id: [list of surgery objects] alongside a bunch of functions to make it easier to retrieve things

  def __init__(self):
      self.sessions = []
      self.sessionIds = []
      self.surgeries = []
      self.surgeryIds = []
      self.dict = {}
    
  def get_dict(self):
     return self.dict
  def get_sessions(self):
     return self.sessions
  def get_sessionIds(self):
     return self.sessionIds
  def get_surgeries(self, sessionID):
     return self.dict[sessionID]
  
  def get_all_surgeries(self):
     all_surgeries = []
     for surgeries in self.dict.values():
        all_surgeries = all_surgeries + surgeries
     return all_surgeries
  
  def fill_better_schedule(self, sess_sur_dict, sessionObjs, surgery_objs):
     for session_id, surgery_IDs in sess_sur_dict.items():
        self.sessionIds.append(session_id)
        self.sessions = self.sessions + [sess for sess in sessionObjs if sess.n == session_id]
        #find corresponding object based on surgeryIDs in surgery_Objs and add to dict as a list
        self.dict[session_id] = list(filter(lambda x: x.n in surgery_IDs, surgery_objs))
        
  def fill_session(self, session, surgery_objs):
     self.dict[session.n] = surgery_objs
     self.sessions.append(session)
     
  
def get_disruption_count_cv(all_swapped_surgery_ids):

        #COUNT DISRUPTIONS (make df)
        #flatten
        flattened_all_disruptions = sum(all_swapped_surgery_ids, [])
        print(len(flattened_all_disruptions))
        #list of dictionaries
        list_of_dicts_for_df = []
        #get unique surgery ids
        unique_surgeries = list(set(flattened_all_disruptions))
        #loop through
        for unique_surgery in unique_surgeries:
            dict = {}
            count = flattened_all_disruptions.count(unique_surgery)
            dict['surgery_id'] = unique_surgery
            dict['disruption count'] = count
            list_of_dicts_for_df.append(dict)
        disruption_count = pd.DataFrame(list_of_dicts_for_df)
        return disruption_count

def get_operations_which_changed(sess_sur_dict1, sess_sur_dict2, new_surgeries, recently_cancelled_surgeries):

  #create list of all swapped surgeries between weeks
  list_of_swapped_surgey_ids = []
  #loop through sessions
  for session2_id, surgeries2_array in sess_sur_dict2.items():

      #loop through surgeries
      for surgery2 in surgeries2_array:

          #if surgery is new arrival then can't have been disrupted so ignore
          if len(list(filter(lambda x: x.n == surgery2, new_surgeries))) > 0:
              continue
          #don't count surgeries which were booked then cancelled as disruptions
          if surgery2 in recently_cancelled_surgeries:
              continue
          #if session new then any non-new surgeries must have been swapped so add to list
          if session2_id not in sess_sur_dict1:
              list_of_swapped_surgey_ids.append(surgery2)
          #if surgery in different session to what it was then must have been swapped so add to list
          elif surgery2 not in sess_sur_dict1[session2_id]:
              list_of_swapped_surgey_ids.append(surgery2)

  return list_of_swapped_surgey_ids

def get_plenty_of_sess(all_sess, waitlist):
  duration_of_all_surgeries = sum([surgery.ed for surgery in waitlist])
  avg_duration_of_all_sessions = sum([session.sdt for session in all_sess]) / len(all_sess)
  number_sessions_needed = round(int(duration_of_all_surgeries//avg_duration_of_all_sessions)*1.5) #plus 20% for safety
  return all_sess[0:number_sessions_needed]

def print_detailed_ses_sur_dict(sess_sur_dict, waitlist, plenty_of_sess, turn_around):
    
    print(f"sess ssur dict!!!")
    print(sess_sur_dict)
   #for each session in dictionary
    for session_id, surgery_array in sess_sur_dict.items():
        print(f"session id {session_id}") 
        #get info about this session such as duration
        sess_matches = [session for session in plenty_of_sess if session.n == session_id]
        sess = sess_matches[0]
        session_duration = sess.sd
        combined_surgery_duration = 0
        #get surgeries and order them from biggest to smallest
        surgeries = []
        print(f"session duration {session_duration}")
        print(f"session sdt {sess.sdt}")
        #make sure session has surgeries assigned to it
        if len(surgery_array) == 0:
           continue
        for surgery_id in surgery_array:
            sur = [sur for sur in waitlist if sur.n == surgery_id][0]
            surgeries.append(sur)

        for surg in surgeries:
           print(f"     Surgery id: {surg.n}, surgery ad: {surg.ad}, surgery dd: {surg.dd}, surgery duration: {surg.ed}")
           combined_surgery_duration += surg.ed + turn_around

        print(f"  combined surgery durations for session {session_id} is {combined_surgery_duration - turn_around}")
         
def compute_metrics(waitlist, scheduled_sessions, week, completed_surgeries, sess_sur_dict):

    total_tardiness = 0
    number_patients_tardy = 0
    total_waittime_p33 = 0
    total_waittime_p66 = 0
    total_waittime_p100 = 0
    num_surs_scheduled = 0

    #For each scheduled session
    for session in scheduled_sessions:
        #get associated surgery ids
        # scheduled_surgery_ids = ses_sur_dict[session.n]

        #and surgery objects
        scheduled_surgeries = [surgery for surgery in waitlist if surgery.n in sess_sur_dict[session.n]]
        num_surs_scheduled += len(scheduled_surgeries)
        
        for surgery in scheduled_surgeries:
          tardiness = max(0, session.sdt - surgery.dd)
          total_tardiness += tardiness
          if tardiness > 0:
              number_patients_tardy += 1

          wait_time = session.sdt - surgery.ad
          if surgery.priority <= 0.33:
              total_waittime_p33 += wait_time
          elif surgery.priority <= 0.66:
              total_waittime_p66 += wait_time
          else:
              total_waittime_p100 += wait_time
          
    # Calculate average wait times
    if num_surs_scheduled > 0:
        average_waittime_p33 = total_waittime_p33 / num_surs_scheduled
        average_waittime_p66 = total_waittime_p66 / num_surs_scheduled
        average_waittime_p100 = total_waittime_p100 / num_surs_scheduled
    else:
        average_waittime_p33 = average_waittime_p66 = average_waittime_p100 = 0
    
    if average_waittime_p100 + 3.1 < 0.1:
        print("xyxyxyx")
        print(week)
        print(scheduled_surgeries)
        print(scheduled_sessions)

        for scheduled_surgery in scheduled_surgeries:
          print(f"surgery {scheduled_surgery.n} has ad of {scheduled_surgery.ad}")

        sys.exit(0)
    
    num_sessions = len(scheduled_sessions)
    # num_cancelled = len(cancelled_surgeries)

    return num_sessions, total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100

# Class that builds and solves the MIP models for scheduling.
class inconvenienceProb:
  # Copy and sort the surgeries and sessions, build the model, then solve the
  # model.
  def __init__(self, sim_start_date, iter, surgeries, sessions, turn_around, obj_type, is_disruption_considered, 
               max_disruption_parameter, max_disruption_shift, time_lim=300, optimality_gap=1, init_assign=None, 
               perfect_information=False, new_sessions=[], seed = 10):

    self.seed = seed
    self.iter = iter

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)
    self.sess_ids = list(map(lambda x: x.n, self.sess))
    self.new_sess=deepcopy(new_sessions)

    self.sim_start_date = sim_start_date

    print(f"self.sess {self.sess}")

    #add in dummy session to make problem feasible:
    # last_sess = max(sessions, key=attrgetter('sdt'))
    # print(f"last_sess.sdt {last_sess.sdt}")
    # extra_sess_start = last_sess.sdt + 28
    # self.sess.append(schedSession(-1, extra_sess_start, 999999, 0))

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.priority_inds = [self.ops.index(o) for o in self.priority_ops]
    self.ordered_inds = [self.sess.index(s) for s in self.ordered_sess]

    self.actual_sess = self.ordered_sess #used to exclude -1 session. Doesn't anymore

    self.init_assign = init_assign

    self.pi = perfect_information

    self.ta = turn_around
    self.time_lim = time_lim
    self.optimality_gap = optimality_gap

    self.obj_type = obj_type

    self.idc = is_disruption_considered
    self.mdp = max_disruption_parameter
    self.mds = max_disruption_shift

    self.prob = 0
    self.obj = 0

    self.build_model()
    self.solve_model()

  def build_model(self):

    # Initialise the Gurobi model.
    self.prob = Model('Surgery Scheduling Problem')

    self.prob.setParam("Seed", self.seed)

    # Add the x variables.
    self.x_inds = [(o.n, s.n) for o in self.ops
      for s in self.sess]
    self.x = self.prob.addVars(self.x_inds, vtype=GRB.BINARY,
      name='AssignSurgeries')
    
    #get current day/week
    earliest_day = min([s.sdt for s in self.sess])

    # If there is a previous solution to use as a starting point, set the
    # Start attribute of the x variables.
    if self.init_assign is not None:
      for s in self.sess:
        for o in self.ops:
          if s.n in self.init_assign.keys(): #check session from previous solution hasn't been removed
            if o.n in self.init_assign[s.n]:
              self.x[o.n, s.n].Start = 1
              if self.idc == True:
                #ban shifts by more than max_disruption_shift
                #get list of all sessions which would represent too much of a shift in schedule if this operation were reassigned
                banned_session_ids = [banned_session.n for banned_session in self.sess if banned_session.sdt < s.sdt - self.mds or banned_session.sdt > s.sdt + self.mds]
                for banned_session_id in banned_session_ids:
                  self.prob.addConstr(self.x[o.n, banned_session_id] == 0)
          else:
             continue
    
    #limit the number of deviations from previous solution to self.mdp or less #TODO test this!!
    if self.idc == True and self.init_assign is not None:
        disruption = quicksum((1-self.x[o, s]) for s in self.init_assign.keys() for o in self.init_assign[s] if s in self.sess_ids)
        self.prob.addConstr(disruption <= self.mdp, name="max disruption")
    #TODO find way to make sure that it's counted as a swap if an old surgery assigned to a new session also

    if self.obj_type != "t&p matrix":
      # Add the tardiness variables
      self.tardiness_inds = [(o.n) for o in self.ops]
      self.tardiness = self.prob.addVars(self.tardiness_inds, vtype=GRB.CONTINUOUS, lb=0,
        name='Tardiness')
    
    #try calculating cost without tardiness variables
    self.cost = {} #define empty (for now) 2d dictionary
    for o in self.ops:
      self.cost[o.n] = {}
      for s in self.sess:
          tardiness = max([s.sdt - o.dd, 0])
          self.cost[o.n][s.n] = 365*tardiness + (o.priority*s.sdt) #TODO make so 365 is replaced with days_in_simulation_period    
    # plot_cost(self.cost)

    if self.obj_type == "t":
      #define objective function for tardiness #TODO uncomment and combine with above
      self.prob.setObjective(quicksum( self.tardiness[o.n]*self.x[o.n, s.n] #- (o.priority/s.sdt) * self.x[o.n, s.n]
          for o in self.ops
          for s in self.sess
          ))
    elif self.obj_type == "t&p":
      self.prob.setObjective(quicksum( self.tardiness[o.n]*self.x[o.n, s.n] - (o.priority/s.sdt) * self.x[o.n, s.n]
          for o in self.ops
          for s in self.sess
          ))
    elif self.obj_type == "t&p matrix":
      self.prob.setObjective(quicksum(self.cost[o.n][s.n]*self.x[o.n, s.n]
          for o in self.ops
          for s in self.sess
          ))

    # Each surgery is performed once.
    for i, o in enumerate(self.ops):
      self.prob.addConstr(quicksum(self.x[o.n, s.n]
        for s in self.sess) == 1, name='Surgery_' + str(i))

    #sum of surgery durations within session is less than or equals that session's duration
    for j, s in enumerate(self.sess):
      if s.n != -1:
        # Surgery duration + turn around = session duration
        # try:
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) - self.ta <= s.rhs,
          "session_duration_%s" % j)
        # except:
        #    print("yo")

    if self.obj_type != "t&p matrix":
      #each surgery's tardiness is greater than their scheduled time - due date (and 0)
      for o in self.ops:
          self.prob.addConstr(self.tardiness[o.n] >= quicksum( self.x[o.n, s.n]*int(s.sdt - o.dd) for s in self.sess))

    #add inconvenient time constraints if perfect information
    #TODO
    if self.pi == True:
      for o in self.ops:
        day_banned = o.day_banned
        weeks_banned = o.weeks_banned
        month_banned = o.month_banned
        #check if constraints needed
        if day_banned != None or weeks_banned != None or month_banned != None:
          for s in self.actual_sess:
            if is_surgery_inconvenient(s.sdt, self.sim_start_date, o):
            # session_time = s.sdt
            # day_inconvenient = session_time % 7 == day_banned
            # week_inconvenient = math.floor(session_time / 7) + 1 in weeks_banned
            # month_inconvenient = math.floor(session_time / 30.41) + 1 == month_banned
            # if day_inconvenient or week_inconvenient or month_inconvenient:
              self.prob.addConstr(self.x[o.n, s.n] == 0) 
        
  # Solves the model and prints the solution.
  def solve_model(self):
    self.prob.Params.TimeLimit = self.time_lim
    self.prob.Params.MIPGap = self.optimality_gap
    # self.prob.Params.NodeFileStart = 0.5
    self.prob.optimize()

    if self.prob.status == 3:
      self.prob.computeIIS()
      for c in self.prob.getConstrs():
        if c.IISConstr:
          print(c.ConstrName)

    self.ses_sur_dict = {s.n: [] for s in self.sess}

    for j, s in enumerate(self.sess):
      for i, o in enumerate(self.ops):
        try:
          if self.x[o.n, s.n].X > 0.99:
            self.ses_sur_dict[s.n].append(o.n)
        except AttributeError:
           print(f"self.x[o.n,s.n] {self.x[o.n,s.n]}")
           print(f"self.iter{self.iter}")
          # print('Scheduled:', i, o.n, int(o.ed), o.priority)
    # print(self.prob.objVal)

    # if self.idc == True and self.init_assign is not None: #TODO Brodie was using for debugging. Can delete if not already deleted by week 7
    #   # Get the constraint by its name
    #   constraint = self.prob.getConstrByName("max disruption")

    #   # Extract the linear expression from the constraint
    #   # Get the LHS expression of the constraint
    #   lhs_expression = self.prob.getRow(constraint)

    #   # Iterate over the terms in the LHS expression and print the variables and their values
    #   print("Variables in the LHS of 'max disruption' constraint:")
    #   for i in range(lhs_expression.size()):
    #       var = lhs_expression.getVar(i)
    #       if var.X == 0:  
    #         print(f"Variable {var.VarName}: Value {var.X}")

def is_surgery_inconvenient(session_days_since_start, sim_start_date, surgery):
    # Calculate the actual date of the session
    session_date = sim_start_date + timedelta(days=session_days_since_start)
    
    # Extract the month, week number, and day of the week from the session date
    month = session_date.month
    week = session_date.isocalendar()[1]
    day_of_week = session_date.isoweekday()  # 1=Monday, ..., 7=Sunday

    week_inconvenient = False 
    if surgery.weeks_banned:
      weeks_inconvenient = [item for item in surgery.weeks_banned if item == week]
      if weeks_inconvenient:
        week_inconvenient = True
    
    # Check for inconvenient times
    is_inconvenient = (
        (surgery.month_banned == month) or
        (week_inconvenient) or # need to check actual values but need to prevent index error. 
        (surgery.day_banned == day_of_week)
    )
    
    return is_inconvenient

# def create_schedule(sessions, surgeries, perfect_information = True):
    #TODO maybe don't consider disruption parameter for now? if so only need to generate for either 2 weeks or one week
    #TODO in that vain - could use a warm start?

    #obj function: #TODO agree on this with 

    

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


#NEXT STEPS
# simulate for surgeries that run too long
# experiment with different objective functions/normalisation parameters

# disruption parameter
# add in inconvenient times as well as weeks or days
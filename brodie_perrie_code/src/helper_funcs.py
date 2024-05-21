import sys

from copy import deepcopy
import numpy as np
from gurobipy import Model, GRB, quicksum
from operator import attrgetter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import math
# from classes import *
# from .solution_classes import (get_sessions, get_surgeries,
#   get_solution_assignments)
from .scheduler_utils import (read_database)
from .classes import (schedSession, schedSurgery) #TODO make sure this down the bottom

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
         
def compute_metrics(waitlist, ids_of_surgery_scheduled, scheduled_sessions, week):
    # Scheduled surgeries from waitlist
    scheduled_surgeries = [s for s in waitlist if s.n in ids_of_surgery_scheduled]

    total_tardiness = 0
    number_patients_tardy = 0
    total_waittime_p33 = 0
    total_waittime_p66 = 0
    total_waittime_p100 = 0
    num_surs_scheduled = len(scheduled_surgeries)

    for surgery in scheduled_surgeries:
        tardiness = max(0, week - surgery.dd)
        total_tardiness += tardiness
        if tardiness > 0:
            number_patients_tardy += 1

        wait_time = week+1 - surgery.ad
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
    
    num_sessions = len(scheduled_sessions)

    return total_tardiness, number_patients_tardy, average_waittime_p33, average_waittime_p66, average_waittime_p100, num_surs_scheduled, num_sessions

# Class that builds and solves the MIP models for scheduling.
class inconvenienceProb:
  # Copy and sort the surgeries and sessions, build the model, then solve the
  # model.
  def __init__(self, surgeries, sessions, turn_around, obj_type, time_lim=300, init_assign=None, perfect_information=False):

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)

    print(f"self.sess {self.sess}")

    #add in dummy session to make problem feasible:
    last_sess = max(sessions, key=attrgetter('sdt'))
    print(f"last_sess.sdt {last_sess.sdt}")
    extra_sess_start = last_sess.sdt + 28
    self.sess.append(schedSession(-1, extra_sess_start, 999999, 0))

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.priority_inds = [self.ops.index(o) for o in self.priority_ops]
    self.ordered_inds = [self.sess.index(s) for s in self.ordered_sess]

    self.actual_sess = self.ordered_sess[:-1]

    self.init_assign = init_assign

    self.pi = perfect_information

    self.ta = turn_around
    self.time_lim = time_lim

    self.obj_type = obj_type

    self.prob = 0
    self.obj = 0

    self.build_model()
    self.solve_model()

  def build_model(self):

    # Initialise the Gurobi model.
    self.prob = Model('Surgery Scheduling Problem')

    # Add the x variables.
    self.x_inds = [(o.n, s.n) for o in self.ops
      for s in self.sess]
    self.x = self.prob.addVars(self.x_inds, vtype=GRB.BINARY,
      name='AssignSurgeries')

    # If there is a previous solution to use as a starting point, set the
    # Start attribute of the x variables.
    if self.init_assign is not None:
      for s in self.sess:
        for o in self.ops:
          if o.n in self.init_assign[s.n]:
            self.x[o.n, s.n].Start = 1

    # Add the tardiness variables
    self.tardiness_inds = [(o.n) for o in self.ops]
    self.tardiness = self.prob.addVars(self.tardiness_inds, vtype=GRB.CONTINUOUS, lb=0,
      name='Tardiness')
    
    if self.obj_type == "tardiness":
      #define objective function for tardiness #TODO uncomment and combine with above
      self.prob.setObjective(quicksum( self.tardiness[o.n]*self.x[o.n, s.n] #- (o.priority/s.sdt) * self.x[o.n, s.n]
          for o in self.ops
          for s in self.sess))
    elif self.obj_type == "tardiness and priority":
      self.prob.setObjective(quicksum( self.tardiness[o.n]*self.x[o.n, s.n] - (o.priority/s.sdt) * self.x[o.n, s.n]
          for o in self.ops
          for s in self.sess))

    # Each surgery is performed once.
    for i, o in enumerate(self.ops):
      self.prob.addConstr(quicksum(self.x[o.n, s.n]
        for s in self.sess) == 1, name='Surgery_' + str(i))

    #sum of surgery durations within session is less than or equals that session's duration
    for j, s in enumerate(self.sess):
      if s.n != -1:
        # Surgery duration + turn around = session duration
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) - self.ta <= s.rhs,
          "session_duration_%s" % j)

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
            session_time = s.sdt
            day_inconvenient = session_time % 7 == day_banned
            week_inconvenient = math.floor(session_time / 7) + 1 in weeks_banned
            month_inconvenient = math.floor(session_time / 30.41) + 1 == month_banned
            if day_inconvenient or week_inconvenient or month_inconvenient:
              self.prob.addConstr(self.x[o.n, s.n] == 0)
        
  # Solves the model and prints the solution.
  def solve_model(self):
    self.prob.Params.TimeLimit = self.time_lim
    self.prob.optimize()

    if self.prob.status == 3:
      self.prob.computeIIS()
      for c in self.prob.getConstrs():
        if c.IISConstr:
          print(c.ConstrName)

    self.ses_sur_dict = {s.n: [] for s in self.sess}

    for j, s in enumerate(self.sess):
      for i, o in enumerate(self.ops):
        if self.x[o.n, s.n].X > 0.99:
          self.ses_sur_dict[s.n].append(o.n)
          # print('Scheduled:', i, o.n, int(o.ed), o.priority)
    print(self.prob.objVal)

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
# implement warm starts from previous week's schedules
# experiment with different objective functions/normalisation parameters

# disruption parameter
# add in inconvenient times as well as weeks or days
from copy import deepcopy
import numpy as np
from numpy.random import Generator, PCG64
from gurobipy import Model, GRB, quicksum
from .solution_classes import (get_sessions, get_surgeries,
  get_solution_assignments)
import math

rng = Generator(PCG64(891011))


# Class for surgeries used while scheduling.
class schedSurgery:
    def __init__(self, name, expected_duration, duration_variance,
      arrive_date, due_date):

      self.n = int(name)
      self.ed = expected_duration
      self.dv = duration_variance
      self.ad = arrive_date
      self.dd = due_date
      self.priority = rng.uniform()
      self.actual_mean = expected_duration

      #properties to do with inc
      self.chance_of_day_week_month_preference = 0.083 #should result in CDI (cancellation due to inconvenince) rate of 2.5%
      self.day_banned = self.get_inconvenient_day()
      self.weeks_banned = self.get_inconvenient_weeks()
      self.month_banned = self.get_inconvenient_month()

    def get_inconvenient_day(self):
       #returns 1 if monday inconvenient, 2 if tuesday inconvenient,... 7 if Sunday inconvenient.
       #returns 0 if no days are inconvenient
       random_number = rng.uniform()
       if random_number <= self.chance_of_day_week_month_preference:
          return math.floor(rng.uniform()*7) + 1
       else:
          return None
       
    def get_inconvenient_weeks(self):
       #returns an array of length 4 representing the 4 weeks of the year which are inconvenient
       #if no weeks are inconvenient, returns an empty array
       random_number = rng.uniform()
       if random_number <= self.chance_of_day_week_month_preference:
            inconvenient_weeks = []
            while len(inconvenient_weeks) < 4:
                inconvenient_week = math.floor(rng.uniform()*52) + 1
                if inconvenient_week not in inconvenient_weeks:
                    inconvenient_weeks.append(inconvenient_week)
            return inconvenient_weeks
       else:
            return []
       
    def get_inconvenient_month(self):
       #returns 1 if Jan inconvenient, 2 if Feb inconvenient,... 12 if Dec inconvenient.
       #returns 0 if no months are inconvenient
       random_number = rng.uniform()
       if random_number <= self.chance_of_day_week_month_preference:
          return math.floor(rng.uniform()*12) + 1
       else:
          return None
       

    def __repr__(self):
      return '<Surgery(n={0})>'.format(self.n)


# Class for sessions used while scheduling.
class schedSession:
  def __init__(self, name, start_date_time, session_duration,
    theatre_number):

    self.n = int(name)
    self.sdt = start_date_time
    self.sd = session_duration
    self.tn = theatre_number
    self.rhs = session_duration

  def __repr__(self):
      return '<Session(n={0})>'.format(self.n)


# Class that builds and solves the MIP models for scheduling.
class schedProb:
  # Copy and sort the surgeries and sessions, build the model, then solve the
  # model.
  def __init__(self, surgeries, sessions, turn_around,
    time_lim, strict_priority, transfer_limit, init_assign=None,
    overtime_obj=None):

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.priority_inds = [self.ops.index(o) for o in self.priority_ops]
    self.ordered_inds = [self.sess.index(s) for s in self.ordered_sess]

    self.actual_sess = self.ordered_sess[:-1]

    self.ta = turn_around
    self.strict_priority = strict_priority
    self.transfer_limit = transfer_limit
    self.time_lim = time_lim
    self.overtime_obj = overtime_obj

    self.prob = 0
    self.obj = 0
    self.init_assign = init_assign

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

    # Add the undertime variables.
    self.ut_inds = [(s.n) for s in self.actual_sess]
    self.ut = self.prob.addVars(self.ut_inds, vtype=GRB.CONTINUOUS, lb=0.0,
      name='Undertime')

    # Add the transfer variables.
    self.y = self.prob.addVars(self.x_inds, vtype=GRB.BINARY,
      name='SurgeriesTransfers')

    # If overtime_obj is not set, then assume we want to minimise undertime.
    if self.overtime_obj is None:
      self.prob.setObjective(quicksum(self.ut[s.n] for s in self.actual_sess))
    # Otherwise we want to minimise the number of transfers subject a
    # constraint on the amount of undertime.
    else:
      self.prob.setObjective(quicksum(self.y[o.n, s.n] for o in self.ops
        for s in self.sess))
      self.prob.addConstr(quicksum(self.ut[s.n] for s in self.actual_sess) <= self.overtime_obj)

    # Each surgery is performed once.
    for i, o in enumerate(self.ops):
      self.prob.addConstr(quicksum(self.x[o.n, s.n]
        for s in self.sess) == 1, name='Surgery_' + str(i))

    for j, s in enumerate(self.sess):
      if s.n != -1:
        # Surgery duration + turn around + undertime = session duration
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) + self.ut[s.n] - self.ta == s.rhs,
          "session_duration_%s" % j)
      else:
        # Extra session
        # Surgery duration + turn around <= session duration
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) - self.ta <= s.rhs,
          "session_duration_%s" % j)

    # If we are strictly enforcing priority, then an operaton o cannot go in an
    # earlier session than any higher priority operations (o1).
    if self.strict_priority:
      for j, s in enumerate(self.ordered_sess):
        earlier_sess = self.ordered_sess[:j + 1]
        for i, o in enumerate(self.priority_ops):
          above_ops = self.priority_ops[:i]
          for o1 in above_ops:
            self.prob.addConstr(self.x[o.n, s.n] <= quicksum(self.x[o1.n, s1.n] for s1 in earlier_sess))

    # If we have a transfer limit then we need to enforce it.
    if self.transfer_limit is not None:

      # Transfer limit of -1 means we want to calculate the transfers but not
      # actually limit them.
      if self.transfer_limit != -1:
        self.prob.addConstr(quicksum(self.y[o.n, s.n] for o in self.ops for s in self.actual_sess) <= self.transfer_limit, "total_transfers")

      for j, s in enumerate(self.actual_sess):
        earlier_sess = self.ordered_sess[:j + 1]
        for i, o in enumerate(self.priority_ops):
          below_ops = self.priority_ops[i + 1:]
          l4 = self.prob.addConstr(s.rhs * self.y[o.n, s.n] >= 1 + quicksum(self.x[o1.n, s.n] * int(o1.ed + self.ta) for o1 in below_ops) - self.ta + self.ut[s.n] - int(o.ed) - s.rhs * (quicksum(self.x[o.n, s1.n] for s1 in earlier_sess)),
            "session_operation_transfer_%s_%s" % (i, j))
  
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

    for j, s in enumerate(self.ordered_sess):
      print('------------')
      if s.n != -1:
        print(s.n, s.rhs, self.ut[s.n].X)
      else:
        print(s.n, s.rhs)
      for i, o in enumerate(self.ops):
        if self.x[o.n, s.n].X > 0.99:
          self.ses_sur_dict[s.n].append(o.n)
          print('Scheduled:', i, o.n, int(o.ed), o.priority)
        if self.y[o.n, s.n].X > 0.99:
          print('Transfer:', i, o.n, int(o.ed), o.priority)


# A class just for solving the strict priority problem, no MIP is required.
class priorityProb:
  def __init__(self, surgeries, sessions, turn_around):

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.actual_sess = self.ordered_sess[:-1]

    self.ta = turn_around

    self.sur_assigned_dict = {o.n: -1 for o in self.ops}
    self.ses_sur_dict = {s.n: [] for s in self.sess}
    self.ses_mean_dict = {s.n: 0 for s in self.sess}

    for i, s in enumerate(self.ordered_sess):
      ses_lim = 0
      for o in self.priority_ops:
        if self.sur_assigned_dict[o.n] == -1:
          if (self.ses_mean_dict[s.n] + int(o.ed + self.ta) <= s.rhs) and (ses_lim == 0):
            if len(self.ses_sur_dict[s.n]) == 0:
              self.ses_mean_dict[s.n] += int(o.ed)
            else:
              self.ses_mean_dict[s.n] += int(o.ed + self.ta)
            self.ses_sur_dict[s.n].append(o.n)
            self.sur_assigned_dict[o.n] = i
          else:
            ses_lim = 1

    self.obj = 0
    for s in self.actual_sess:
      self.obj += s.rhs - self.ses_mean_dict[s.n]


# Function to calculate if there are any justified transfers.
def check_inequities(surgeries, sessions, ses_sur_dict, turn_around, transfers):

  priority_ops = sorted(surgeries, key=lambda x: x.priority, reverse=True)
  ordered_sess = sorted(sessions, key=lambda x: x.sdt)

  sur_ses_ind = {}
  for ses in ses_sur_dict:
    for sur in ses_sur_dict[ses]:
      ses_obj = next((x for x in ordered_sess if x.n == ses), None)
      sur_ses_ind[sur] = ordered_sess.index(ses_obj)

  for i, op in enumerate(priority_ops):
    below_ops = priority_ops[i:]
    earlier_sess = ordered_sess[:sur_ses_ind[op.n]]

    for e_ses in earlier_sess:
      below_ops_in_ses = []
      for ses_op in ses_sur_dict[e_ses.n]:
        ses_op_obj = next((x for x in below_ops if x.n == ses_op), None)
        if ses_op_obj is not None:
          below_ops_in_ses.append(ses_op_obj)

      print('Test')


# Calculates the difference (in number of sessions) between two schedules.
def compare_solution_schedules(sol1, sol2, db_ses):

  sessions = get_sessions(db_ses)
  sessions = sessions.sort_values('start_datetime')
  surgeries = get_surgeries(db_ses)
  sol1_assigns = get_solution_assignments(db_ses, sol1.id)
  sol2_assigns = get_solution_assignments(db_ses, sol2.id)

  ses_diffs = []

  for i, sur in surgeries.iterrows():
    sol1_ses = sol1_assigns.loc[sol1_assigns['surgery_id'] == i, 'session_id'].values[0]
    sol1_ses_ind = sessions.index.get_loc(sol1_ses)
    sol2_ses = sol2_assigns.loc[sol2_assigns['surgery_id'] == i, 'session_id'].values[0]
    sol2_ses_ind = sessions.index.get_loc(sol2_ses)

    ses_diffs.append(sol1_ses_ind - sol2_ses_ind)

  return ses_diffs

from copy import deepcopy
from gurobipy import Model, GRB, quicksum
from operator import attrgetter
# from classes import *
# from .solution_classes import (get_sessions, get_surgeries,
#   get_solution_assignments)

# Class that builds and solves the MIP models for scheduling.
class inconvenienceProb:
  # Copy and sort the surgeries and sessions, build the model, then solve the
  # model.
  def __init__(self, surgeries, sessions, turn_around, time_lim=300, init_assign=None, perfect_information=False):

    #add in dummy session to make problem feasible:
    last_sess = max(sessions, key=attrgetter('sdt'))
    print(f"last_sess.sdt {last_sess.sdt}")
    extra_sess_start = last_sess.sdt + 28
    sessions.append(schedSession(-1, extra_sess_start, 999999, 0))

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.priority_inds = [self.ops.index(o) for o in self.priority_ops]
    self.ordered_inds = [self.sess.index(s) for s in self.ordered_sess]

    self.actual_sess = self.ordered_sess[:-1] #TODO ask Tom - assuming this removes dummy session? Where is dummy session actually created?

    self.init_assign = init_assign

    self.pi = perfect_information

    self.ta = turn_around
    self.time_lim = time_lim

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
    self.tardiness = self.prob.addVars(self.tardiness_inds, vtype=GRB.INTEGER, lb=0.0,
      name='Tardiness')


   #define objective function for high priority #TODO incorporate and normalise
    self.prob.setObjective(quicksum( (o.priority/s.sdt) * self.x[o.n, s.n]
        for o in self.ops
        for s in self.sess))

    #define objective function for tardiness #TODO check with Tom 
    S = len(self.actual_sess)
    self.prob.setObjective(quicksum( self.tardiness[o.n]*self.x[o.n, s.n] 
        for o in self.ops
        for s in self.sess))

    # Each surgery is performed once.
    for i, o in enumerate(self.ops):
      self.prob.addConstr(quicksum(self.x[o.n, s.n]
        for s in self.sess) == 1, name='Surgery_' + str(i))

    
    #sum of surgery durations within session is less than or equals that session's duration
    for j, s in enumerate(self.sess):
      if s.n != -1:
        # Surgery duration + turn around + undertime = session duration
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) - self.ta <= s.rhs,
          "session_duration_%s" % j)
      else:
        # Extra session
        # Surgery duration + turn around <= session duration
        self.prob.addConstr(quicksum(self.x[o.n, s.n] * int(o.ed + self.ta)  #
          for o in self.ops) - self.ta <= s.rhs,
          "session_duration_%s" % j)

    #each surgery's tardiness is greater than their scheduled time - expected time (and 0)
    for o in self.ops:
      if s.n != -1:
        self.prob.addConstr(self.tardiness[o.n] >= quicksum( s.sdt*self.x[o.n, s.n] - o.dd for s in self.actual_sess))
      else:
        #TODO decide penalty for not being scheduled
        self.prob.addConstr(self.tardiness[o.n] >= quicksum( s.sdt*self.x[o.n, s.n] - o.dd for s in self.actual_sess))

    #add inconvenient time constraints if perfect information
    #TODO
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

# def create_schedule(sessions, surgeries, perfect_information = True):
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
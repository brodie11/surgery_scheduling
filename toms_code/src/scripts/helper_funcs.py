from copy import deepcopy
from gurobipy import Model, GRB, quicksum
# from .solution_classes import (get_sessions, get_surgeries,
#   get_solution_assignments)

# Class that builds and solves the MIP models for scheduling.
class schedProb:
  # Copy and sort the surgeries and sessions, build the model, then solve the
  # model.
  def __init__(self, surgeries, sessions, turn_around,
    time_lim):

    self.ops = deepcopy(surgeries)
    self.sess = deepcopy(sessions)

    self.priority_ops = sorted(self.ops, key=lambda x: x.priority, reverse=True)
    self.ordered_sess = sorted(self.sess, key=lambda x: x.sdt)

    self.priority_inds = [self.ops.index(o) for o in self.priority_ops]
    self.ordered_inds = [self.sess.index(s) for s in self.ordered_sess]

    self.actual_sess = self.ordered_sess[:-1] #TODO ask Tom

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

def create_schedule(sessions, surgeries, perfect_information = True):
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

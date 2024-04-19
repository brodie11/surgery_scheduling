import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

from ..configs import DATABASE_DIR, OUTPUT_DB_DIR, DATA_FILE
from ..scheduler_utils import (
  prepare_data, create_schedule_surs, create_schedule_sess)
from ..scheduler_classes import (schedProb, priorityProb)
from ..solution_classes import (Base, get_create_solution,
  create_update_solution_assignments,
  get_solution, get_ses_sur_dict, create_update_solution_transfers)
from ..visualise import create_session_graph


if __name__ == '__main__':
  print('Testing Equity scheduling')

  print(DATABASE_DIR)

  # Set the value of the parameters.
  turn_around = 15
  specialty_id = 4
  facility = 'A'
  start_date = pd.Timestamp(year=2016, month=1, day=1)
  # end_date = pd.Timestamp(year=2016, month=1, day=25)
  end_date = pd.Timestamp(year=2016, month=3, day=1)
  time_lim = 300

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

    # Create and solve the problem where priority is strictly enforced, no-one
    # can go ahead of someone if they are lower priority that them.
    priority_prob = priorityProb(sched_surs, sched_sess, turn_around)
    pri_sol = get_create_solution(session, 1, 0, 0, priority_prob.obj)
    create_update_solution_assignments(session, pri_sol.id,
      priority_prob.ses_sur_dict)
    graph_name = 'specialty_{0}_start_{1}_end_{2}_strict_priority'.format(specialty_id,
      start_date.date(), end_date.date())
    create_session_graph(pri_sol, session, graph_name)

    # Create and solve the problem where there are no justified transfers,
    # people can go ahead of others that are higher priority than them, but
    # only if the higher priority patient can't fit in the session.
    no_transfer_prob = schedProb(sched_surs, sched_sess, turn_around, time_lim,
      0, 0, priority_prob.ses_sur_dict, None)
    no_transfer_sol = get_create_solution(session, -1,
        0, 0, no_transfer_prob.prob.obj_val)
    create_update_solution_assignments(session, no_transfer_sol.id,
      no_transfer_prob.ses_sur_dict)
    graph_name = 'specialty_{0}_start_{1}_end_{2}_transfer_0'.format(specialty_id,
      start_date.date(), end_date.date())
    create_session_graph(no_transfer_sol, session, graph_name)
    
    # Check if the lexicograhoic solution has been found already. If it has we
    # don't want to spend time finding it again.
    min_under_lex_sol = get_solution(session, -1, None, 1)

    if min_under_lex_sol is None:
      # If we don't have it we need to find the solution that has the fewest
      # transfers while still minimising the undertime. First we solve the
      # problem of just minimising undertime. Then given this minimum undertime
      # value we minimise the number of transfers subject to the minimum
      # undertime as a constraint.
      min_under_prob = schedProb(sched_surs, sched_sess, turn_around,
        time_lim, 0, None)
      util_obj = min_under_prob.prob.obj_val

      min_under_prob_lex = schedProb(sched_surs, sched_sess, turn_around,
        time_lim, 0, -1, min_under_prob.ses_sur_dict, util_obj)
      min_under_lex_sol = get_create_solution(session, -1,
        min_under_prob_lex.prob.obj_val, 1, util_obj)

      create_update_solution_assignments(session, min_under_lex_sol.id,
        min_under_prob_lex.ses_sur_dict)
      create_update_solution_transfers(session, min_under_lex_sol.id,
        min_under_prob_lex)

    else:
      min_under_lex_ssd = get_ses_sur_dict(session, min_under_lex_sol.id)
      util_obj = min_under_lex_sol.under_time

    graph_name = 'specialty_{0}_start_{1}_end_{2}_min_under'.format(specialty_id,
      start_date.date(), end_date.date())
    create_session_graph(min_under_lex_sol, session, graph_name)

    # We should never need more than the number of transfers needed here
    max_transfers = min_under_lex_sol.transfers_allowed

  print('Complete')
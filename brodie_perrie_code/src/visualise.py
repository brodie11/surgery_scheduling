import os

import numpy as np
import matplotlib.pyplot as pyp
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib import patheffects

from configs import OUTPUT_FIG_DIR
from solution_classes import (get_sessions, get_surgeries,
  get_solution_assignments, get_solution_transfers)

pyp.style.use(os.path.join(OUTPUT_FIG_DIR, 'presentation.mplstyle'))


def create_session_graph(solution, db_ses, fig_name):

  sol_assigns = get_solution_assignments(db_ses, solution.id)
  sol_transfers = None

  sessions = get_sessions(db_ses)
  sessions = sessions.sort_values('start_datetime')
  surgeries = get_surgeries(db_ses)

  fig, ax = pyp.subplots()

  cnorm = Normalize(vmin=0, vmax=1)
  smap = ScalarMappable(cnorm, 'viridis')

  ses_num = 0
  for i, ses in sessions.iterrows():
    ses_num += 1
    x_left = 0
    y_bottom = ses_num - 0.4
    width = ses.duration
    if (i != -1):
      ses_rect = mpatches.Rectangle((x_left, y_bottom), width=width, height=0.8,
        fill=False, edgecolor='k', linewidth=0.5, zorder=5)
      ax.add_artist(ses_rect)
    else:
      ax.plot([-20, 600], [ses_num, ses_num], color='k', linestyle='-', linewidth=1)
      ses_num += 1

    ses_assigns = surgeries.loc[sol_assigns.loc[
      sol_assigns['session_id'] == ses.name, 'surgery_id'], ]
    ses_assigns = ses_assigns.sort_values('priority', ascending=False)

    x2_left = 0
    for j, sur in ses_assigns.iterrows():
      width2 = sur.duration
      if (i == -1):
        rect_height = 0.2
        if (x2_left + width2 > 540):
          x2_left = 0
          ses_num += 0.25

      else:
        rect_height = 0.7

      y2_bottom = ses_num - 0.35

      sur_rect = mpatches.Rectangle((x2_left, y2_bottom), width=width2, height=rect_height,
        fill=True, color=smap.to_rgba(sur.priority), linewidth=0.5)
      ax.add_artist(sur_rect)

      if sol_transfers is not None:
        if sol_transfers.loc[j] > 0:
          if i != -1:
            ax.text(x2_left + width2/2, y2_bottom + rect_height*0.3,
              s='{0:.0f}'.format(sol_transfers.loc[j]), fontsize=6,
              horizontalalignment='center', verticalalignment='baseline',
              path_effects=[patheffects.withStroke(linewidth=0.5, foreground="w")])

          else:
            ax.text(x2_left + width2/2, y2_bottom,
              s='{0:.0f}'.format(sol_transfers.loc[j]), fontsize=4,
              horizontalalignment='center', verticalalignment='baseline',
              path_effects=[patheffects.withStroke(linewidth=0.5, foreground="w")])

      # ax.text(x2_left + width2/2, y_bottom + 0.2, s='{0:.0f}\n{1:.2f}-{2:.0f}'.format(j, sur.priority, sur.duration),
      #     fontsize='xx-small', horizontalalignment='center',
      #     verticalalignment='baseline',)

      if (i != -1):
        x2_left += width2 + 15

      else:
        x2_left += width2 + 5

  ax.set_xlim(-20, 600)
  ax.set_ylim(0.5, np.ceil(ses_num))
  y_tick_list = list(range(1, sessions.shape[0]))
  ax.set_yticks(y_tick_list)

  save_file = os.path.join(OUTPUT_FIG_DIR, fig_name + '.pdf')
  # ax.set_title('Generated Sessions')
  ax.set_xlabel('Time (h)')
  ax.set_ylabel('Session')

  fig.set_size_inches(3.1, 3.49)
  # fig.set_size_inches(6, 5)
  fig.subplots_adjust(left=.15, bottom=0.12, right=0.95, top=0.99)
  pyp.savefig(save_file,
    orientation='landscape', transparent=True, dpi=500, format='pdf')
  pyp.close()

  # pyp.show()

  return 0


def vis_sessions(db_ses, fig_name):

  sessions = get_sessions(db_ses)
  sessions = sessions.sort_values('start_datetime')
  
  fig, ax = pyp.subplots()

  cnorm = Normalize(vmin=0, vmax=1)
  smap = ScalarMappable(cnorm, 'viridis')

  ses_num = 0
  for i, ses in sessions.iterrows():
    ses_num += 1
    x_left = 0
    y_bottom = ses_num - 0.4
    width = ses.duration
    if (i != -1):
      ses_rect = mpatches.Rectangle((x_left, y_bottom), width=width, height=0.8,
        fill=False, edgecolor='k', linewidth=0.5, zorder=5)
      ax.add_artist(ses_rect)
    # else:
    #   ax.plot([-20, 600], [ses_num, ses_num], color='k', linestyle='-', linewidth=1)
    #   ses_num += 1

  ax.set_xlim(-20, 600)
  ax.set_ylim(0.5, np.ceil(ses_num))
  ax.set_axis_off()
  # y_tick_list = list(range(1, sessions.shape[0]))
  # ax.set_yticks(y_tick_list)

  save_file = os.path.join(OUTPUT_FIG_DIR, fig_name + '.pdf')
  # ax.set_title('Generated Sessions')
  # ax.set_xlabel('Time (h)')
  # ax.set_ylabel('Session')

  fig.set_size_inches(3, 3.49)
  # fig.set_size_inches(6, 5)
  fig.subplots_adjust(left=.01, bottom=0.01, right=0.99, top=0.999)
  pyp.savefig(save_file,
    orientation='landscape', transparent=True, dpi=500, format='pdf')
  pyp.close()

  # pyp.show()

  return 0


def vis_surgeries(db_ses, sur_ids, fig_name):

  surgeries = get_surgeries(db_ses)

  vis_surs = surgeries.loc[sur_ids, ]

  fig, ax = pyp.subplots()

  cnorm = Normalize(vmin=0, vmax=1)
  smap = ScalarMappable(cnorm, 'viridis')

  ses_num = 0
  ses_num += 1
  x_left = 0
  y_bottom = ses_num - 0.4
  
  x2_left = 0
  for j, sur in vis_surs.iterrows():
    width2 = sur.duration

    if (x2_left + width2 > 540):
      x2_left = 0
      ses_num += 1

    rect_height = 0.7

    y2_bottom = ses_num - 0.35

    sur_rect = mpatches.Rectangle((x2_left, y2_bottom), width=width2, height=rect_height,
      fill=True, color=smap.to_rgba(sur.priority), linewidth=0.5)
    ax.add_artist(sur_rect)

    x2_left += width2 + 5

  ax.set_xlim(-20, 600)
  ax.set_ylim(0.5, np.ceil(ses_num + 1))
  ax.set_axis_off()

  save_file = os.path.join(OUTPUT_FIG_DIR, fig_name + '.pdf')
  # ax.set_title('Generated Sessions')
  # ax.set_xlabel('Time (h)')
  # ax.set_ylabel('Session')

  fig.set_size_inches(3, 3.49)
  # fig.set_size_inches(6, 5)
  fig.subplots_adjust(left=.01, bottom=0.01, right=0.999, top=0.99)
  pyp.savefig(save_file,
    orientation='landscape', transparent=True, dpi=500, format='pdf')
  pyp.close()

  # pyp.show()

  return 0
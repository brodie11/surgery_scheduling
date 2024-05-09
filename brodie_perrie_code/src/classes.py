from numpy.random import Generator, default_rng
import math

rng = default_rng()

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
  
#   if __name__ == '__main__':
#       name = 0
#       expected_duration = 10
#       duration_variance = 5
#       arrive_date = 1
#       due_date = 10
#       sched = schedSurgery(name, expected_duration, duration_variance,
#       arrive_date, due_date)
#       print(f"sched.days_banned {sched.days_banned} sched.inconvenient_days {sched.weeks_banned} sched.months_banned {sched.months_banned}")
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

filepath = Path("toms_code/output/databases/percentile_metrics.csv")
df = pd.read_csv(filepath)

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='num_surgeries_completed', data=df)
plt.title('Number of surgeries scheduled for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Number of surgeries scheduled')
plt.show()

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='average_surgery_utilisation', data=df)
plt.title('Average surgery utilisation scheduled for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Average surgery utilisation')
plt.show()

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='total_mins_overtime', data=df)
plt.title('Total mins overtime scheduled for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Total mins overtime')
plt.show()

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='num_sessions_that_run_overtime', data=df)
plt.title('Number of sessions that run overtime for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Number of overtime sessions')
plt.show()

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='num_sessions_with_cancelled_surgeries', data=df)
plt.title('Number of sessions with cancelled surgeries for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Number of sessions with cancelled surgeries')
plt.show()

plt.figure(figsize=(8, 6))
sns.violinplot(x='percentile_column_name', y='num_surgeries_cancelled', data=df)
plt.title('Number of cancelled surgeries for each percentile value')
plt.xlabel('Percentile Values')
plt.ylabel('Number of cancelled surgeries')
plt.show()
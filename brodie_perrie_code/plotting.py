import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import norm

filepath = Path("toms_code/output/databases/experiment-no-ordering-1000-runs/percentile_metrics_debug_s0fA_ordered2024-07-251001.csv")
save_location = Path("brodie_perrie_code/output/plots/debug/random_seed")
df = pd.read_csv(filepath)

# Creating subplots with multiple histograms
data1 = df[df['percentile_column_name'] == 'duration_45th_percentile']
data2 = df[df['percentile_column_name'] == 'duration_50th_percentile']
data3 = df[df['percentile_column_name'] == 'duration_55th_percentile']
data4 = df[df['percentile_column_name'] == 'duration_60th_percentile']
data5 = df[df['percentile_column_name'] == 'duration_65th_percentile']
data6 = df[df['percentile_column_name'] == 'duration_70th_percentile']

# plt.figure(figsize=(8, 6))
# sns.displot(data=df, x='num_surgeries_completed', hue="percentile_column_name", kind="kde", legend=False, aspect=1.5)
# plt.legend(df['percentile_column_name'].unique(), loc='upper left', bbox_to_anchor=(0, 1))
# plt.title("Kernel density plot for number of surgeries completed")
# # plt.legend(loc="upper left")
# plt.tight_layout()
# plt.savefig(f"{save_location}/num_surg_completed_kde.png")

# # plotting histograms 
# plt.figure(figsize=(8, 6))
# plt.hist(data1['num_surgeries_completed'],  
#          alpha=0.4,  
#          label='45th', 
#          color='red')

# plt.hist(data2['num_surgeries_completed'],  
#          alpha=0.4,  
#          label='50th', 
#          color='blue')
  
# plt.hist(data3['num_surgeries_completed'],  
#          alpha=0.4,  
#          label='55th', 
#          color='green')
  
# plt.hist(data4['num_surgeries_completed'],  
#          alpha=0.4,  
#          label='60th', 
#          color='yellow')

# plt.hist(data5['num_surgeries_completed'],  
#          alpha=0.4,  
#          label='65th', 
#          color='purple')

# plt.legend(loc='upper right') 
# plt.title('Number of surgeries completed for each percentile value') 
# plt.tight_layout()
# plt.savefig(f"{save_location}/num_surg_completed.png")

# plotting normal distributions fitted to data
def plot_normal(data, label, colour, column):
    mu, std = norm.fit(data[column])
    xmin = min(data[column])
    xmax = max(data[column])
    x = np.linspace(xmin, xmax, 100)
    p = norm.pdf(x, mu, std)
    plt.plot(x, p, linewidth=2, label=label, color=colour)
    plt.axvline(x=mu, color=colour, label=f"{label} mean", linestyle=":")

plt.figure(figsize=(8, 6))
column = 'num_surgeries_completed'
colours = ['#ef476f', '#f78c6b', '#ffd166', '#06d6a0', '#118ab2', '#073b4c']
# plot_normal(data1, label="45th", colour=colours[0], column=column)
# plot_normal(data2, label="50th", colour=colours[1], column=column)
# plot_normal(data3, label="55th", colour=colours[2], column=column)
# plot_normal(data4, label="60th", colour=colours[3], column=column)
# plot_normal(data5, label="65th", colour=colours[4], column=column)
# plot_normal(data6, label="70th", colour=colours[5], column=column)

plt.title("Comparison of PDFS for different percentile values")
plt.ylabel("PDF")
plt.xlabel("Number of surgeries completed")
plt.legend()
plt.savefig(f"{save_location}/num_surg_completed_norm_dist.png")

def twin_axis_compare(values1, label1, values2, label2, plot_title, file_name):
    # Create figure and axis objects
    fig, ax1 = plt.subplots()

    percentiles = ["40th", "45th", "50th", "55th", "60th", "65th", "70th"]

    # Plot surgeries completed
    color = 'tab:blue'
    ax1.set_xlabel('Percentile Values')
    ax1.set_ylabel(label1, color=color)
    ax1.plot(percentiles, values1, color=color, marker='o', linestyle='dotted')
    ax1.tick_params(axis='y', labelcolor=color)

    # Create a second y-axis for surgeries cancelled
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel(label2, color=color)
    ax2.plot(percentiles, values2, color=color, marker='o', linestyle='dotted')
    ax2.tick_params(axis='y', labelcolor=color)

    # Add title and display the plot
    plt.title(plot_title)
    plt.savefig(f"{save_location}/{file_name}")

# Plot twin axis comparison for surgeries completed and cancelled
average_surgeries_completed = df.groupby('percentile_column_name')['num_surgeries_completed'].mean()
label1 = "Average Surgeries Completed"
average_surgeries_cancelled = df.groupby('percentile_column_name')['num_surgeries_cancelled'].mean()
label2 = "Average Surgeries Cancelled"
plot_title = 'Average Surgeries Completed vs. Average Surgeries Cancelled'
file_name = 'completed_vs_cancelled.png'
twin_axis_compare(values1=average_surgeries_completed,label1=label1, values2=average_surgeries_cancelled, label2=label2, plot_title=plot_title, file_name=file_name)

# Plot twin axis comparison for average surgery utilisation and total mins overtime
average_surgery_utilisation = df.groupby('percentile_column_name')['average_session_utilisation'].mean()
label1 = "Average Session Utilisation"
total_mins_overtime = df.groupby('percentile_column_name')['total_mins_overtime'].mean()
label2 = "Average Mins Overtime Per Schedule"
plot_title = 'Average Session Utilisation vs. Average Mins Overtime Per Schedule'
file_name = 'utilisation_vs_overtime.png'
twin_axis_compare(values1=average_surgery_utilisation,label1=label1, values2=total_mins_overtime, label2=label2, plot_title=plot_title, file_name=file_name)

# Plot twin axis comparison for number of sessions that run overtime and number of sessions with cancelled surgeries
num_sessions_that_run_overtime = df.groupby('percentile_column_name')['num_sessions_that_run_overtime'].mean()
label1 = "Number of sessions that run overtime"
num_sessions_with_cancelled_surgeries = df.groupby('percentile_column_name')['num_sessions_with_cancelled_surgeries'].mean()
label2 = "Number of sessions with cancelled surgeries"
plot_title = '# Overtime sessions vs. # Sessions with cancelled surgeries'
file_name = 'num_overtime_vs_num_cancelled.png'
twin_axis_compare(values1=num_sessions_that_run_overtime,label1=label1, values2=num_sessions_with_cancelled_surgeries, label2=label2, plot_title=plot_title, file_name=file_name)

# Plot twin axis comparison for number of sessions that run overtime and number of sessions with cancelled surgeries
average_surgery_utilisation = df.groupby('percentile_column_name')['average_session_utilisation'].mean()
label1 = "Average Session Utilisation"
average_surgeries_cancelled = df.groupby('percentile_column_name')['num_surgeries_cancelled'].mean()
label2 = "Average Surgeries Cancelled"
plot_title = 'Average Session Utilisation vs. Average Number of Cancelled Surgeries'
file_name = 'avg_util_vs_avg_cancelled.png'
twin_axis_compare(values1=average_surgery_utilisation,label1=label1, values2=average_surgeries_cancelled, label2=label2, plot_title=plot_title, file_name=file_name)

# plot sum of cancelled and completed session
grouped_df = df.groupby('percentile_column_name').agg({
    'num_surgeries_completed': 'sum',
    'num_surgeries_cancelled': 'sum'
})

sum_cancelled_completed = grouped_df['num_surgeries_completed'] + grouped_df['num_surgeries_cancelled']

# Plot settings
label1 = "Sum of cancelled and completed sessions"
plot_title = 'Sum of cancelled and completed sessions'
file_name = 'sum_cancelled_completed.png'

percentiles = grouped_df.index.tolist()  # Using index from grouped_df
values = sum_cancelled_completed.tolist()  # Converting the series to a list

# Plot the sum of cancelled and completed surgeries
color = 'tab:blue'
plt.figure(figsize=(10, 6))
plt.xlabel('Percentile Values')
plt.ylabel(label1, color=color)
plt.plot(percentiles, values, color=color, marker='o', linestyle='dotted')
plt.tick_params(axis='y', labelcolor=color)

# Add title and save the plot
plt.title(plot_title)
plt.savefig(f"{save_location}/{file_name}")


# Plot total mins surgery time
avg_mins_surgery_time = df.groupby('percentile_column_name')['total_mins_surgery_time'].mean()

# Plot settings
label1 = "Average mins spent operating per schedule"
plot_title = 'Average mins spent operating per schedule'
file_name = 'minutes_in_surgery.png'

percentiles = grouped_df.index.tolist()  # Using index from grouped_df

# Plot the sum of cancelled and completed surgeries
color = 'tab:blue'
plt.figure(figsize=(10, 6))
plt.xlabel('Percentile Values')
plt.ylabel(label1, color=color)
plt.plot(percentiles, avg_mins_surgery_time, color=color, marker='o', linestyle='dotted')
plt.tick_params(axis='y', labelcolor=color)

# Add title and save the plot
plt.title(plot_title)
plt.savefig(f"{save_location}/{file_name}")
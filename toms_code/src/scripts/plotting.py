import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import norm

filepath = Path("output/databases/percentile_metrics.csv")
df = pd.read_csv(filepath)


# Creating subplots with multiple histograms
data1 = df[df['percentile_column_name'] == 'duration_45th_percentile']
data2 = df[df['percentile_column_name'] == 'duration_50th_percentile']
data3 = df[df['percentile_column_name'] == 'duration_55th_percentile']
data4 = df[df['percentile_column_name'] == 'duration_60th_percentile']
data5 = df[df['percentile_column_name'] == 'duration_65th_percentile']

# plotting histograms 
plt.hist(data1['num_surgeries_completed'],  
         alpha=0.4,  
         label='45th', 
         color='red')

  
plt.hist(data2['num_surgeries_completed'],  
         alpha=0.4,  
         label='50th', 
         color='blue')
  
plt.hist(data3['num_surgeries_completed'],  
         alpha=0.4,  
         label='55th', 
         color='green')
  
plt.hist(data4['num_surgeries_completed'],  
         alpha=0.4,  
         label='60th', 
         color='yellow')

plt.hist(data5['num_surgeries_completed'],  
         alpha=0.4,  
         label='65th', 
         color='purple')



plt.legend(loc='upper right') 
plt.title('Number of surgeries completed for each percentile value') 
plt.show()

# plotting normal distributions fitted to data
def plot_normal(data, label, colour):
    mu, std = norm.fit(data['num_surgeries_completed'])
    xmin = min(data['num_surgeries_completed'])
    xmax = max(data['num_surgeries_completed'])
    x = np.linspace(xmin, xmax, 100)
    p = norm.pdf(x, mu, std)
    plt.plot(x, p, linewidth=2, label=label, color=colour)
    plt.axvline(x=mu, color=colour, label=f"{label} mean", linestyle=":")

plot_normal(data1, label="45th", colour="red")
plot_normal(data2, label="50th", colour="green")
plot_normal(data3, label="55th", colour="blue")
plot_normal(data4, label="60th", colour="orange")
plot_normal(data5, label="65th", colour="purple")

plt.title("Comparison of PDFS for different percentile values")
plt.ylabel("PDF")
plt.xlabel("Number of surgeries completed")
plt.legend()
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
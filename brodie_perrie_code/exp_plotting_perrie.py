import os
import pandas as pd
import matplotlib.pyplot as plt

# Plot average value results 
def plot_dual_average_values(df, x_column, y1_column, y2_column, fig_title, xlabel="X-axis", ylabel1="Y1-axis", ylabel2="Y2-axis"):
    """
    Plots a dual-axis chart with two y-axes.
    
    Parameters:
    df (pd.DataFrame): The DataFrame containing the data
    x_column (str): The column to use for the x-axis (e.g., percentile or overtime)
    y1_column (str): The column to use for the left y-axis
    y2_column (str): The column to use for the right y-axis
    fig_title (str): Title of the figure for saving
    xlabel (str): Label for the x-axis
    ylabel1 (str): Label for the left y-axis
    ylabel2 (str): Label for the right y-axis
    title (str): Title of the plot
    """

    # Ensure the columns are numeric
    df[y1_column] = pd.to_numeric(df[y1_column], errors='coerce')
    df[y2_column] = pd.to_numeric(df[y2_column], errors='coerce')
    df[x_column] = pd.to_numeric(df[x_column], errors='coerce')
    
    # Get unique x_column values
    unique_x_values = df[x_column].unique()

    # Initialize lists to store the filtered data
    x_values = []
    y1_values = []
    y2_values = []

    # Loop through unique x_column values and filter the dataframe for corresponding y values
    for x_val in unique_x_values:
        filtered_df = df[df[x_column] == x_val]
        
        # Calculate the mean for y1 and y2 corresponding to the current x_val
        y1_mean = filtered_df[y1_column].mean()
        y2_mean = filtered_df[y2_column].mean()

        # Append the results to the lists
        x_values.append(x_val)
        y1_values.append(y1_mean)
        y2_values.append(y2_mean)

    # Sort values based on x_column for plotting
    sorted_x_values, sorted_y1_values, sorted_y2_values = zip(*sorted(zip(x_values, y1_values, y2_values)))

    # Plotting the data
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot the first y-axis (y1 values)
    color1 = 'tab:blue'
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel1, color=color1)
    ax1.plot(sorted_x_values, sorted_y1_values, color=color1, label=y1_column, marker="o")
    ax1.tick_params(axis='y', labelcolor=color1)

    # Create a second y-axis sharing the same x-axis (y2 values)
    ax2 = ax1.twinx()
    color2 = 'tab:red'
    ax2.set_ylabel(ylabel2, color=color2)
    ax2.plot(sorted_x_values, sorted_y2_values, color=color2, label=y2_column, marker="o")
    ax2.tick_params(axis='y', labelcolor=color2)

    # Show the grid
    ax1.grid(True)

    # Display the plot
    plt.savefig(f'brodie_perrie_code/output/Perrie_exp/plots/{fig_title}.png', format='png')


# Path to the folder containing your CSV files
folder_path = 'brodie_perrie_code/output/perrie_experiments'

# overtime results
filename = 'metricss_0_f_A_sd_0301_ed_0301_ipic_F_idce_F_mdp_-1_mds_-1_ipc_F_pc_[50]_ioc_T_dct_91_tl_20_og_05.csv'
file_path = os.path.join(folder_path, filename)
overtime_dataframe  = pd.read_csv(file_path)

x_col = "allowed overtime"
y_col1 = "total cancelled overtime"
y_col2 = "num sessions overtime"

plot_dual_average_values(overtime_dataframe, x_col, y_col1, y_col2, fig_title = "overtime_num_cancelled_min_over", xlabel="Overtime Values (mins)", ylabel1="Average # of Cancellations", ylabel2="Average # of Overtime Sessions")

x_col = "allowed overtime"
y_col1 = "average utilisation"
y_col2 = "average overtime"

plot_dual_average_values(overtime_dataframe, x_col, y_col1, y_col2, fig_title = "utilisation_min_over", xlabel="Overtime Values (mins)", ylabel1="Average Utilisation", ylabel2="Average Overtime (mins)")

# percentile results
filename = 'metricss_0_f_A_sd_0301_ed_0301_ipic_F_idce_F_mdp_-1_mds_-1_ipc_T_pc_[30, 35, 40, 45, 50, 55, 60]_ioc_F_dct_91_tl_20_og_05.csv'
file_path = os.path.join(folder_path, filename)
percentile_dataframe = pd.read_csv(file_path)

x_col = "percentile"
y_col1 = "total cancelled overtime"
y_col2 = "num sessions overtime"

plot_dual_average_values(percentile_dataframe, x_col, y_col1, y_col2, fig_title = "overtime_num_cancelled_min_over_percentile", xlabel="Percentile Values", ylabel1="Average # of Cancellations", ylabel2="Average # of Overtime Sessions")

x_col = "percentile"
y_col1 = "average utilisation"
y_col2 = "average overtime"

plot_dual_average_values(percentile_dataframe, x_col, y_col1, y_col2, fig_title = "utilisation_min_over_percentile", xlabel="Percentile Values", ylabel1="Average Utilisation", ylabel2="Average Overtime (mins)")


def plot_avg_wait_time(df, x_column, fig_title, xlabel="X-axis"):
    """
    Plots a graph showing the average wait time for each priority level against the varying experimental value.
    
    Parameters:
    df (pd.DataFrame): The DataFrame containing the data
    x_column (str): The column to use for the x-axis (e.g., percentile or overtime)
    fig_title (str): Title of the figure for saving
    xlabel (str): Label for the x-axis
    title (str): Title of the plot
    """

    # Define columns of interest
    y1 = "average wait time (priority < 0.33)"
    y2 = "average wait_time (0.33 < priority < 0.66)"
    y3 = "average wait time 0.66 < priority"

    # Get unique x_column values
    unique_x_values = df[x_column].unique()

    # Initialize lists to store the filtered data
    x_values = []
    y1_values = []
    y2_values = []
    y3_values = []

    # Loop through unique x_column values and filter the dataframe for corresponding y values
    for x_val in unique_x_values:
        filtered_df = df[df[x_column] == x_val]
        
        # Calculate the mean for y1 and y2 corresponding to the current x_val
        y1_mean = filtered_df[y1].mean()
        y2_mean = filtered_df[y2].mean()
        y3_mean = filtered_df[y3].mean()

        # Append the results to the lists
        x_values.append(x_val)
        y1_values.append(y1_mean)
        y2_values.append(y2_mean)
        y3_values.append(y3_mean)

    # Sort values based on x_column for plotting
    sorted_x_values, sorted_y1_values, sorted_y2_values, sorted_y3_values = zip(*sorted(zip(x_values, y1_values, y2_values, y3_values)))

    # Plotting the data
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot the first y-axis (y1 values)
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel("Average Waiting Time (# Days)")
    ax1.plot(sorted_x_values, sorted_y1_values, label="Priority < 0.33", marker="o")
    ax1.plot(sorted_x_values, sorted_y2_values, label="0.33 < Priority < 0.66", marker="o")
    ax1.plot(sorted_x_values, sorted_y3_values, label="Priority > 0.66", marker="o")
    ax1.legend()

    # Show the grid
    ax1.grid(True)

    # Display the plot
    plt.savefig(f'brodie_perrie_code/output/Perrie_exp/plots/{fig_title}.png', format='png')

# Overtime priority waiting time
plot_avg_wait_time(overtime_dataframe, "allowed overtime", "priority_wait_time_overtime", "Overtime Values (mins)")

# Percentiles priority waiting time
plot_avg_wait_time(percentile_dataframe, "percentile", "priority_wait_time_percentile", "Percentile Values")

def get_baseline_results(overtime_dataframe):
    """Gets the baseline model performance metrics"""

    filtered_df = overtime_dataframe[overtime_dataframe["allowed overtime"] == 0]
    results_df = pd.DataFrame()

    # Select the relevant columns
    last_columns = filtered_df.iloc[:, -15:]
    mean_values = last_columns.mean()
    mean_df = pd.DataFrame(mean_values, columns=['Mean'])

    # Add the original column names as a new column in the result dataframe
    mean_df['Original Column'] = mean_df.index

    # Reset index
    mean_df = mean_df.reset_index(drop=True)

    results_df = pd.concat([results_df, mean_df], ignore_index=True)

    csv_title = "baseline_results"
    results_df.to_csv(f'brodie_perrie_code/output/Perrie_exp/plots/{csv_title}.csv', index=False)

    return

get_baseline_results(overtime_dataframe)



    
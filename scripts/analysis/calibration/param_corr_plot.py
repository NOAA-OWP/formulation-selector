import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# 1. Define your input and output directories
# Update dir_raw_data if your parameter files are in a different folder
dir_raw_data = Path("~/noaa/regionalization/data/raw/regn_apr26_test1").expanduser()

dir_out_plots = dir_raw_data / "correlation_plots"
dir_out_plots.mkdir(exist_ok=True, parents=True)

# 2. Find all matching parquet files
param_files = list(dir_raw_data.glob("*_params.parquet"))
print(f"Found {len(param_files)} parameter files to process.")

# 3. Loop over each file
for path_params in param_files:
    
    # Extract the formulation name from the filename (e.g., 'pet_snow17_sacsma_selected')
    formulation_name = path_params.name.replace("_params.parquet", "")
    print(f"Processing {formulation_name}...")
    
    # Read the data
    df_params = pd.read_parquet(path_params)
    
    # Isolate the numeric parameter columns
    df_numeric = df_params.select_dtypes(include='number')
    
    if df_numeric.empty:
        print(f"  ⚠️ Skipping {formulation_name}: No numeric columns found.")
        continue
        
    # Calculate the Pearson correlation matrix
    df_corr = df_numeric.corr()
    
    # Create the plot
    plt.figure(figsize=(16, 12))
    sns.heatmap(
        df_corr, 
        annot=False,  # Switch to True if you want the correlation decimals visible
        cmap='coolwarm', 
        linewidths=0.5, 
        vmin=-1, 
        vmax=1
    )
    
    # Formatting
    plt.title(f'Parameter Correlation Matrix: {formulation_name}', fontsize=20)
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    
    # Save the plot dynamically based on the formulation name
    path_out_plot = dir_out_plots / f"param_corr_{formulation_name}.png"
    plt.savefig(path_out_plot, dpi=300)
    print(f"  ✅ Saved plot to {path_out_plot.name}")
    
    # CRITICAL: Clear the figure from memory to prevent RAM leaks
    plt.clf()
    plt.close()

    path_out_plot_sign = dir_out_plots / f"param_corr_significant_{formulation_name}.png"
    mask = abs(df_corr) <= 0.4
    plt.figure(figsize=(16, 12))
    sns.heatmap(
        df_corr, 
        mask=mask,  # Blank out values <= 0.4
        annot=True, # Optional: safe to turn on now since fewer squares will be shown
        cmap='YlOrRd', 
        linewidths=0.5, 
        vmin=0.4, 
        vmax=1.0
    )
    
    plt.title(f'Parameter Correlation Matrix: {formulation_name}', fontsize=20)
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    plt.savefig(path_out_plot_sign, dpi=300)
    plt.clf()
    plt.close()
    
print(f"Finished! All plots are saved in: {dir_out_plots}")
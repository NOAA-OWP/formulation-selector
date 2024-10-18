'''
@title: Format model results for the linear model run by 2022 Summer Institute "Formulation and Evaluation" team (Bolotin, Liu, Liao, Haces)
@author: Lauren Bolotin <lauren.bolotin@noaa.gov>
@description: Reads in the linear model dataset, which is for a subset of CAMELS basins, 
    and converts to a standard format expected by the formulation-selector tooling.
@usage: python proc_SI_lm_metrics.py "/full/path/to/SI_lm_schema.yaml"

Changelog/contributions
    2024-07-02 Originally created, GL
'''
import argparse
import pandas as pd
from pathlib import Path
import yaml
from fs_proc.proc_eval_metrics import read_schm_ls_of_dict, proc_col_schema

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    # The path to the configuration
    path_config = args.path_config # '/Users/laurenbolotin/Lauren/FSDS/fsds/scripts/eval_ingest/SI/SI_LSTM_schema.yaml' 

    if not Path(path_config).exists():
        raise ValueError("The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    with open(path_config, 'r') as file:
        config = yaml.safe_load(file)

    # ----- File IO
    print("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and format the home_dir in case it was defined in file path
    path_data = col_schema_df['path_data'].loc[0].format(home_dir = str(Path.home()))
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir = str(Path.home()))

    # BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in the 2022 Summer Institute's linear model (LM) results
    print("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_csv(path_data,index_col = 0, dtype={col_schema_df['gage_id'].loc[0] :str})
    df_all_data = df_all_data.drop(columns=['fold'])

    # Ensure appropriate str formats & remove extraneous spaces that exist in this particular dataset
    df_all_data.columns = df_all_data.columns.str.replace(' ','')
    
    df = df_all_data
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    print(f"Standardizing datasets and writing to {dir_save}")
    ds = proc_col_schema(df, col_schema_df, dir_save)
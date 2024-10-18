'''
@title: Find CAMELS basins inside Julie Mai's xSSA dataset
@author: Guy Litt <guy.litt@noaa.gov>
@description: Reads in the xSSA dataset, 
    subset xSSA data to just CAMELS basins, 
    and converts to a standard format expected by the formulation-selector tooling.
@usage: python proc_xssa_metrics.py "/full/path/to/xssa_config.yaml"

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
    path_config = args.path_config # '~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_config.yaml' 

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
    path_camels = col_schema_df['path_camels'].loc[0].format(home_dir = str(Path.home()))
    path_data = col_schema_df['path_data'].loc[0].format(home_dir = str(Path.home()))
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir = str(Path.home()))

    # BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in Julie Mai's 2022 Nat Comm xSSA results
    print("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_csv(path_data,sep = '; ',dtype={col_schema_df['gage_id'].loc[0] :str})

    # Ensure appropriate str formats & remove extraneous spaces that exist in this particular dataset
    df_all_data.columns = df_all_data.columns.str.replace(' ','')
    df_all_data[col_schema_df['gage_id'].loc[0]] = df_all_data[col_schema_df['gage_id'].loc[0]].str.replace(' ','')

    # Read in CAMELS data (simply to retrieve the gauge_ids)
    df_camlh = pd.read_csv(path_camels,sep=';',dtype={'gauge_id' :str})
    
    # Subset the xssa dataset to CAMELS basins
    print(f"Subsetting the dataset {col_schema_df['dataset_name']} to CAMELS basins")
    df_camls_merge = df_camlh.merge(df_all_data, left_on= 'gauge_id', right_on = col_schema_df['gage_id'].loc[0], how='inner')
    df = df_camls_merge.drop(columns = df_camlh.columns)
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    
    ds = proc_col_schema(df, col_schema_df, dir_save)
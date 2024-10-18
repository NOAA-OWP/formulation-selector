'''
title: Find CAMELS basins inside Julie Mai's xSSA dataset
author: Guy Litt <guy.litt@noaa.gov>
description: Reads in the xSSA dataset, 
    subset xSSA data to just CAMELS basins, 
    and converts to a standard format expected by the formulation-selector tooling.
usage: python proc_xssa_metrics.py "/full/path/to/xssa_schema.yaml"

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
    path_config = args.path_config # './ngenBEC_TOPMODEL_schema.yaml' # 


    if not Path(path_config).exists():
        raise ValueError("The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    # with open(path_config, 'r') as file:
    #     config = yaml.safe_load(file)

    # ----- File IO
    print("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and format the home_dir in case it was defined in file path
    path_data = (col_schema_df.loc[0, 'path_data']
                    .format(home_dir = str(Path.home())))
    dir_save = (col_schema_df.loc[0, 'dir_save']
                    .format(home_dir = str(Path.home())))

    # BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in ngen calibration results from Choat et al 2024 - in progress
    print("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_csv(
        path_data,
        dtype={col_schema_df.loc[0, 'gage_id']: str}
    )

    form_work = col_schema_df.loc[0, 'formulation_base']

    df = df_all_data.query("Model_RR == @form_work")

    # -----------------------------
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    print(f"Standardizing datasets and writing to {dir_save}")

    ds = proc_col_schema(df, col_schema_df, dir_save)
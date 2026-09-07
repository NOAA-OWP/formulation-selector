'''
@title: Generate a test dataset from hfATLAS outputs
@author: Guy Litt <guy.litt@noaa.gov>
@description: Just a fake dataset
@usage: python prep_hfatl_metrics.py "/full/path/to/hfatl_prep_config.yaml"

Changelog/contributions
    2026-04-20 Originally created, GL
'''
import argparse
import pandas as pd
from pathlib import Path
import yaml
import rafts_prep.proc_eval_metrics as pem
import logging

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    # The path to the configuration
    path_config = Path(args.path_config).expanduser() # path_config = Path('~/git/rafts/scripts/workflow_configs/legacy/xssa/xssa_prep_config.yaml').expanduser() 

    if not Path(path_config).exists():
        raise ValueError("The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    with open(path_config, 'r') as file:
        config = yaml.safe_load(file)

    # Logger setup - first define required paths/name in the config
    home_dir = Path("~/").expanduser()
    dir_save = [x for x in config['file_io'] if 'dir_save' in x.keys()][0]['dir_save'].format(home_dir = home_dir)

    # Generate path to the log file & initialize logging
    path_log = pem.std_path_log(dir_input=dir_save, path_config=path_config,
                            script='prep_xssa_metrics')
    logging.basicConfig(level=logging.INFO, filename=path_log, format='%(asctime)s - %(levelname)s - %(message)s')

    # ----- File IO
    logging.info("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = pem.read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and format the home_dir in case it was defined in file path
    path_data = col_schema_df['path_data'].loc[0].format(home_dir = str(Path.home()))
    dir_save = col_schema_df['dir_save'].loc[0].format(home_dir = str(Path.home()))
    
    # BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in hfatlas test dataset
    logging.info("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_parquet(path_data)#,engine="pyarrow")
   # df_all_data[col_schema_df['gage_id']] = df_all_data.index.astype(str)

    print("Subsetting to 8000 locations just for testing.")
    df_all_data = df_all_data.sample(n=8000, random_state=42)
    # Drop unnamed column
    #df_all_data = df_all_data.drop(columns=[col for col in df_all_data.columns if "Unnamed" in col])

    # Ensure appropriate str formats & remove extraneous spaces that exist in this particular dataset
    # df_all_data.columns = df_all_data.columns.str.replace(' ','')
    #df_all_data[col_schema_df['gage_id'].loc[0]] = df_all_data[col_schema_df['gage_id'].loc[0]].str.replace(' ','')

 
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    ds = pem.proc_col_schema(df_all_data, col_schema_df, dir_save)
    print("COMPLETED PROCESSING prep_hfatl_test.py")
    logging.shutdown() # Remember to add this at the end of each script so that log files are separated by the script run
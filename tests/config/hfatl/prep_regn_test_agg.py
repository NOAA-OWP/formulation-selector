'''
@title: Generate a test dataset from hfATLAS outputs based on basin-aggregated values
@author: Guy Litt <guy.litt@noaa.gov>
@description: This is the first rafts_select output from the July 2026 calibration
 experiments. Selection criteria: multiobj function, equally weighting NNSE & MAPPE
@usage: 
python agg_calib_basins.py # Must run first
python prep_regn_test.py "/full/path/to/regn_prep_config.yaml"

Changelog/contributions
    2026-04-20 Originally created, GL
    2026-05-13 Adapted from hfatl_test, GL
'''
import argparse
import pandas as pd
from pathlib import Path
import yaml
import rafts_prep.proc_eval_metrics as pem
import logging
import geopandas as gpd
import ast

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    
    # The path to the configuration
    path_config = Path(args.path_config).expanduser().resolve()

    if not path_config.exists():
        raise ValueError(f"The provided path to the configuration file does not exist: {path_config}")

    # Load the YAML configuration file
    with open(path_config, 'r') as file:
        config = yaml.safe_load(file)

    # Logger setup - first define required paths/name in the config
    home_dir = str(Path.home())
    
    # Extract dir_save and make it robust to relative test paths
    dir_save_raw = [x for x in config['file_io'] if 'dir_save' in x.keys()][0]['dir_save'].format(home_dir=home_dir)
    dir_save_path = Path(dir_save_raw).expanduser()
    if not dir_save_path.is_absolute():
        dir_save_path = (path_config.parent / dir_save_path).resolve()
    
    # Ensure the save directory exists for tests
    dir_save_path.mkdir(parents=True, exist_ok=True)
    dir_save = str(dir_save_path)

    # Generate path to the log file & initialize logging
    path_log = pem.std_path_log(dir_input=dir_save, path_config=path_config,
                            script='prep_xssa_metrics')
    logging.basicConfig(level=logging.INFO, filename=path_log, format='%(asctime)s - %(levelname)s - %(message)s')

    # ----- File IO
    logging.info("Converting schema to DataFrame")
    # Read in the config file & convert to pd.DataFrame
    col_schema_df = pem.read_schm_ls_of_dict(schema_path = path_config)

    # Extract path and make it robust to relative test paths
    path_data_raw = col_schema_df['path_data'].loc[0].format(home_dir=home_dir)
    path_data = Path(path_data_raw).expanduser()
    if not path_data.is_absolute():
        path_data = (path_config.parent / path_data).resolve()
    
    dir_gpkg_out = path_data.parent
    print(f"Reading data from: {path_data}")
    
# BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in hfatlas test dataset
    logging.info("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_parquet(path_data)
    
    # NEW FIX: Parse stringified tuple columns back to base names
    parsed_cols = []
    for col in df_all_data.columns:
        if isinstance(col, str) and col.startswith("("):
            try:
                # Extract the first element of the tuple string (the base name)
                parsed_cols.append(ast.literal_eval(col)[0])
            except (ValueError, SyntaxError):
                parsed_cols.append(col)
        else:
            parsed_cols.append(col)
    df_all_data.columns = parsed_cols
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    ds = pem.proc_col_schema(df_all_data, col_schema_df, dir_save)
    print("COMPLETED PROCESSING prep_regn_test_agg.py")
    logging.shutdown() # Remember to add this at the end of each script so that log files are separated by the script run
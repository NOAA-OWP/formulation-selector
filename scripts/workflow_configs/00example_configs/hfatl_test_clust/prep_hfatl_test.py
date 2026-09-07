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
import geopandas as gpd

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
    df_all_data = pd.read_parquet(path_data)


    
    # Extract the gpkg path from your loaded config
    path_hf_gpkg = col_schema_df['path_hf_gpkg'].loc[0].format(home_dir=str(Path.home()))
    hf_divides_layer = col_schema_df['hf_divides_layer'].loc[0]
    
    logging.info(f"Scanning hydrofabric GPKG for HUC01 locations: {path_hf_gpkg}")
    
    # NOTE: Replace 'huc2' with the exact column name in your .gpkg that specifies the HUC
    # We use pyogrio's native 'where' clause so we don't have to load the entire CONUS into RAM
    gdf_huc01 = gpd.read_file(
        path_hf_gpkg, 
        layer=hf_divides_layer, 
        engine="pyogrio", 
        columns=['divide_id', 'vpuid'], # Only load the columns we need
        where="vpuid = '01'"            # SQL-style filter applied during read
    )
    
    huc01_ids = gdf_huc01['divide_id'].unique()
    logging.info(f"Found {len(huc01_ids)} locations in HUC01. Subsetting dataset...")

    # Filter the dataset to ONLY include HUC01 locations
    df_all_data = df_all_data[df_all_data['divide_id'].isin(huc01_ids)]
    # ----------------------------------
 
    # END CUSTOMIZED DATASET MUNGING

    # ------ Extract metric data and write to file
    ds = pem.proc_col_schema(df_all_data, col_schema_df, dir_save)
    print("COMPLETED PROCESSING prep_hfatl_test.py")
    logging.shutdown() # Remember to add this at the end of each script so that log files are separated by the script run
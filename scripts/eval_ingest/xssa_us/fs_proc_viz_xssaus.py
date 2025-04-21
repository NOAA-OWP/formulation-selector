import argparse
import yaml
import pandas as pd
from pathlib import Path
import fs_algo.fs_algo_train_eval as fsate
import ast
import numpy as np
import geopandas as gpd
from shapely import wkt
"""Post-prediction script that plots map of xSSA process sensitivity predictions
Created for the HUC08 predictions
Refer to xssaus_proc_rafts_all.sh for a description of the key steps to reach this point.
fs_pred_algo.py must run first for this to work


Usage:
python fs_proc_viz_xssaus.py "~/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml"

Changelog/Contributions
2025-04-07 Originally created, GL
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the prediction config file')
    parser.add_argument('path_pred_config', type=str, help='Path to the YAML configuration file specific for prediction')
    args = parser.parse_args()

    home_dir = Path.home()
    path_pred_config = Path(args.path_pred_config) # path_pred_config=Path(f"{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml")

    with open(path_pred_config, 'r') as file:
        pred_cfg = yaml.safe_load(file)

    response_vars = pred_cfg['algo_response_vars']

    #%%  READ CONTENTS FROM THE ATTRIBUTE CONFIG
    path_attr_config = fsate.build_cfig_path(path_pred_config,pred_cfg.get('name_attr_config',None))
    # path_algo_config = fsate.build_cfig_path(path_pred_config,pred_cfg.get('name_algo_config',None))

    
    attr_cfig = fsate.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()

    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets') # Identify datasets of interest

    #%%  Generate standardized output directories
    dirs_std_dict = fsate.fs_save_algo_dir_struct(dir_base)
    dir_out = dirs_std_dict.get('dir_out')
    dir_out_alg_base = dirs_std_dict.get('dir_out_alg_base')
    dir_out_anlys_base = dirs_std_dict.get('dir_out_anlys_base')
    dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')

    #%%  Generate standardized output directories
    dirs_std_dict = fsate.fs_save_algo_dir_struct(dir_base)
    dir_out = dirs_std_dict.get('dir_out')
    dir_out_alg_base = dirs_std_dict.get('dir_out_alg_base')
    dir_out_anlys_base = dirs_std_dict.get('dir_out_anlys_base')
    dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')
    dir_out_preds_base = dirs_std_dict.get('dir_out_preds_base')

    for ds in datasets:
        # Read in the geospatial data corresponding to training/prediction locations:
        path_fs_proc = fsate._std_fs_proc_ds_paths(dir_std_base, ds =ds, mtch_str='*.nc')
        path_gpkg = fsate._std_fs_proc_ds_companion_gpkg_path(path_fs_proc[0])
        gdf = gpd.read_file(path_gpkg)

        # Read in the predicted data
        dir_out_pred = Path(Path(dir_out_preds_base),Path(ds))
        paths_pred = [x for x in list(dir_out_pred.rglob('*.parquet'))]
        for resp_var in response_vars:
            paths_resp = [x for x in paths_pred if resp_var in str(x)]
            for path_resp in paths_resp:
                df_resp = pd.read_parquet(path_resp) # The predicticted results dataframe
                # Match location with predicted results
                gdf_all = pd.merge(left=df_resp,right=gdf,left_on='featureID', right_on = 'comid')
                gdf_all = gpd.GeoDataFrame(gdf_all, geometry = 'geometry')

                # Generate map of predicted sensitivity values
                fsate.plot_map_pred_wrap(test_gdf=gdf_all,dir_out_viz_base=dir_out_viz_base, ds=ds,
                      metr=resp_var,algo_str=df_resp['algo'].iloc[0],
                      split_type='HUC08',
                      colname_data='prediction')

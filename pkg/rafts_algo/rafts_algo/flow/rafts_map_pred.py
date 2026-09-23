"""Workflow script to generate a map of predictions

Make sure to add in a unique string pertaining to the prediction of interest!
Example: 
    >>> python rafts_map_pred.py "/path/to/pred_config.yaml" "huc08"

# Changelog/contributions
    2025-08-21 added logging, GL
    2025-10-10 refactor to renamed rafts_algo modules, GL
"""
import argparse
import pandas as pd
from pathlib import Path
import rafts_algo.utils as raftsutil
import rafts_algo.plots as raftsplot
import geopandas as gpd
import logging
from logging.handlers import MemoryHandler
import rafts_prep.proc_eval_metrics as pem

# Predict values and evaluate predictions
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the prediction config file')
    parser.add_argument('path_pred_config', type=str, help='Path to the YAML configuration file specific for prediction.')
    parser.add_argument('analysis_str', type=str, default='') # The string to add on to end of each plotting file name
    # NOTE pred_config should contain the path for path_algo_config
    args = parser.parse_args()

    path_pred_config = Path(args.path_pred_config).expanduser() #Path(f'~/git/rafts/scripts/workflow_configs/legacy/xssangencerf/xssangencerf_pred_config.yaml') 
    # --- Commence logging before creating the log file
    memory_handler = MemoryHandler(capacity=30)
    # Get the root logger and add the memory handler to it
    # The root logger is the ancestor of all other loggers
    root_logger = logging.getLogger()
    root_logger.addHandler(memory_handler)
    root_logger.setLevel(logging.INFO) # Set the level to capture INFO messages
    logging.info(f"Running rafts_map_pred.py with \
                {path_pred_config.parent / path_pred_config.name} config file")
    # ---
    analysis_str = args.analysis_str

    pred_cfg = raftsutil.PredConfigParser(path_pred_config)
    pred_cfg._read_pred_config()
    
    #%% PREDICTION FILE'S COMIDS (IMPLICIT ASSUMPTION: Each dataset processes the same IDS)
    path_meta_pred = pred_cfg.pred_cfg_dict.get('path_meta')
    comid_pred_col = pred_cfg.pred_cfg_dict.get('pred_file_comid_colname')
    write_type = pred_cfg.pred_cfg_dict.get('write_type','parquet')
    ds_type = pred_cfg.pred_cfg_dict.get('ds_type')
    
    #%% prediction config
    resp_vars = pred_cfg.pred_cfg_dict.get('algo_response_vars')
    algos = pred_cfg.pred_cfg_dict.get('algo_type')

    path_meta_pred = pred_cfg.pred_cfg_dict.get('path_meta')
    #%%  READ CONTENTS FROM THE ATTRIBUTE CONFIG
    path_attr_config = raftsutil.build_cfig_path(pred_cfg.pred_cfg_dict.get('path_pred_config'),pred_cfg.pred_cfg_dict.get('name_attr_config',None))
    path_algo_config = raftsutil.build_cfig_path(pred_cfg.pred_cfg_dict.get('path_pred_config'),pred_cfg.pred_cfg_dict.get('name_algo_config'))

    # Initialize algo configuration class for extracting attributes
    algo_cfig = raftsutil.AlgoConfigParser(path_algo_config)
    algo_cfig._read_algo_config()

    # Extract variables from dictionary created by AlgoConfigParser
    algo_config = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["algo_config"]
    
    # Generate variable algo_config_og
    algo_config_og = algo_config.copy()

    metrics = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["metrics"]

    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()

    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets') # Identify datasets of interest

    dirs_std_dict = raftsutil.rafts_save_algo_dir_struct(dir_base)
    dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')
    dirs_std_dict.get('dir_out')
    dir_out = dirs_std_dict.get('dir_out')

    # ---------- Generate path to the log file & initialize logging -----------
    path_log = pem.std_path_log(dir_input=dir_base, 
                                path_config=path_pred_config,
                            script='rafts_map_pred')
    logging.basicConfig(level=logging.INFO, 
                        filename=path_log, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filemode='w', 
                        force = True) # overwrite log file when force=T

    # We need to find the new FileHandler that basicConfig created and set it
    # as the target for our MemoryHandler - aka we can now put previous logs
    # into the log file now that it has been created
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            memory_handler.setTarget(handler)
            memory_handler.flush()
            break  
    logging.info(f"Writing logs to {path_log}")
    root_logger.removeHandler(memory_handler) # Remove the pre-file logger
    # -------------------------------------------------------------------------
    for ds in datasets: 
        path_pred_locs = raftsutil.build_pred_locs_path(path_meta_template=path_meta_pred, dir_std_base=dir_std_base, 
                                                    ds=ds,ds_type=ds_type, write_type=write_type)
        comids_pred = raftsutil._read_pred_comid(path_pred_locs, comid_pred_col )
       
        vals = {'dir_std_base':dir_std_base,'ds':ds}
        dir_db_attrs = Path(str(dir_db_attrs).format(**vals))

        path_rafts_dat_resp =  raftsutil._std_rafts_prep_ds_paths(dir_std_base=dir_std_base,ds=ds,mtch_str='*.nc')
        path_gpkg_rafts_prep = raftsutil._std_rafts_prep_ds_companion_gpkg_path(path_rafts_dat_resp[0])
        gdf_all = gpd.read_file(path_gpkg_rafts_prep)
        gdf_all = gdf_all.rename(columns={'featureID':'featIDgpkg','featureSource':'featSrcegpkg'})

        for metr in resp_vars:
            for algo_str in pred_cfg.pred_cfg_dict.get('algo_type'):
                logging.info(f"Generating prediction map for dataset: {ds}\n"
                             f"Algorithm: {algo_str}\nResponse variable: {metr}")
                # Read in the prediction file for each response variable
                path_pred_in = raftsutil.std_pred_path(dir_out=dir_out,algo=algo_str,metric=metr,dataset_id=ds)
        
                df_pred = pd.read_parquet(path_pred_in)

                gdf_pred = gdf_all.merge(df_pred,how='right', right_on='featureID',left_on='comid')

                #gdf_pred = gdf_pred.dropna(subset='gage_id')
                #%% PREDICT                 
                raftsplot.plot_map_pred_wrap(gdf_pred,
                                dir_out_viz_base, ds,
                                    metr,algo_str,
                                    split_type=analysis_str,
                                    colname_data='prediction')
        logging.info(f"Completed prediction map generation for {path_pred_config}")
    logging.shutdown()
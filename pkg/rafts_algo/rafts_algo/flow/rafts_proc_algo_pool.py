"""Workflow script to train algorithms in parallel on catchment attribute data for predicting
    formulation metrics and/or hydrologic signatures. The rafts_proc_algo_viz.py should perform
    the exact same processing, but without parallelization or the ability to handle
    unsupervised clustering algorithms.

Example: 
    >>> python rafts_proc_algo_pool.py "/path/to/algo_config.yaml" 4 --validate

Changelog/Contributions
2026-05-08 refactor: Adapt rafts_proc_algo_viz to this parallelization structure, GL
"""
import argparse
import pandas as pd
from pathlib import Path
import rafts_algo.rafts_algo_train as raftsalgt
import rafts_algo.utils as raftsutil
import rafts_algo.plots as raftsplot
import numpy as np
import os
import matplotlib
matplotlib.use(os.environ.get("MPLBACKEND", "Agg"))
import matplotlib.pyplot as plt
import xarray as xr
import rafts_prep.proc_eval_metrics as pem
from logging.handlers import MemoryHandler
import logging
import sys
import gc

import copy
import gc
import itertools
import concurrent.futures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the algorithm config file')
    parser.add_argument('path_algo_config', type=str,
                        help='Path to the YAML configuration file specific for algorithm training')
    parser.add_argument('--validate', action='store_true', default=False, 
                        help='If present, enables schema validation for all input and output data. Defaults to False.')
    parser.add_argument('--chunk_size', default=4, type=int, help = "Set chunk_size to match your physical CPU cores (e.g., 4, 6, or 8)" )
    args = parser.parse_args()

    path_algo_config = Path(args.path_algo_config).expanduser() #Path(f'~/git/rafts/scripts/workflow_configs/legacy/xssa/xssa_algo_config.yaml').expanduser()
    config_dir = path_algo_config.parent
    chunk_size = args.chunk_size

    # --- Conditionally load schemas
    arg_val = args.validate 
    if arg_val:
        logging.info("Schema validation enabled. Using statically imported schemas from rafts_algo.schemas.")
            
    # --- Commence logging before creating the log file
    memory_handler = MemoryHandler(capacity=30)
    # Get the root logger and add the memory handler to it
    # The root logger is the ancestor of all other loggers
    root_logger = logging.getLogger()
    root_logger.addHandler(memory_handler)
    root_logger.setLevel(logging.INFO) # Set the level to capture INFO messages
    logging.info(f"Running rafts_proc_algo_pool.py with \
                {path_algo_config.parent / path_algo_config.name} config file")
    
    # ---
    logging.info("BEGINNING algorithm training, testing, & evaluation.")
    # Initialize algo configuration class for extracting attributes
    algo_cfig = raftsutil.AlgoConfigParser(path_algo_config)
    algo_cfig._read_algo_config()

    # Extract variables from dictionary created by AlgoConfigParser
    algo_config = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["algo_config"]

    # Generate variable algo_config_og
    algo_config_og = algo_config.copy()

    verbose = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["verbose"]
    test_size = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["test_size"]
    seed = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["seed"]
    read_type = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["read_type"] # Arg for how to read attribute data using comids in rafts_read_attr_comid(). May be 'all' or 'filename'.
    metrics = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["metrics"]
    make_plots = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["make_plots"]
    same_test_ids = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["same_test_ids"]
    path_attr_config = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["path_attr_config"]
    uncertainty_cfg = algo_cfig.algo_cfg_unc_dict["algo_unc_dict"]["uncertainty_cfg"]
    confidence_levels = algo_cfig.algo_cfg_unc_dict["algo_unc_dict"]["uncertainty_cfg"].get("confidence_levels")
    uncn_bnd_algo = algo_cfig.algo_cfg_unc_dict["algo_unc_dict"]["uncertainty_cfg"].get("uncn_bnd_algo",False)
    n_jobs_cfg = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"].get("n_jobs",1) # The total number of jobs for GridSearchCV. Preferably n_jobs = 1 when pooling.
    n_jobs = 1 if n_jobs_cfg is None else n_jobs_cfg

    #%% Attribute configuration
    # Initialize attribute configuration class for extracting attributes
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()

    # READ rafts_categories.yaml
    logging.info("Reading uncertainty bounds from rafts_categories.yaml...")
    rafts_catg_uncn = pem._conv_ls_dicts_df_long()

    # Grab the attributes of interest from the attribute config file,
    #  OR a .csv file if specified in the algo config file.
    name_attr_csv = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["name_attr_csv"]
    colname_attr_csv = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"]["colname_attr_csv"]
    attrs_sel = raftsutil.read_validated_attribute_selection(
        attr_cfig=attr_cfig,
        path_cfig=path_algo_config, 
        name_attr_csv=name_attr_csv,
        colname_attr_csv=colname_attr_csv,
        arg_val=arg_val
    )
    
    # Define directories/datasets from the attribute config file
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets') # Identify datasets of interest
    # Grab variables for building out the path to metadata (which contains comid-gage id mappings)
    ds_type = [x for x in attr_cfig.attr_config.get('file_io') if 'ds_type' in x][0]['ds_type']
    path_meta_fstr = [x for x in attr_cfig.attr_config.get('file_io') if 'path_meta' in x][0]['path_meta']


    # ---------- Generate path to the log file & initialize logging -----------
    path_log = pem.std_path_log(dir_input=dir_base, 
                                path_config=path_algo_config,
                            script='rafts_proc_algo_pool')
    print(f"Logging to {path_log}")
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
    #%%  Generate standardized output directories
    dirs_std_dict = raftsutil.rafts_save_algo_dir_struct(dir_base)
    dir_out = dirs_std_dict.get('dir_out')
    dir_out_alg_base = dirs_std_dict.get('dir_out_alg_base')
    dir_out_anlys_base = dirs_std_dict.get('dir_out_anlys_base')
    dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')
    # Define identifier schemas from attribute config:
    featureID = attr_cfig.attr_config.get('col_schema')[0].get('featureID')
    featureSource = attr_cfig.attr_config.get('col_schema')[0].get('featureSource')
    col_locid = 'featureID' # Enforcing the default column name expected throughout, 'featureID'. 
    if same_test_ids:
        # Must first establish which comids to use in the train-test split
        split_dict = raftsutil.split_train_test_comid_wrap(dir_std_base=dir_std_base, 
                    datasets=datasets, path_attr_config=path_attr_config,
                    id_col=col_locid, test_size=test_size,
                    random_state=seed)
        # If we use all the same comids for testing, we can make inter-comparisons
        test_ids = split_dict.get('sub_test_ids',None) #If this returns None, we use the test_size for all data
        dict_gdf_comids = split_dict.get('dict_gdf_comids',None) # retrieve the featureID - gage_id - geometry mapping
        # TODO PROBLEM: The raftsutil.rafts_read_attr_comid step can reduce the total number of comids for consideration if data are missing. Thus test_ids would need to be revised
    else:
        test_ids = None
        # retrieve the featureID - gage_id - geometry mapping

    # %% Looping over datasets
    for ds in datasets: 
        logging.info(f'PROCESSING {ds} dataset inside \n {dir_std_base}')

        dir_out_alg_ds = Path(dir_out_alg_base/Path(ds))
        dir_out_alg_ds.mkdir(exist_ok=True)

        vals = {'ds_type':ds_type,'write_type':'parquet', 'dir_std_base':dir_std_base,'ds':ds}
        path_meta = path_meta_fstr.format(**vals)
        dir_db_attrs = Path(str(dir_db_attrs).format(**vals))
        if Path(path_meta).exists() and False:
            # TODO allow secondary option where dat_resp and metrics read in from elsewhere. 
            # NOTE dataset metadata handling will also need to be considered
            # TODO first check for comids from metadata in the path_attr_config file
            if 'parquet' in Path(path_meta).suffix:
                df_meta = pd.read_parquet(path_meta)
            elif 'csv' in Path(path_meta).suffix:
                df_meta = pd.read_csv(path_meta)

            # Select the unique metadata:
            df_meta_uniq = df_meta[['featureSource',col_locid,'gage_id']].drop_duplicates().set_index('gage_id')
            # Read in the original data
            dat_resp = raftsutil._open_response_data_rafts(dir_std_base,ds)

            # Add the featureSource/featureID to the xr dataset's data vars
            for coord in ['featureSource', col_locid]:
                dat_resp[coord] = (('gage_id'), df_meta_uniq[coord])

            locids_resp = dat_resp[col_locid].data
            # TODO add gdf_comid based on lat/lon
        else:
            # Read in the standardized dataset generated by rafts_prep & grab comids/coords
            dict_resp_gdf = raftsutil.combine_resp_gdf_comid_wrap(dir_std_base=dir_std_base,
                            ds= ds, path_attr_config=path_attr_config)
            dat_resp = dict_resp_gdf['dat_resp'] # TODO why is dat_resp len 36 when it should be 44 with benchmarking FY25?
            gdf_comid = dict_resp_gdf['gdf_comid']

            # -- Subset to the gage ids only selected for training (just in case some predictions make it into dat_resp)
            # Drop duplicate multi-part geometries for the same gage
            gdf_comid = gdf_comid.drop_duplicates(subset=['gage_id']).copy()
            # Reorder gdf_comid so it perfectly matches dat_resp's coordinate order
            gdf_comid = gdf_comid.set_index('gage_id').loc[dat_resp['gage_id'].values].reset_index()
            # Safely assign to Xarray without size mismatches or scrambled indexing
            dat_resp["comid"] = (("gage_id"), gdf_comid["comid"].astype(str).values)
            
            # --- VALIDATION: GDF Comid ---
            raftsutil.validate_gdf_comid_schema(gdf_comid, arg_val=arg_val)
                    
            locids_resp = gdf_comid[col_locid].tolist()
            
        if not metrics:
            # The metrics approach. These are all xarray data variables of the response(s)
            metrics = dat_resp.attrs['respvar_mappings'].split('|')

        # --- VALIDATION: Response Data (dat_resp) ---
        raftsutil.validate_dat_resp_schema(dat_resp, metrics, col_locid, arg_val)        

        #%%  Read in predictor variable data (aka basin attributes) & NA removal
        # Read the predictor variable data (basin attributes) generated by proc.attr.hydfab
        # NOTE some gage_ids lost inside rafts_read_attr_comid. 
        try:
            df_attr = raftsutil.rafts_read_attr_comid(dir_db_attrs, locids_resp, attrs_sel = attrs_sel,
                                            _s3 = None,storage_options=None,read_type=read_type)
        except: # The read_type='filename' approach may not work
            df_attr = raftsutil.rafts_read_attr_comid(dir_db_attrs, locids_resp, attrs_sel = attrs_sel,
                                _s3 = None,storage_options=None,read_type='all')
        
        # --- VALIDATION: Attribute Data (df_attr) ---
        raftsutil.validate_input_attributes(df_attr,arg_val=arg_val)
            
        # Convert into wide format for model training
        try:
            df_attr_wide = df_attr.pivot(index=col_locid, columns = 'attribute', values = 'value')
        except:
            logging.error("Could not convert to long format. A common culprit is duplicated data, perhaps un-detected due to" \
            " 1) multiple sub-directories containing data inside dir_db_attrs" \
            " 2) data across all standard columns are the same but the dl_timestamp differs.")
            sys.exit(1)
        comids_df_attr_wide = df_attr_wide.index.values

        # Prepare attribute correlation matrix w/o NA values (writes to file)
        if df_attr_wide.isna().any().any(): # 
            df_attr_wide_dropna = df_attr_wide.dropna()
            locids_with_na_attrs = [x for x in df_attr_wide.index if x not in df_attr_wide_dropna.index]
            logging.warning(f"Dropping {df_attr_wide.shape[0] - df_attr_wide_dropna.shape[0]} total locations from analysis \
            for correlation/PCA assessment due to NA values, reducing dataset to {df_attr_wide_dropna.shape[0]} points")
            missing_locs_str = '\n'.join(locids_with_na_attrs)
            logging.warning(f"Locations with missing attribute data include:\n{missing_locs_str}")
            frac_na = (df_attr_wide.shape[0] - df_attr_wide_dropna.shape[0])/df_attr_wide.shape[0]
            if frac_na > 0.1:
                logging.warning(f"!!!!{np.round(frac_na*100,1)}%  of data are NA values and will be discarded before training/testing!!!!")
        else:
            df_attr_wide_dropna = df_attr_wide.copy()
        # ---------  UPDATE gdf and comid list after possible data removal ---------- #
        # Data removal comes from from raftsutil.rafts_read_attr_comid & df_attr_wide.dropna():
        remn_comids = list(df_attr_wide_dropna.index) # these are the comids that are left after checking what data are available
        # Revise gdf_comid
        gdf_comid = gdf_comid[gdf_comid[col_locid].isin(remn_comids)].reset_index()
        
        if isinstance(test_ids,pd.Series): # Revise test_ids
            # This resets the index of test_ids to correspond with gdf_comid
            test_ids = gdf_comid[col_locid][gdf_comid[col_locid].isin(test_ids)]

        #%% Characterize dataset correlations & principal components:
        fig_corr_mat = raftsplot.plot_corr_mat_save_wrap(df_X=df_attr_wide_dropna,
                                    title=f'Correlation matrix from {ds} dataset',
                                    dir_out_viz_base=dir_out_viz_base,
                                    ds=ds)
        plt.close(fig_corr_mat) # Explicitly close the exact figure
   
        plt.clf()
        # Attribute correlation results based on a correlation threshold (writes to file)
        df_corr_rslt = raftsplot.corr_thr_write_table_wrap(df_X=df_attr_wide_dropna,
                                                       dir_out_anlys_base=dir_out_anlys_base,
                                                       ds = ds,
                                                       corr_thr=0.8)
        
        # Principal component analysis
        pca_rslt = raftsplot.plot_pca_save_wrap(df_X=df_attr_wide_dropna, 
                        dir_out_viz_base=dir_out_viz_base,
                        ds = ds, 
                        std_scale=True # Apply the StandardScaler.
                        )
        plt.close(pca_rslt)
        plt.close('all')
        gc.collect()
        # %% Train, test, and evaluate
        task_type = algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"].get("task_type", "regression")
        # Override metrics if clustering (we don't need real metrics)
        if task_type == 'clustering':
            metrics = ['cluster_labels']

        rslt_eval = dict()
        tasks = []
        # Prepare data for all metrics sequentially to avoid pickling complex xarray objs
        for metr in metrics:
            logging.info(f' - Preparing data for {metr}')
            # GET MIN/MAX BOUNDS FOR THE CURRENT METRIC
            min_lim = None
            max_lim = None
            metric_bounds = rafts_catg_uncn[rafts_catg_uncn['var'] == metr]            
            if not metric_bounds.empty:
                min_lim = metric_bounds['min_lim'].iloc[0]
                max_lim = metric_bounds['max_lim'].iloc[0]
                logging.warning(f"   Applying bounds for '{metr}': min={min_lim}, max={max_lim}")
            else:
                logging.warning(f"   No bounds found for '{metr}'. Predictions will not be clipped.")

            if len(algo_config) == 0:
                algo_config = algo_config_og.copy()

            if task_type == 'clustering':
                # Bypass dat_resp completely. Just use attributes!
                df_pred_resp = df_attr_wide_dropna.reset_index()
            else:
                
                # Subset response data to metric of interest & the comid
                df_metr_resp = pd.DataFrame({col_locid: dat_resp[col_locid],
                                            'featureSource': dat_resp['featureSource'],
                                            metr : dat_resp[metr].data})
                # Join attribute data and response data
                df_pred_resp = df_metr_resp.merge(df_attr_wide_dropna, left_on = col_locid, right_on = col_locid)

                if df_pred_resp.isna().any().any(): # Check for NA values and remove them if present to avoid errors during evaluation
                    tot_na_dfpred = df_pred_resp.shape[0] - df_pred_resp.dropna().shape[0]
                    pct_na_dfpred = tot_na_dfpred/df_pred_resp.shape[0]*100
                    logging.info(f"Removing {tot_na_dfpred} NA values, which is {pct_na_dfpred}% of total data")
                    df_pred_resp = df_pred_resp.dropna()
                    if pct_na_dfpred > 10:
                        logging.warning(f"!!!!More than 10% of data are NA values!!!!")

            # TODO may need to add additional distinguishing strings to dataset_id, e.g. in cases of probabilistic simulation
            # Package arguments
            args_dict = {
                'metr': metr, 'task_type' : task_type, 'df_pred_resp': df_pred_resp, 'algo_config': copy.deepcopy(algo_config),
                'attrs_sel': attrs_sel, 'uncertainty_cfg': uncertainty_cfg, 
                'dir_out_alg_ds': dir_out_alg_ds, 'ds': ds, 'test_size': test_size,
                'seed': seed, 'col_locid': col_locid, 'verbose': verbose,
                'confidence_levels': confidence_levels, 'uncn_bnd_algo': uncn_bnd_algo,
                'min_lim': min_lim, 'max_lim': max_lim, 'make_plots': make_plots,
                'save_all_clusters': algo_cfig.algo_cfg_unc_dict["algo_cfg_dict"].get('save_all_clusters', False),
                'dir_out_viz_base': dir_out_viz_base, 'dir_out_anlys_base': dir_out_anlys_base,
                'gdf_comid': gdf_comid,'test_ids': test_ids,'n_jobs':n_jobs,
            }
            tasks.append(args_dict)

            # 2. Process tasks in strict batches to protect RAM and Disk I/O
            
            logging.info(f"Dispatching {len(tasks)} metrics in batches of {chunk_size}...")
            
            for batch_num, task_batch in enumerate(itertools.batched(tasks, chunk_size)):
                logging.info(f"--- Starting Batch {batch_num + 1} ---")
                
                # Create a pool EXACTLY the size of the batch
                with concurrent.futures.ProcessPoolExecutor(max_workers=chunk_size) as executor:
                    results = executor.map(raftsalgt._process_single_metric, task_batch)
                    
                    # Collect the returned dataframes
                    for metr, eval_df in results:
                        if eval_df is not None:
                            rslt_eval[metr] = eval_df
                
                # 3. Explicit Garbage Collection between batches
                # This guarantees RAM drops back down to baseline before the next batch spins up
                logging.info(f"--- Batch {batch_num + 1} Complete. Cleaning up memory... ---")
                gc.collect()

            # Compile results and write to file
            if rslt_eval:
                rslt_eval_df = pd.concat(rslt_eval.values()).reset_index(drop=True)

                # --- VALIDATION and file writing: Result Eval DF ---
                raftsutil.write_validated_evaluation_output(
                    rslt_eval_df=rslt_eval_df, 
                    dir_out_alg_ds=dir_out_alg_ds, 
                    ds=ds, valid_metrics=metrics, arg_val=arg_val
                )    
                    
            dat_resp.close()
    #%% Cross-comparison across all datasets: determining where the best metric lives
    if same_test_ids and len(datasets)>1:
        logging.info("Cross-comparison across multiple datasets possible.\n"+
        f"Refer to custom script processing example inside scripts/analysis/rafts_proc_viz_best_ealstm.py")

    logging.info("FINISHED algorithm training, testing, & evaluation")
    logging.shutdown()

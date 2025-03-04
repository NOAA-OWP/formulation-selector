import argparse
import yaml
import pandas as pd
from pathlib import Path
import fs_algo.fs_algo_train_eval as fsate
import ast
import numpy as np
import geopandas as gpd
from shapely import wkt
import matplotlib.pyplot as plt
"""Workflow script to train algorithms on catchment attribute data for predicting
    formulation metrics and/or hydrologic signatures.

:raises ValueError: When the algorithm config file path does not exist
:note python fs_proc_algo.py "/path/to/algo_config.yaml"

"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the algorithm config file')
    parser.add_argument('path_algo_config', type=str, help='Path to the YAML configuration file specific for algorithm training')
    args = parser.parse_args()

    path_algo_config = Path(args.path_algo_config) #Path(f'~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_algo_config.yaml') 

    with open(path_algo_config, 'r') as file:
        algo_cfg = yaml.safe_load(file)
    
    # Ensure the string literal is converted to a tuple for `hidden_layer_sizes`
    algo_config = {k: algo_cfg['algorithms'][k] for k in algo_cfg['algorithms']}
    if algo_config['mlp'][0].get('hidden_layer_sizes',None): # purpose: evaluate string literal to a tuple
        algo_config['mlp'][0]['hidden_layer_sizes'] = ast.literal_eval(algo_config['mlp'][0]['hidden_layer_sizes'])
    algo_config_og = algo_config.copy()

    verbose = algo_cfg['verbose']
    test_size = algo_cfg['test_size']
    seed = algo_cfg['seed']
    read_type = algo_cfg.get('read_type','all') # Arg for how to read attribute data using comids in fs_read_attr_comid(). May be 'all' or 'filename'.
    metrics = algo_cfg.get('metrics',None)
    make_plots = algo_cfg.get('make_plots',False)
    same_test_ids = algo_cfg.get('same_test_ids',True)
    
    mapie_alpha = algo_cfg['MAPIE_alpha']    
    bagging_ci_params_list = algo_cfg['Bagging_uncertainty']
    bagging_ci_params = {}
    if isinstance(bagging_ci_params_list, list):
        for param_dict in bagging_ci_params_list:
            if isinstance(param_dict, dict):  # Ensure each item is a dictionary
                bagging_ci_params.update(param_dict)    

    #%% Attribute configuration
    name_attr_config = algo_cfg.get('name_attr_config', Path(path_algo_config).name.replace('algo','attr')) 
    path_attr_config = fsate.build_cfig_path(path_algo_config, name_attr_config)
    
    if not Path(path_attr_config).exists():
        raise ValueError(f"Ensure that 'name_attr_config' as defined inside {path_algo_config.name} \
                          \n is also in the same directory as the algo config file {path_algo_config.parent}" )
    print("BEGINNING algorithm training, testing, & evaluation.")

    # Initialize attribute configuration class for extracting attributes
    attr_cfig = fsate.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()



    # Grab the attributes of interest from the attribute config file,
    #  OR a .csv file if specified in the algo config file.
    name_attr_csv = algo_cfg.get('name_attr_csv')
    colname_attr_csv = algo_cfg.get('colname_attr_csv')
    attrs_sel = fsate._id_attrs_sel_wrap(attr_cfig=attr_cfig,
                    path_cfig=path_attr_config,
                    name_attr_csv = name_attr_csv,
                    colname_attr_csv = colname_attr_csv)
    
    # Define directories/datasets from the attribute config file
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets') # Identify datasets of interest

    #%%  Generate standardized output directories
    dirs_std_dict = fsate.fs_save_algo_dir_struct(dir_base)
    dir_out = dirs_std_dict.get('dir_out')
    dir_out_alg_base = dirs_std_dict.get('dir_out_alg_base')
    dir_out_anlys_base = dirs_std_dict.get('dir_out_anlys_base')
    dir_out_viz_base = dirs_std_dict.get('dir_out_viz_base')

    if same_test_ids:
        # Must first establish which comids to use in the train-test split
        split_dict = fsate.split_train_test_comid_wrap(dir_std_base=dir_std_base, 
                    datasets=datasets, attr_config=attr_cfig.attr_config,
                    comid_col='comid', test_size=test_size,
                    random_state=seed)
        # If we use all the same comids for testing, we can make inter-comparisons
        test_ids = split_dict.get('sub_test_ids',None) #If this returns None, we use the test_size for all data

        # TODO PROBLEM: The fsate.fs_read_attr_comid step can reduce the total number of comids for consideration if data are missing. Thus test_ids would need to be revised
    else:
        test_ids = None

    # %% Looping over datasets
    for ds in datasets: 
        print(f'PROCESSING {ds} dataset inside \n {dir_std_base}')

        dir_out_alg_ds = Path(dir_out_alg_base/Path(ds))
        dir_out_alg_ds.mkdir(exist_ok=True)

        # TODO allow secondary option where dat_resp and metrics read in from elsewhere
        # Read in the standardized dataset generated by fs_proc & grab comids/coords
        dict_resp_gdf = fsate.combine_resp_gdf_comid_wrap(dir_std_base=dir_std_base,
                          ds= ds, attr_config = attr_cfig.attr_config)
        dat_resp = dict_resp_gdf['dat_resp']
        gdf_comid = dict_resp_gdf['gdf_comid']

        comids_resp = gdf_comid['comid'].tolist()
        if not metrics:
            # The metrics approach. These are all xarray data variables of the response(s)
            metrics = dat_resp.attrs['metric_mappings'].split('|')
  
        #%%  Read in predictor variable data (aka basin attributes) & NA removal
        # Read the predictor variable data (basin attributes) generated by proc.attr.hydfab
        # NOTE some gage_ids lost inside fs_read_attr_comid. 
        df_attr = fsate.fs_read_attr_comid(dir_db_attrs, comids_resp, attrs_sel = attrs_sel,
                                        _s3 = None,storage_options=None,read_type=read_type)
        # Convert into wide format for model training
        df_attr_wide = df_attr.pivot(index='featureID', columns = 'attribute', values = 'value')
        comids_df_attr_wide = df_attr_wide.index.values

        # Prepare attribute correlation matrix w/o NA values (writes to file)
        if df_attr_wide.isna().any().any(): # 
            df_attr_wide_dropna = df_attr_wide.dropna()
            print(f"Dropping {df_attr_wide.shape[0] - df_attr_wide_dropna.shape[0]} total locations from analysis \
            for correlation/PCA assessment due to NA values, reducing dataset to {df_attr_wide_dropna.shape[0]} points")
            frac_na = (df_attr_wide.shape[0] - df_attr_wide_dropna.shape[0])/df_attr_wide.shape[0]
            if frac_na > 0.1:
                raise UserWarning(f"!!!!{np.round(frac_na*100,1)}%  of data are NA values and will be discarded before training/testing!!!!")
        else:
            df_attr_wide_dropna = df_attr_wide.copy()
        # ---------  UPDATE gdf and comid list after possible data removal ---------- #
        # Data removal comes from from fsate.fs_read_attr_comid & df_attr_wide.dropna():
        remn_comids = list(df_attr_wide_dropna.index) # these are the comids that are left after checking what data are available
        # Revise gdf_comid
        gdf_comid = gdf_comid[gdf_comid['comid'].isin(remn_comids)].reset_index()
        
        if isinstance(test_ids,pd.Series): # Revise test_ids
            # This resets the index of test_ids to correspond with gdf_comid
            test_ids = gdf_comid['comid'][gdf_comid['comid'].isin(test_ids)]

        #%% Characterize dataset correlations & principal components:
        fig_corr_mat = fsate.plot_corr_mat_save_wrap(df_X=df_attr_wide_dropna,
                                    title=f'Correlation matrix from {ds} dataset',
                                    dir_out_viz_base=dir_out_viz_base,
                                    ds=ds)
        plt.clf()
        # Attribute correlation results based on a correlation threshold (writes to file)
        df_corr_rslt = fsate.corr_thr_write_table_wrap(df_X=df_attr_wide_dropna,
                                                       dir_out_anlys_base=dir_out_anlys_base,
                                                       ds = ds,
                                                       corr_thr=0.8)
        

        # Principal component analysis
        pca_rslt = fsate.plot_pca_save_wrap(df_X=df_attr_wide_dropna, 
                        dir_out_viz_base=dir_out_viz_base,
                        ds = ds, 
                        std_scale=True # Apply the StandardScaler.
                        )
        plt.clf()
        # %% Train, test, and evaluate
        rslt_eval = dict()
        for metr in metrics:
            print(f' - Processing {metr}')
            if len(algo_config) == 0:
                algo_config = algo_config_og.copy()
            # Subset response data to metric of interest & the comid
            df_metr_resp = pd.DataFrame({'comid': dat_resp['comid'],
                                        metr : dat_resp[metr].data})
            # Join attribute data and response data
            df_pred_resp = df_metr_resp.merge(df_attr_wide_dropna, left_on = 'comid', right_on = 'featureID')
            if df_pred_resp.isna().any().any(): # Check for NA values and remove them if present to avoid errors during evaluation
                tot_na_dfpred = df_pred_resp.shape[0] - df_pred_resp.dropna().shape[0]
                pct_na_dfpred = tot_na_dfpred/df_pred_resp.shape[0]*100
                print(f"Removing {tot_na_dfpred} NA values, which is {pct_na_dfpred}% of total data")
                df_pred_resp = df_pred_resp.dropna()
                if pct_na_dfpred > 10:
                    raise UserWarning(f"!!!!More than 10% of data are NA values!!!!")

            # TODO may need to add additional distinguishing strings to dataset_id, e.g. in cases of probabilistic simulation

            # Instantiate the training, testing, and evaluation class
            train_eval = fsate.AlgoTrainEval(df=df_pred_resp,
                                        attrs=attrs_sel,
                                        algo_config=algo_config,
                                        dir_out_alg_ds=dir_out_alg_ds, dataset_id=ds,
                                        metr=metr,test_size=test_size, rs = seed,
                                        test_ids=test_ids,
                                        verbose=verbose,
                                        mapie_alpha=mapie_alpha,
                                        bagging_ci_params=bagging_ci_params)
            train_eval.train_eval() # Train, test, eval wrapper

            # Get the comids corresponding to the testing data/run QA checks
            if train_eval.X_test.shape[0] + train_eval.X_train.shape[0] == df_pred_resp.shape[0]:
                if all(train_eval.X_test.index == test_ids.index):
                    df_pred_resp_test = df_pred_resp.iloc[train_eval.X_test.index]
                    comids_test = df_pred_resp_test['comid'].values
                    if not all(comids_test == test_ids.values): 
                        raise ValueError("PROBLEM: the testing comids stored using AlgoTrainEval do not match the expected testing comids")
                else:
                    raise ValueError("Unexpected train/test split index corruption when using AlgoTrainEval.train_eval().")
            else:
                raise ValueError("Problem with expected dimensions. Consider how missing data may be handled with AlgoTrainEval.train_eval()")

            # Retrieve evaluation metrics dataframe & write to file
            rslt_eval[metr] = train_eval.eval_df
            path_eval_metr = fsate.std_eval_metrs_path(dir_out_viz_base, ds,metr)
            train_eval.eval_df.to_csv(path_eval_metr)

            #%% Random Forest Feature Importance
            y_test = train_eval.y_test
            df_X, y_all = train_eval.all_X_all_y()

            if make_plots:
                # See if random forest was trained in the AlgoTrainEval class object:
                rfr = fsate._extr_rf_algo(train_eval)
                if rfr: # Generate & save the feature importance plot
                    fsate.save_feat_imp_fig_wrap(rfr=rfr,
                            attrs=df_X.columns,
                            dir_out_viz_base=dir_out_viz_base,
                            ds=ds,metr=metr)

                
                # Create learning curves for each algorithm
                algo_plot_lc = fsate.AlgoEvalPlotLC(df_X,y_all)
                fsate.plot_learning_curve_save_wrap(algo_plot_lc,train_eval, 
                                dir_out_viz_base=dir_out_viz_base,
                                ds=ds,
                                cv = 5,n_jobs=-1,
                                train_sizes = np.linspace(0.1, 1.0, 10),
                                scoring = 'neg_mean_squared_error',
                                ylabel_scoring = "Mean Squared Error (MSE)",
                                training_uncn = False
                                )

            # %% Model testing results visualization
            # TODO extract y_pred for each model
            dict_test_gdf = dict()
            for algo_str in train_eval.algs_dict.keys():

                #%% Evaluation: learning curves
                y_pred = train_eval.preds_dict[algo_str]['y_pred']
                y_obs = train_eval.y_test.values
                if make_plots:
                    # Regression of testing holdout's prediction vs observation
                    fsate.plot_pred_vs_obs_wrap(y_pred, y_obs, dir_out_viz_base,
                            ds, metr, algo_str=algo_str,split_type=f'testing{test_size}')

                # PREPARE THE GDF TO ALIGN PREDICTION VALUES BY COMIDS/COORDS
                test_gdf = gdf_comid.loc[test_ids.index]#[gdf_comid['comid'].isin(comids_test)].copy()
                # Ensure test_gdf is ordered in the same order of comids as y_pred
                if all(test_gdf['comid'].values == comids_test):             
                    test_gdf['id'] = pd.Categorical(test_gdf['comid'], categories=np.unique(comids_test), ordered=True) 
                    # The comid can be used for sorting... see test_gdf.sort_values() below
                else:
                    raise ValueError("Unable to ensure test_gdf is ordered in the same order of comids as y_pred")
                test_gdf.loc[:,'performance'] = y_pred
                test_gdf.loc[:,'observed'] = y_obs
                test_gdf.loc[:,'dataset'] = ds
                test_gdf.loc[:,'metric'] = metr
                test_gdf.loc[:,'algo'] = algo_str
                if test_gdf.shape[0] != len(comids_test):
                    raise ValueError("Problem with dataset size")
                test_gdf = test_gdf.sort_values('id').reset_index(drop=True)
                dict_test_gdf[algo_str] = test_gdf.drop('id',axis=1)

                if make_plots:
                    fsate.plot_map_pred_wrap(test_gdf,
                                    dir_out_viz_base, ds,
                                        metr,algo_str,
                                        split_type='test',
                                        colname_data='performance')
            
            # Generate analysis path out:
            path_pred_obs = fsate.std_test_pred_obs_path(dir_out_anlys_base,ds, metr)
            # TODO why does test_gdf end up with a size larger than total comids? Should be the split test amount
            df_pred_obs_ds_metr = pd.concat(dict_test_gdf)
            df_pred_obs_ds_metr.to_csv(path_pred_obs)
            print(f"Wrote the prediction-observation-coordinates dataset to file\n{path_pred_obs}")
                
            del train_eval
        # Compile results and write to file
        rslt_eval_df = pd.concat(rslt_eval).reset_index(drop=True)
        rslt_eval_df['dataset'] = ds
        rslt_eval_df.to_parquet(Path(dir_out_alg_ds)/Path('algo_eval_'+ds+'.parquet'))
        print(f'... Wrote training and testing evaluation to file for {ds}')

        dat_resp.close()
    #%% Cross-comparison across all datasets: determining where the best metric lives
    if same_test_ids and len(datasets)>1:
        print("Cross-comparison across multiple datasets possible.\n"+
        f"Refer to custom script processing example inside scripts/analysis/fs_proc_viz_best_ealstm.py")

    print("FINISHED algorithm training, testing, & evaluation")


'''
@title: Produce data visualizations for RaFTS model performance outputs
@author: Lauren Bolotin <lauren.bolotin@noaa.gov>
@description: Reads in several config files, 
    visualizes results for the specified RaFTS algorithms and evaluation metrics, 
    and saves plots to .png's.
@usage: python fs_perf_viz.py "/full/path/to/viz_config.yaml"

Changelog/contributions
    2024-11-22 Originally created, LB
'''
import geopandas as gpd
import os
import pandas as pd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from sklearn.metrics import r2_score
from sklearn.metrics import root_mean_squared_error
import yaml
from pathlib import Path
import argparse
import fs_algo.fs_algo_train_eval as fsate
import xarray as xr
import urllib.request
import zipfile
import pkg_resources


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'process the data visualization config file')
    parser.add_argument('path_viz_config', type=str, help='Path to the YAML configuration file specific for data visualization')
    args = parser.parse_args()

    home_dir = Path.home()
    path_viz_config = Path(args.path_viz_config) #Path(f'{home_dir}/FSDS/formulation-selector/scripts/eval_ingest/xssa/xssa_viz_config.yaml') 

    with open(path_viz_config, 'r') as file:
        viz_cfg = yaml.safe_load(file)

    # Get features from the viz config file --------------------------
    algos = viz_cfg.get('algos')
    print('Visualizing data for the following RaFTS algorithms:')
    print(algos)
    print('')
    metrics = viz_cfg.get('metrics')
    print('And for the following evaluation metrics:')
    print(metrics)
    print('')

    plot_types = viz_cfg.get('plot_types')
    plot_types_dict = {k: v for d in plot_types for k, v in d.items()}
    true_keys = [key for key, value in plot_types_dict.items() if value is True]
    print('The following plots will be generated:')
    print(true_keys)
    print('')

    # Get features from the pred config file --------------------------
    path_pred_config = fsate.build_cfig_path(path_viz_config,viz_cfg.get('name_pred_config',None)) # currently, this gives the pred config path, not the attr config path
    pred_cfg = yaml.safe_load(open(path_pred_config, 'r'))
    path_attr_config = fsate.build_cfig_path(path_pred_config,pred_cfg.get('name_attr_config',None)) 
    ds_type = pred_cfg.get('ds_type')
    write_type = pred_cfg.get('write_type')

    # Get features from the attr config file --------------------------
    attr_cfg = fsate.AttrConfigAndVars(path_attr_config)
    attr_cfg._read_attr_config()
    datasets = attr_cfg.attrs_cfg_dict.get('datasets')
    dir_base = attr_cfg.attrs_cfg_dict.get('dir_base')  
    dir_std_base = attr_cfg.attrs_cfg_dict.get('dir_std_base')

    # Get features from the main config file --------------------------
    # NOTE: This assumes that the main config file is just called [same prefix as all other config files]_config.yaml
    # Build the path to the main config file by referencing the other config files we've already read in
    prefix_viz = str(path_viz_config.name).split('_')[0]
    prefix_attr = str(path_attr_config.name).split('_')[0]
    if (prefix_viz != prefix_attr):
        raise ValueError('All config files must be in the same directory and be\
                          identifiable using the same prefix as each other (e.g.\
                          [dataset]_config.yaml, [dataset]_pred_config.yaml, \
                         [dataset]_attr_config.yaml, etc.)')
    else:
        prefix = prefix_viz

    path_main_config = fsate.build_cfig_path(path_viz_config,f'{prefix_viz}_config.yaml')
    with open(path_main_config, 'r') as file:
        main_cfg = yaml.safe_load(file)

    # NOTE: This is something I'm not totally sure will function properly with multiple datasets
    formulation_id = list([x for x in main_cfg['formulation_metadata'] if 'formulation_id' in x][0].values())[0]
    save_type = list([x for x in main_cfg['file_io'] if 'save_type' in x][0].values())[0]
    if save_type.lower() == 'netcdf':
        save_type_obs = 'nc'
        engine = 'netcdf4'
    else:
        save_type_obs = 'zarr'
        engine = 'zarr'

    # Access the location metadata for prediction sites
    path_meta_pred = pred_cfg.get('path_meta')

    # Location for accessing existing outputs and saving plots
    dir_out = fsate.fs_save_algo_dir_struct(dir_base).get('dir_out')
    dir_out_viz_base = Path(dir_out/Path("data_visualizations"))

    # Enforce style
    style_path = pkg_resources.resource_filename('fs_algo', 'RaFTS_theme.mplstyle')
    plt.style.use(style_path)

    # Loop through all datasets
    for ds in datasets:
        path_meta_pred = f'{path_meta_pred}'.format(ds = ds, dir_std_base = dir_std_base, ds_type = ds_type, write_type = write_type)
        meta_pred = pd.read_parquet(path_meta_pred)

        # Loop through all algorithms
        for algo in algos:
            # Loop through all metrics
            for metric in metrics:
                # Pull the predictions
                path_pred = fsate.std_pred_path(dir_out,algo=algo,metric=metric,dataset_id=ds)
                pred = pd.read_parquet(path_pred)
                data = pd.merge(meta_pred, pred, how = 'inner', on = 'comid')
                Path(f'{dir_out}/data_visualizations').mkdir(parents=True, exist_ok=True)
                # If you want to export the merged data for any reason: 
                # data.to_csv(f'{dir_out}/data_visualizations/{ds}_{algo}_{metric}_data.csv')

                # Does the user want a scatter plot comparing the observed module performance and the predicted module performance by RaFTS?
                if 'pred_map' in true_keys:
                    states = fsate.gen_conus_basemap(f'{dir_out}/data_visualizations/')

                    # Plot performance on map
                    lat = data['Y']
                    lon = data['X']
                    geometry = [Point(xy) for xy in zip(lon,lat)]
                    geo_df = gpd.GeoDataFrame(geometry = geometry)
                    geo_df['performance'] = data['prediction'].values
                    geo_df.crs = ("EPSG:4326")

                    fsate.plot_map_pred(geo_df=geo_df, states=states, 
                                        title=f'RaFTS Predicted Performance Map: {ds}', 
                                        metr=metric, colname_data='performance')

                    # Save the plot as a .png file
                    output_path = fsate.std_map_pred_path(dir_out_viz_base=dir_out_viz_base,
                                                          ds=ds, metr=metric, algo_str=algo,
                                                          split_type='prediction')
                    plt.savefig(output_path, dpi=300, bbox_inches='tight')
                    plt.clf()
                    plt.close()
                    
                    
                if 'obs_vs_sim_scatter' in true_keys:
                    # Scatter plot of observed vs. predicted module performance
                    # Remove 'USGS-' from ids so it can be merged with the actual performance data
                    data['identifier'] = data['identifier'].str.replace(r'\D', '', regex=True)
                    data['identifier'] = data['identifier'].str.strip() # remove leading and trailing spaces

                    # Read in the observed performance data
                    path_obs_perf = f'{dir_std_base}/{ds}/{ds}_{formulation_id}.{save_type_obs}'
                    obs = xr.open_dataset(path_obs_perf, engine=engine)
                    # NOTE: Below is one option, but it assumes there is only one possible .nc or .zarr file to read in (it only reads the first one it finds with that file extension)
                    # obs = fsate._open_response_data_fs(dir_std_base=dir_std_base, ds=ds)
                    obs = obs.to_dataframe()

                    # Standardize column names
                    obs.reset_index(inplace=True)
                    obs = obs.rename(columns={"gage_id": "identifier"})

                    # Subset columns
                    data = data[['identifier', 'comid', 'X', 'Y', 'prediction', 'metric', 'dataset']]
                    data = data[data['metric'] == metric]
                    data.columns = data.columns.str.lower()
                    obs = obs[['identifier', metric]]

                    # Merge the observed and predicted data
                    data = pd.merge(data, obs, how = 'inner', on = 'identifier')

                    # Plot the observed vs. predicted module performance
                    fsate.plot_pred_vs_obs_regr(y_pred=data['prediction'], y_obs=data[metric], 
                                                ds = ds, metr=metric)

                    # Save the plot as a .png file
                    output_path = fsate.std_regr_pred_obs_path(dir_out_viz_base=dir_out_viz_base,
                                                               ds=ds, metr=metric, algo_str=algo,
                                                            split_type='prediction')
                    plt.savefig(output_path, dpi=300, bbox_inches='tight')
                    plt.clf()
                    plt.close()
                

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process the YAML config file.')
    parser.add_argument('path_config', type=str, help='Path to the YAML configuration file')
    args = parser.parse_args()
    # The path to the configuration
    path_config = Path(args.path_config).expanduser() # path_config = Path('~/git/rafts/scripts/workflow_configs/00example_configs/nexus_test/nex_test_agg_prep_config.yaml').expanduser()

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
    dir_gpkg_out = Path(path_data).parent
    print(path_data)

    
    # BEGIN CUSTOMIZED DATASET MUNGING
    # ---- Read in hfatlas test dataset
    logging.info("Custom code: Reading/formatting non-standardized input datasets")
    df_all_data = pd.read_parquet(path_data)#,engine="pyarrow")
    # # df_all_data[col_schema_df['gage_id']] = df_all_data.index.astype(str)
    # # TODO standardize the dataset here

    # # Read the hydrofabric divides used for the july 2026 calibrations and pick one for a quick-and-dirty assessment

    # dir_hydfab_calib = Path("~/noaa/hydrofabric/hf22_apr26cal/selected_subsets_edited_geom/sites_new_ngsh_edited_geom").expanduser()
    # # From NOAA gdrive RegionalizationCollab/calibration/benchmark_hydrofabric/selected_subsets_edited_geom/
    # # [sites_new_ngsh_edited_geom.zip](https://drive.google.com/file/d/1Sh0lI2O8qXAmdJ8X2G8bvFu5z976kdcx/view?usp=drive_link)
    # data_list = []
    # gdrafts_to_concat = []
    # for gpkg_path in dir_hydfab_calib.glob("*.gpkg"):
    #     usgs_id = gpkg_path.name.replace(".gpkg","").replace("gage_","")

    #     gdf = gpd.read_file(gpkg_path, layer = 'divides', engine = "pyogrio")
    #     # Get the divide_id closest to median areasqkm
    #     median_val = gdf['areasqkm'].median()
    #     idx_closest = (gdf['areasqkm'] - median_val).abs().idxmin()
    #     closest_row = gdf.loc[[idx_closest]]
    #     div_id_midsized = closest_row['divide_id'].values[0]
    #     data_list.append({
    #                     'usgs_id': usgs_id,
    #                     'divide_id': div_id_midsized
    #                     })
    #     closest_row['gage_id'] = usgs_id
    #     # Convert the polygon into a Point geometry so hfatlas_to_rafts_prep.py can extract X/Y coords
    #     closest_row['geometry'] = closest_row.geometry.centroid
    #     gdrafts_to_concat.append(closest_row)

    # if gdrafts_to_concat:
    #     logging.info("Building consolidated GeoPackage for gages...")
    #     combined_gdf = pd.concat(gdrafts_to_concat, ignore_index=True)
    #     # Ensure it remains a proper GeoDataFrame with the original CRS
    #     combined_gdf = gpd.GeoDataFrame(combined_gdf, geometry='geometry', crs=gdf.crs)
        
    #     path_combined_gpkg = Path(dir_gpkg_out) / "hf22_regn_apr26_gages.gpkg"
    #     combined_gdf.to_file(path_combined_gpkg, layer='gages', driver='GPKG')
    #     logging.info(f"Saved combined gage geometries to {path_combined_gpkg} with layer 'gages'")
    #     print(f"Saved hf aggregated to gage station at: {path_combined_gpkg}")

    # # The map of a divide_id to a gage_id
    # sngl_div_gdf = pd.DataFrame(data_list)

    # df_cmbo_id = df_all_data.merge(sngl_div_gdf,left_on='site_id',right_on='usgs_id')
    
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
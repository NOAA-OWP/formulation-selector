"""Workflow script to format hfATLAS attributes into RaFTS-compatible attributes.

Intended to run after the initial prep script that generates the response variable .nc file.

Preferred script for preparing attribute data when the data have been organized to the desired resolution (i.e. pre-aggregated).

This script is designed for preparing training attribute data at the dataset's pre-defined native featureID level,
aka at the resolution of location identifiers in the input attribute dataset. These location identifiers correspond 
1:1 with the known response variables. It assumes that every modeled location in the dataset corresponds directly 
to a single featureID (i.e., a 1:1 relationship).

In cases where divides need to be aggregated to a larger scale, rafts_agg_hfatl_basin.py should be run instead.

Example: 
    >>> uv run python hfatlas_to_rafts_prep.py --path_prep_config "~/git/rafts/scripts/workflow_configs/00example_configs/hfatl_test/hfatl_prep_config.yaml" --name_attr_config "hfatl_attr_config.yaml"

Changelog/Contributions
2026-04-28 Originally created to map hfATLAS divides to VPU and format for RaFTS.Developed by SS with the help of AI.

# TODO should gdf_hf['gage_id'] always be the same as divide_id??  We may want this to differ when performing basin-based assessments (e.g. HUC level, not divide level as currently used)
"""

import argparse
import ast
import logging
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
from collections import ChainMap
from logging.handlers import MemoryHandler
import geopandas as gpd
from shapely.geometry import Point
import os

# Import RaFTS functions
from rafts_prep.proc_eval_metrics import read_schm_ls_of_dict, std_path_log

import rafts_algo.utils as raftsutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process hfATLAS attributes & hydrofabric for RaFTS.")
    parser.add_argument("--path_prep_config", required=True, help="Path to the prep config YAML file (e.g., hfatl_prep_config.yaml)")
    parser.add_argument("--name_attr_config", help="Filename of the attribute config YAML file")
    parser.add_argument('--validate', action='store_true', default=False, 
                        help='If present, enables schema validation for all input and output data. Defaults to False.')
    args = parser.parse_args()

    if  args.validate:
        # Placeholder for future pandera integration if required for this script
        pass 

    memory_handler = MemoryHandler(capacity=30)
    root_logger = logging.getLogger()
    root_logger.addHandler(memory_handler)
    root_logger.setLevel(logging.INFO)
    
    path_prep_config = Path(args.path_prep_config).expanduser()
    if not path_prep_config.exists():
        raise ValueError(f"Prep config file not found at {path_prep_config}")
    logging.info(f"Running hfatlas_to_rafts_prep.py with {path_prep_config.name} config file")

    # # --- Execute workflow
    # process_hfatlas_to_rafts(path_prep_config, args.validate, memory_handler, root_logger)

    # PARSE THE ATTRIBUTE CONFIG
    path_attr_config = raftsutil.build_cfig_path(path_known_config = path_prep_config, path_or_name_cfig = args.name_attr_config)
    attr_cfig = raftsutil.AttrConfigAndVars(path_attr_config)
    attr_cfig._read_attr_config()
    home_dir =  raftsutil._define_home_dir(attr_cfig.attr_config)
    # Define directories/datasets from the attribute config file
    dir_db_attrs = attr_cfig.attrs_cfg_dict.get('dir_db_attrs')
    dir_std_base = attr_cfig.attrs_cfg_dict.get('dir_std_base')
    dir_base = attr_cfig.attrs_cfg_dict.get('dir_base')
    datasets = attr_cfig.attrs_cfg_dict.get('datasets') # Identify datasets of interest
    # Grab variables for building out the path to metadata (which contains comid-gage id mappings)
    ds_type = [x for x in attr_cfig.attr_config.get('file_io') if 'ds_type' in x][0]['ds_type']
    path_meta_fstr = [x for x in attr_cfig.attr_config.get('file_io') if 'path_meta' in x][0]['path_meta']
    # The hfatlas attribute column names of interest:
    attrs_sel = attr_cfig.attrs_cfg_dict.get("attrs_sel")
    # Determine the identifier column, or assume it's 'divide_id'
    attr_select_list = attr_cfig.attr_config.get('attr_select', [])
    map_id_col = next(
        (x.get('hfatl_id_col') for x in attr_select_list if isinstance(x, dict) and 'hfatl_id_col' in x), 
        "divide_id"
    )

    # TODO add path_hfatl to attr_config parser
    
    paths_raw = [
        x.get('paths_hfatl') 
        for x in attr_cfig.attr_config.get('attr_select', []) 
        if x.get('paths_hfatl') is not None
    ]
    paths_hfatl = []
    if paths_raw and isinstance(paths_raw[0], list):
        for p in paths_raw[0]:
            # Handle both {home_dir} string formatting and standard '~/' expansion
            formatted_path = str(p).format(home_dir=home_dir)
            resolved_path = Path(formatted_path).expanduser()
            
            if resolved_path.exists():
                paths_hfatl.append(resolved_path)
            else:
                logging.warning(f"hfATLAS path defined in config does not exist and will be skipped: {resolved_path}")
                
    if not paths_hfatl:
        logging.error("No valid paths provided or found for hfATLAS data (paths_hfatl).")
        sys.exit(1)


    # --- 
    # Loop over each dataset. Realistically this will only be one, but keeping the definition of ds for consistency across RaFTS workflow scripts
    for ds in datasets: 
        logging.info(f'PROCESSING {ds} dataset inside \n {dir_std_base}')

        # 1. Parse the prep config YAML into a DataFrame
        logging.info(f"Loading configuration from {path_prep_config}")
        config_df = read_schm_ls_of_dict(path_prep_config)
        raw_config = config_df.iloc[0].dropna().to_dict()
        # Inject the dataset name into the dictionary for f-string resolution
        fio = {k: raftsutil.resolve_fstrings(v, raw_config) for k, v in raw_config.items()}

        # 2. Extract specific variables of interest
        path_hf_gpkg = Path(fio.get("path_hf_gpkg"))
        
        # featureID & featureSource:
        featureSource = fio.get('featureSource', 'hf_id')
        gage_id = fio.get('gage_id') # This pertains to the response variable dataset??

        # Hydrofabric cols, location id cols, & data source
        hf_layer = fio.get("hf_fp_layer", "flowpaths") # In hf v2.2, the flowpath layer that maps divide_ids & VPUs
        hf_id_col = fio.get("hf_fp_id_col", "id") # Flowpath layer's id column
        #map_id_col = fio.get("map_id_col", "divide_id") # TODO should this differ from fio.get('gage_id')? A: probably. 
        map_id_type = fio.get("map_id_type", "hf_id")
        vpu_id_col = fio.get("vpu_id_col", "vpuid") # Column name for vpu id in the hydrofabric f"{hf_layer}"
        vpu_mapped = fio.get('vpu_mapped', False) # Should output data be organized by vpu? vpu_mapped = True

        # Define path of the response variable dataset
        path_rafts_dat_resp =  raftsutil._std_rafts_prep_ds_paths(dir_std_base=dir_std_base,ds=ds,mtch_str='*.nc')
        if len(path_rafts_dat_resp) > 1:
            error_str = f"The following directory contains too many .nc files: {path_rafts_dat_resp}"
            logging.error(error_str)
            raise ValueError(error_str)
        
        # Define path of the standardized .gpkg file write of combined attributes & geometry (alternative to metadata parquet)
        # TODO should we also consider prediction locations here?
        path_gpkg_rafts_prep = raftsutil._std_rafts_prep_ds_companion_gpkg_path(path_rafts_dat_resp[0])

        # 2. Setup File Logging and transfer MemoryHandler logs
        path_log = std_path_log(dir_input=dir_base, path_config=path_prep_config, script='rafts_hfatlas_to_rafts')
        
        file_handler = logging.FileHandler(path_log, mode='w')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(file_handler)
        
        # Flush memory handler to the newly created file/stream handlers, then remove it
        memory_handler.setTarget(file_handler)
        memory_handler.flush()
        root_logger.removeHandler(memory_handler)
        
        logging.info(f"Writing logs to {path_log}")
        logging.info("Starting hfATLAS to RaFTS conversion.")

        # 3. Ingest Data
        paths_str = "\n    ".join(str(p) for p in paths_hfatl)
        logging.info(f"Loading hfATLAS predictors from \n{paths_str}")
        
        # Check if the aggregated attributes are defined in the config file and have been created via rafts_agg_hfatl_basin.py
        path_hf_gpkg_basins = raw_config.get('path_hf_basins_gpkg', None)
        if path_hf_gpkg_basins:
            dir_db_attrs_agg_save = raftsutil.std_dir_ds_agg(dir_db_attrs, ds)
            out_path = raftsutil.std_path_agg_ds(dir_db_attrs_agg_save=dir_db_attrs_agg_save, ds = ds)
            if Path(out_path).exists():
                logging.info(f"Aggregated attributes file found for {ds} at {out_path}. Loading this file instead of performing hfATLAS to RaFTS conversion.")
                df_hfatlas_agg = pd.read_parquet(out_path)
                # Re-defining dataset source & id col for training dataset prep
                paths_hfatl = [out_path]
                #map_id_col = gage_id
        try: # Run attribute read & clean wrapper function
            df_hfatlas = raftsutil.read_hfatlas_wrap_dask(paths_hfatl, attrs_sel, 
                                map_id_col)
        except: # The gage_id could work instead - this work for the case of path_hf_gpkg_basins from rafts_agg_hfatl_basin.py
            df_hfatlas = raftsutil.read_hfatlas_wrap_dask(paths_hfatl, attrs_sel, 
                                                    gage_id)                         

        # Read in the hydrofabric flowpath w/ vpuid and standardize cols
        gdf_hf = raftsutil.generate_algo_points_gpkg_wrap(div_ids = df_hfatlas[map_id_col], 
                                                path_hf_gpkg=path_hf_gpkg,
                                                path_gpkg_rafts_prep=path_gpkg_rafts_prep, # Only for writing to file
                                                hf_layer=hf_layer,
                                                map_id_col=map_id_col,
                                                featureSource=featureSource,
                                                vpu_id_col=vpu_id_col,# epsg = 4326
                                                )
        # Combine location identifiers with geometry, write to file spread out among different vpu_ids if vpu_mapped==True
        df_save = raftsutil.hfatl_hf_cmbo_wrap(df_hfatlas=df_hfatlas, gdf_hf=gdf_hf, 
                            ds=ds, dir_db_attrs=dir_db_attrs, featureSource=featureSource, map_id_col=map_id_col,
                            vpu_id_col=vpu_id_col, vpu_mapped=vpu_mapped,
                            data_source = fio.get('data_source','hfATLAS'))
      
        # Generate the attribute column name mapper to keep track of pint units that get 
        # stripped throughout algo training & prediction
        raw_columns = pd.read_parquet(paths_hfatl).columns
        mapper_df = raftsutil.create_hfatlas_unit_mapper(raw_columns=raw_columns)
        raftsutil.save_hfatlas_unit_mapper(mapper_df=mapper_df, dir_std_base = dir_std_base, ds=ds)
     
        # logging.info(f"Saved placeholder metadata for {len(unique_features)} locations to {path_meta}")
        logging.info("Successfully finished processing and writing all attribute files.")

    

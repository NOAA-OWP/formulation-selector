"""
prep_nexus_test.py

A custom RaFTS preparation script designed to transition a modeling workflow from 
basin-scale (e.g., divide_id or gage_id) to point-scale (nexus) evaluation.
"""

import argparse
import pandas as pd
import geopandas as gpd
from pathlib import Path
import logging
import xarray as xr
import re

import rafts_algo.utils as raftsutil
import rafts_prep.proc_eval_metrics as pem

def prep_nexus_data(path_prep_config: Path):
    logging.info(f"Parsing configuration: {path_prep_config.name}")
    
    # 1. Parse Config using RaFTS rafts_prep utilities
    config_df = pem.read_schm_ls_of_dict(path_prep_config)
    raw_config = config_df.iloc[0].dropna().to_dict()
    
    # Resolve f-strings across the entirely flattened configuration
    fio = {k: raftsutil.resolve_fstrings(v, raw_config) for k, v in raw_config.items()}
    
    # Extract schema mappings natively from the flattened dict
    orig_id_col = fio.get('gage_id', 'site_id')
    metrics_str = fio.get('respvar_cols', '')
    metrics = metrics_str.split('|')
    gpkg_filename_pattern = fio.get('gpkg_filename_pattern')
    
    # 2. Read Raw Response Data
    raw_data_path = Path(fio['path_data'])
    logging.info(f"Loading raw response variables from {raw_data_path.name}")
    if raw_data_path.suffix == '.parquet':
        df_raw = pd.read_parquet(raw_data_path)
    else:
        df_raw = pd.read_csv(raw_data_path)
        
    # 3. Read Flowpaths to Route the Network
    path_hf_gpkg = Path(fio['path_hf_gpkg'])
    
    hf_fp_layer = fio.get('hf_fp_layer', 'flowpaths')
    map_divide_id_col = fio.get('map_divide_id_col', 'divide_id')
    fp_id_col = fio.get('fp_id_col', 'flowpath_id')
    fp_toid_col = fio.get('fp_toid_col', 'flowpath_toid')
    
    logging.info(f"Reading '{hf_fp_layer}' layer from {path_hf_gpkg.name}...")
    
    # --- DIRECTORY SCANNING CAPABILITY & FILENAME PATTERN EXTRACTION ---
    fp_gdfs = []
    if path_hf_gpkg.is_dir():
        for gpkg_file in path_hf_gpkg.glob("*.gpkg"):
            try:
                gdf = gpd.read_file(gpkg_file, layer=hf_fp_layer, columns=[map_divide_id_col, fp_id_col, fp_toid_col], engine='pyogrio')
                
                # Extract gage_id from the filename if a pattern is provided
                if gpkg_filename_pattern:
                    match = re.search(gpkg_filename_pattern, gpkg_file.name)
                    if match:
                        gdf[orig_id_col] = match.group(1)
                    else:
                        logging.warning(f"Filename pattern '{gpkg_filename_pattern}' did not match '{gpkg_file.name}'")
                        
                fp_gdfs.append(gdf)
            except Exception as e:
                logging.debug(f"Skipped {gpkg_file.name}: {e}")
                
    elif path_hf_gpkg.is_file():
        try:
            gdf = gpd.read_file(path_hf_gpkg, layer=hf_fp_layer, columns=[map_divide_id_col, fp_id_col, fp_toid_col], engine='pyogrio')
            
            # Extract gage_id from the single file if a pattern is provided
            if gpkg_filename_pattern:
                match = re.search(gpkg_filename_pattern, path_hf_gpkg.name)
                if match:
                    gdf[orig_id_col] = match.group(1)
                else:
                    logging.warning(f"Filename pattern '{gpkg_filename_pattern}' did not match '{path_hf_gpkg.name}'")
                    
            fp_gdfs.append(gdf)
        except Exception as e:
            logging.error(f"Failed to read flowpaths. Ensure columns {map_divide_id_col}, {fp_id_col}, {fp_toid_col} exist in the {hf_fp_layer} layer! Error: {e}")
            return
    else:
        logging.error(f"Hydrofabric path is neither a file nor directory: {path_hf_gpkg}")
        return
        
    if not fp_gdfs:
        logging.error("No valid flowpaths could be loaded from the provided GPKG path.")
        return
        
    gdf_fp = pd.concat(fp_gdfs, ignore_index=True)
    
    # 4. Map Basin/Divide IDs to Terminal Nexus IDs
    logging.info("Routing network to identify downstream nexus IDs...")
    nexus_mapping = []
    unique_ids = df_raw[orig_id_col].unique()
    
    filter_col = orig_id_col if gpkg_filename_pattern else map_divide_id_col
    
    for loc_id in unique_ids:
        # Isolate the flowpath(s) associated with this specific basin/divide location
        fp_subset = gdf_fp[gdf_fp[filter_col] == loc_id]
        
        if fp_subset.empty:
            logging.warning(f"No flowpaths found for {loc_id}. Dropping from dataset.")
            continue
            
        # The terminal flowpath is the one whose 'toid' does not connect to another flowpath within the same basin subset.
        terminal_fp = fp_subset[~fp_subset[fp_toid_col].isin(fp_subset[fp_id_col])]
        
        if not terminal_fp.empty:
            nexus_id = terminal_fp[fp_toid_col].iloc[0]
            
            # --- USE THE NEW CUSTOM ID FUNCTION ---
            custom_id = pem.create_custom_nexus_id(loc_id, nexus_id)
            
            nexus_mapping.append({
                orig_id_col: loc_id, 
                'nexus_id': nexus_id,
                'custom_id': custom_id
            })
        else:
            logging.warning(f"Could not identify a terminal downstream nexus for {loc_id}.")
            
    if not nexus_mapping:
        logging.error("Failed to map any nexus IDs. Ensure your 'map_divide_id_col' or 'gpkg_filename_pattern' configuration matches the identifiers in your raw data.")
        return
        
    df_mapping = pd.DataFrame(nexus_mapping)
    
    # Merge the new custom_id back into the raw dataset
    df_mapped = df_raw.merge(df_mapping, on=orig_id_col, how='inner')
    
    # 5. Format to RaFTS standard using proc_col_schema
    logging.info("Formatting to RaFTS NetCDF standard...")
    
    # RaFTS expects the primary coordinate to be named 'gage_id', so we rename 'custom_id' to trick it
    df_mapped = df_mapped.rename(columns={'custom_id': 'gage_id'})
    df_final = df_mapped[['gage_id'] + metrics]
    
    # Aggregate any duplicates (if multiple upstream basins poured into the same custom ID)
    df_final = df_final.groupby('gage_id', as_index=False).mean()
    
    # Let RaFTS handle the xarray conversion, attribute mapping, and saving
    ds_xr = pem.proc_col_schema(
        df=df_final, 
        col_schema_df=config_df, 
        dir_save=fio['dir_save'], 
        check_nwis=False
    )
    
    formulation_id = pem.std_form_id(config_df)
    
    # 6. Reconstruct file paths for downstream operations
    dataset_name = fio['dataset_name']
    save_path_eval_metr = pem.path_std_eval_metr(fio['dir_save'], dataset_name, formulation_id)
    dir_std_base = save_path_eval_metr.parent.parent.parent.parent
    
    # Let RaFTS dynamically find the .nc file that proc_col_schema just created
    nc_paths = raftsutil._std_rafts_prep_ds_paths(dir_std_base=dir_std_base, ds=dataset_name, mtch_str='*.nc')
    if not nc_paths:
        logging.error("Could not locate the saved NetCDF file to build companion paths!")
        return
        
    out_nc_path = nc_paths[0]
    logging.info(f"Successfully located standard NetCDF at {out_nc_path}")
    
    logging.info(f"Successfully wrote custom-mapped response variables to {out_nc_path}")

    # 7. Generate the Companion loc.gpkg using the actual Nexus points
    logging.info("Generating companion custom location GeoPackage...")
    nexus_layer = 'nexus' 
    
    nexus_gdfs = []
    try:
        if path_hf_gpkg.is_dir():
            for gpkg_file in path_hf_gpkg.glob("*.gpkg"):
                try:
                    gdf = gpd.read_file(gpkg_file, layer=nexus_layer, engine='pyogrio')
                    
                    # 1. Extract the gage ID from the filename while the file context is still isolated
                    if gpkg_filename_pattern:
                        match = re.search(gpkg_filename_pattern, gpkg_file.name)
                        if match:
                            extracted_gage = match.group(1)
                            
                            # 2. Safely cast to string to avoid float mismatches
                            clean_nexus_series = gdf['nexus_id'].astype(str).str.replace(r'\.0$', '', regex=True)
                            
                            # 3. IMMEDIATELY tag the geometry with the unique combination ID
                            gdf['custom_id'] = pem.create_custom_nexus_id(extracted_gage, clean_nexus_series)
                            nexus_gdfs.append(gdf)
                            
                except Exception as e:
                    logging.debug(f"Skipped {gpkg_file.name} for nexus read: {e}")
                    
        elif path_hf_gpkg.is_file():
            gdf = gpd.read_file(path_hf_gpkg, layer=nexus_layer, engine='pyogrio')
            if gpkg_filename_pattern:
                match = re.search(gpkg_filename_pattern, path_hf_gpkg.name)
                if match:
                    extracted_gage = match.group(1)
                    clean_nexus_series = gdf['nexus_id'].astype(str).str.replace(r'\.0$', '', regex=True)
                    gdf['custom_id'] = pem.create_custom_nexus_id(extracted_gage, clean_nexus_series)
            nexus_gdfs.append(gdf)
            
        if not nexus_gdfs:
            raise ValueError(f"No nexus layers found in {path_hf_gpkg.name}")
            
        # Concatenate all isolated files. Because we tagged them with custom_id, 
        # identical raw nexus_ids from different files will not conflict.
        gdf_nexus_all = pd.concat(nexus_gdfs, ignore_index=True)
        
        # Filter natively using the unique custom IDs
        # (Remember that df_mapped['gage_id'] holds our custom IDs because we renamed it in step 5)
        if 'custom_id' in gdf_nexus_all.columns:
            gdf_nexus_sub = gdf_nexus_all[gdf_nexus_all['custom_id'].isin(df_mapped['gage_id'])]
            
            # 6. Format to RaFTS standard loc.gpkg schema (expects 'comid', 'gage_id', and 'featureID')
            gdf_loc = gdf_nexus_sub.rename(columns={'custom_id': 'comid'}) 
            gdf_loc['gage_id'] = gdf_loc['comid']
            gdf_loc['featureID'] = gdf_loc['comid']
            gdf_loc = gdf_loc.drop(columns=['nexus_toid'], errors='ignore')
            
        else:
            logging.error("Failed to generate 'custom_id' during geometry read. Ensure your filename pattern is correct.")
            return
            
        out_gpkg_path = raftsutil._std_rafts_prep_ds_companion_gpkg_path(out_nc_path)
        
        if gdf_loc.empty:
            logging.error("The resulting geometry dataframe is completely empty! Check identifier string matching.")
        else:
            # We enforce drop_duplicates here just in case the same gage_id/nexus_id combo appeared twice inside the same file
            gdf_loc = gdf_loc.drop_duplicates(subset=['comid'])

            if out_gpkg_path.exists():
                try:
                    out_gpkg_path.unlink()
                    logging.info(f"Deleted existing companion GPKG to prevent file bloat.")
                except Exception as e:
                    logging.warning(f"Could not delete existing GPKG (it may be open in another program): {e}")

            gdf_loc.to_file(out_gpkg_path, driver="GPKG", layer="outlet")
            logging.info(f"Wrote {len(gdf_loc)} companion nexus locations to {out_gpkg_path}")
        
    except Exception as e:
        logging.warning(f"Could not generate companion GPKG for nexus locations. Error: {e}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('path_prep_config', type=str, help='Path to the YAML prep configuration file.')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    prep_nexus_data(Path(args.path_prep_config).expanduser())
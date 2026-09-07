"""
map_nexus_divides.py

1. Reads the RaFTS prep configuration YAML.
2. Loops over gage-specific GPKG files in the configured directory and reads the flowpath layer.
3. Identifies the downstream-most nexus identifier (terminal toid) for each gage.
4. Maps the gage_id to the nexus_id and creates a custom identifier: {gage_id}__{nexus_id}.
5. Identifies all divides that drain to the nexus and writes the mapping to the dataset's standard directory.

Changelog / Contributions
 2026-08-11 Created using Gemini3.1Pro prompts, GL

"""

import argparse
import pandas as pd
import geopandas as gpd
from pathlib import Path
import re
import logging

import rafts_algo.utils as raftsutil
import rafts_prep.proc_eval_metrics as pem

# Set up standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def identify_terminal_nexus(gdf_fp: gpd.GeoDataFrame, fp_id_col: str, fp_toid_col: str) -> str:
    """
    Identifies the downstream-most nexus identifier from a flowpaths GeoDataFrame.
    The terminal flowpath is the one whose 'toid' does not connect to another flowpath 'id' 
    within the same basin network.
    
    :param gdf_fp: GeoDataFrame of the flowpaths layer.
    :param fp_id_col: Column name representing the flowpath ID.
    :param fp_toid_col: Column name representing the downstream connection ID.
    :return: The terminal nexus ID (string), or None if not found.
    """
    # Find the row(s) where the 'toid' is not present in the 'id' column of this subset
    terminal_fp = gdf_fp[~gdf_fp[fp_toid_col].isin(gdf_fp[fp_id_col])]
    
    if not terminal_fp.empty:
        # The toid of the terminal flowpath is the terminal nexus of the basin
        return str(terminal_fp[fp_toid_col].iloc[0])
    else:
        return None

def generate_nexus_mapping(path_prep_config: Path):
    """
    Parses the configuration, extracts the terminal nexus for each GPKG, 
    and writes the mapping to the dataset's standard output directory.
    """
    logging.info(f"Parsing configuration: {path_prep_config.name}")
    
    # 1. Parse Config using RaFTS rafts_prep utilities
    config_df = pem.read_schm_ls_of_dict(path_prep_config)
    raw_config = config_df.iloc[0].dropna().to_dict()
    
    # Resolve f-strings across the flattened configuration
    fio = {k: raftsutil.resolve_fstrings(v, raw_config) for k, v in raw_config.items()}
    
    # Extract variables from configuration
    dir_gpkgs = Path(fio.get('path_hf_basins_gpkg'))
    filename_pattern = fio.get('gpkg_filename_pattern', r"USGS-(.*)-ngen")
    fp_layer = fio.get('hf_fp_layer', 'flowpaths')
    fp_id_col = fio.get('hf_fp_id_col', 'flowpath_id')
    fp_toid_col = fio.get('fp_toid_col', 'flowpath_toid') # fallback if not in config
    divide_id_col = fio.get('map_divide_id_col', 'divide_id')
    
    dataset_name = fio.get('dataset_name')
    formulation_id = pem.std_form_id(config_df)
    save_path_eval_metr = pem.path_std_eval_metr(fio['dir_save'], fio['dataset_name'], formulation_id)
    dir_std_base = save_path_eval_metr.parent.parent.parent.parent

    # Set up output path inside the standard dataset directory (alongside the .nc file)
    out_dir = dir_std_base / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv_path = out_dir / f"{dataset_name}_nexus_divide_mapping.csv"
    
    mapping_records = []
    
    if not dir_gpkgs.is_dir():
        logging.error(f"The provided GPKG directory does not exist: {dir_gpkgs}")
        return

    logging.info(f"Scanning directory {dir_gpkgs} for GPKG files...")
    
    # 2) Loop over each gage-specific gpkg file
    for gpkg_file in dir_gpkgs.glob("*.gpkg"):
        
        # Extract the gage_id from the filename
        match = re.search(filename_pattern, gpkg_file.name)
        if match:
            gage_id = match.group(1)
        else:
            # Fallback to the raw filename without extension if regex fails
            gage_id = gpkg_file.stem
            logging.debug(f"Regex failed for {gpkg_file.name}, using '{gage_id}' as gage_id.")
            
        try:
            # Read in the flowpath layer (only the required columns for speed)
            gdf_fp = gpd.read_file(
                gpkg_file, 
                layer=fp_layer, 
                columns=[fp_id_col, fp_toid_col, divide_id_col], 
                engine='pyogrio'
            )
            
            if gdf_fp.empty:
                logging.warning(f"Flowpaths layer is empty in {gpkg_file.name}. Skipping.")
                continue
                
            # 3) Identify the downstream-most nexus identifier
            nexus_id = identify_terminal_nexus(gdf_fp, fp_id_col, fp_toid_col)
            
            if not nexus_id:
                logging.warning(f"Could not identify a terminal downstream nexus for {gpkg_file.name}. Skipping.")
                continue
                
            # 4) Map gage to nexus and create the combination ID
            custom_id = f"{gage_id}__{nexus_id}"
            
            # 5) Identify all divides that drain to this nexus
            # Because this is a gage-specific GPKG, all flowpaths (and their divides) 
            # within this file represent the upstream contributing area for the terminal nexus.
            divide_ids = gdf_fp[divide_id_col].dropna().unique()
            
            # Append the 1:Many relationships to our records
            for div_id in divide_ids:
                mapping_records.append({
                    'gage_id': gage_id,
                    'nexus_id': nexus_id,
                    'custom_id': custom_id,
                    'divide_id': str(div_id)
                })
                
        except Exception as e:
            logging.error(f"Failed to process {gpkg_file.name}: {e}")
            
    # Write the compiled mappings to file
    if mapping_records:
        df_mapping = pd.DataFrame(mapping_records)
        df_mapping.to_csv(out_csv_path, index=False)
        
        logging.info(f"Successfully wrote {len(df_mapping)} divide-to-nexus mappings to {out_csv_path}")
        logging.info(f"Total unique nexuses mapped: {df_mapping['nexus_id'].nunique()}")
    else:
        logging.error("No valid mappings were found. No file was written.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map gage-specific GPKGs to their terminal nexus and upstream divides.")
    parser.add_argument("path_prep_config", type=str, help="Path to the YAML prep configuration file.")
    
    args = parser.parse_args()
    generate_nexus_mapping(Path(args.path_prep_config).expanduser())
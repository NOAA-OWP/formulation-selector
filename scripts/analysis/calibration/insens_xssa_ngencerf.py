"""
Script to identify the insensitive processes corresponding to the ngenCERF locations 
Originally conceptualized inside rafts/scripts/anlaysis/calibration/visualize_process_sens_dists.R
Changelog/contributions
    2026-06-03 GeminiPro3.1 auto-converted/condensed from aforementioned R script, GL
"""

import os
import glob
import pandas as pd
import geopandas as gpd

# ============================================================================ #
# ----------------------------- CONFIGURATION -------------------------------- #
# ============================================================================ #

# Core parameters
THRESHOLD_SENS = 0.015
OUTPUT_FILEPATH = f"~/noaa/regionalization/data/analyses/insensitivities/ngencerf2025_thr{THRESHOLD_SENS}.csv"

# Input directories and files
DIR_DAT = "~/noaa/regionalization/data/output/algorithm_predictions/xSSA_proc_sens_wt_loc_sel_ngencerf" # Generated in 2025-May. The config files inside scripts/workflow_configs need to be reworked to recreate this dataset
PATH_GPKG = "~/noaa/regionalization/data/input/user_data_std/xSSA_proc_sens_wt_loc_sel_ngencerf2025/xSSA_proc_sens_wt_loc_sel_Raven_blended_loc.gpkg"
DIR_CALIB_GAGES = "~/noaa/hydrofabric/hf22_apr26cal/selected_subsets_edited_geom/sites_new_ngsh_edited_geom"

# ============================================================================ #
# ------------------------------ PROCESSING ---------------------------------- #
# ============================================================================ #

def main():
    # 1. Ensure the output directory exists
    out_dir = os.path.dirname(os.path.expanduser(OUTPUT_FILEPATH))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # 2. Read and prepare the GeoPackage mapping data
    print("Loading GeoPackage...")
    gdf_gpkg = gpd.read_file(os.path.expanduser(PATH_GPKG), layer='outlet')
    
    # We drop the spatial geometry to save memory since we only need tabular mapping
    df_gpkg = pd.DataFrame(gdf_gpkg.drop(columns='geometry'))
    
    # Deduplicate on 'comid' to ensure a clean 1:1 join later
    df_gpkg_unique = df_gpkg.drop_duplicates(subset=['comid']).copy()

    # 3. Get Calibration Gage IDs dynamically from the directory
    calib_dir = os.path.expanduser(DIR_CALIB_GAGES)
    gage_ids_calib = []
    if os.path.exists(calib_dir):
        files = os.listdir(calib_dir)
        # Replicates R's gsub to clean the filenames into IDs
        gage_ids_calib = [f.replace('.gpkg', '').replace('gage_', '') for f in files]
    else:
        print(f"Warning: Calibration directory not found at {calib_dir}")

    # 4. Process all Parquet Prediction Files
    print(f"Processing parquet files in {DIR_DAT}...")
    search_pattern = os.path.join(os.path.expanduser(DIR_DAT), "*pred_rf*")
    parquet_files = glob.glob(search_pattern)

    all_calib_data = []

    for file_path in parquet_files:
        df = pd.read_parquet(file_path)

        # Map the 'featureID' in parquet to 'comid' in the GeoPackage
        df_merged = pd.merge(
            df,
            df_gpkg_unique[['comid', 'gage_id', 'name']],
            left_on='featureID',
            right_on='comid',
            how='left' # Left join ensures we don't drop predictions if mapping is missing
        )

        # Subset to only the locations used for calibration
        sub_calib = df_merged[df_merged['gage_id'].isin(gage_ids_calib)].copy()

        if not sub_calib.empty:
            all_calib_data.append(sub_calib)

    # 5. Combine, Filter, and Export
    if all_calib_data:
        dt_calib = pd.concat(all_calib_data, ignore_index=True)

        # Apply the configurable sensitivity threshold
        dt_insens = dt_calib[dt_calib['prediction'] < THRESHOLD_SENS].copy()

        # Isolate the required columns
        cols_to_keep = ['gage_id', 'name', 'metric', 'prediction']
        
        # Safety check: only keep columns that actually exist in the dataframe
        existing_cols = [c for c in cols_to_keep if c in dt_insens.columns]
        dt_insens = dt_insens[existing_cols]

        # Write to CSV
        output_path_clean = os.path.expanduser(OUTPUT_FILEPATH)
        dt_insens.to_csv(output_path_clean, index=False)
        
        print(f"Success! Processed {len(dt_insens)} insensitive records.")
        print(f"File saved to: {output_path_clean}")
        print(f"Total data points written: {dt_insens.shape[0]}")
    else:
        print("No matching calibration data found to process.")

if __name__ == "__main__":
    main()
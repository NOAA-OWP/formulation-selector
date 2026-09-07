#!/bin/bash

# RaFTS processing the regionalization testing dataset with hfATLAS data
# Instructions:
# Make this script executable using: chmod +x regn_casam_agg_proc.sh
# Run by calling in terminal: ./regn_casam_agg_proc.sh

# -----------------------------------------------------------------------------
# ERROR HANDLING
# -----------------------------------------------------------------------------
# -e: Exit immediately if a command exits with a non-zero status.
# -u: Treat unset variables as an error and exit immediately.
# -o pipefail: Ensure errors in piped commands are caught.
set -euo pipefail || { echo "..."; exit 1; }

# -----------------------------------------------------------------------------
# PATH DEFINITIONS
# -----------------------------------------------------------------------------
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/rafts"
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/00example_configs/xgb_adaboost_regn_casam_jul26"
#DIR_PRED="${DIR_REPO}/scripts/prediction/rfc_locs"
DIR_PREP="${DIR_REPO}/pkg/rafts_prep/rafts_prep/flow"
DIR_PY="${DIR_REPO}/pkg/rafts_algo/rafts_algo/flow"

echo "Running processing from $DIR_CONFIG"

# -----------------------------------------------------------------------------
# EXECUTION WORKFLOW
# -----------------------------------------------------------------------------

# 1. Prepare the initial dataset
echo "Starting execution of hfATLAS parameter regionalization scripts..."
echo "--> Preparing the initial dataset..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_CONFIG}/prep_regn_test_agg.py" "${DIR_CONFIG}/regn_casam_agg_prep_config.yaml" || {
    echo "ERROR: Dataset preparation failed. Exiting."
    exit 1
}

# 2. Run the hfATLAS standardized prep script
echo "--> Grabbing attributes..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/rafts_agg_hfatl_basin.py" \
    --path_prep_config "${DIR_CONFIG}/regn_casam_agg_prep_config.yaml" \
    --path_attr_config "${DIR_CONFIG}/regn_casam_attr_config.yaml" || {
    echo "ERROR: Attribute grabbing failed. Exiting."
    exit 1
}
echo "Attribute grabbing completed successfully!"

# 3. Train the algorithms 
echo "--> Training & testing algorithms..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_proc_algo_pool.py" "${DIR_CONFIG}/regn_casam_algo_config_uncn.yaml" --chunk_size 4 || {
    echo "ERROR: Algorithm training failed. Exiting."
    exit 1
}
echo "Algorithm training completed successfully!"

# 4. Perform the prediction
echo "--> Performing process predictions..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pred_algo.py" "${DIR_CONFIG}/regn_casam_pred_config_uncn.yaml" || {
    echo "ERROR: Process predictions failed. Exiting."
    exit 1
}
echo "Process predictions completed successfully!"

# 5. Map the predictions
echo "--> Plotting the process predictions on static map..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_map_pred_hfatl.py" "${DIR_CONFIG}/regn_casam_pred_config_uncn.yaml" || {
    echo "ERROR: Prediction mapping failed. Exiting."
    exit 1
}
echo "Completed prediction mapping!"


# 6. Write Parameters to Compiled GeoPackage
echo "--> Compiling regionalized parameters into master GPKG..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_regn_params_gpkg.py" "${DIR_CONFIG}/regn_casam_pred_config_uncn.yaml" || {
    echo "ERROR: GPKG compilation failed. Exiting."
    exit 1
}


# echo "========================================================================"
# echo "SUCCESS: Finished the hfATLAS regionalization predictions!"
# echo "========================================================================"
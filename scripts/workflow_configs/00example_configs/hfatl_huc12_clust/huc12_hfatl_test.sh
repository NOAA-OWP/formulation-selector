#!/bin/bash

# RaFTS processing the regionalization testing dataset with hfATLAS data
# Instructions:
# Make this script executable using: chmod +x huc12_hfatl_test.sh
# Run by calling in terminal: ./huc12_hfatl_test.sh

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
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/00example_configs/hfatl_huc12_clust"
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
uv run --project "${DIR_REPO}/pkg" python "${DIR_CONFIG}/prep_hfatl_clust.py" "${DIR_CONFIG}/hfatl_prep_config.yaml" || {
    echo "ERROR: Dataset preparation failed. Exiting."
    exit 1
}

# 2 Aggregate they hydrofabric based on the gage_id (CAMELS basins subset)
echo "--> Aggregating the hydrofabric attributes based on the gage_id (CAMELS basins subset)..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/rafts_agg_hfatl_basin.py" \
    --path_prep_config "${DIR_CONFIG}/hfatl_prep_config.yaml" \
    --path_attr_config "${DIR_CONFIG}/hfatl_attr_config.yaml" || {
    echo "ERROR: Hydrofabric aggregation failed. Exiting."
    exit 1
}
echo "Hydrofabric aggregation completed successfully!"

# 3. Train the algorithms 
echo "--> Training & testing algorithms..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_proc_algo_pool.py" "${DIR_CONFIG}/hfatl_algo_config.yaml" --chunk_size 4 || {
    echo "ERROR: Algorithm training failed. Exiting."
    exit 1
}
echo "Algorithm training completed successfully!"

# 4. Perform the prediction
echo "--> Performing predictions..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pred_algo.py" "${DIR_CONFIG}/hfatl_pred_config.yaml" || {
    echo "ERROR: Process predictions failed. Exiting."
    exit 1
}
echo "Predictions completed successfully!"

# 5. Pair the donor-receivers
echo "--> Performing donor-receiver pairing..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pair_donors.py" "${DIR_CONFIG}/hfatl_pred_config.yaml" || {
    echo "ERROR: Process predictions failed. Exiting."
    exit 1
}
echo "Process predictions completed successfully!"

# 6. Map the predictions
echo "--> Plotting the process predictions on static map..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_map_pred_hfatl.py" "${DIR_CONFIG}/hfatl_pred_config.yaml" || {
    echo "ERROR: Prediction mapping failed. Exiting."
    exit 1
}
echo "Completed prediction mapping!"

# echo "========================================================================"
# echo "SUCCESS: Finished the hfATLAS regionalization predictions!"
# echo "========================================================================"
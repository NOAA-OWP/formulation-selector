#!/bin/bash

# RaFTS overarching processing script for regionalization testing datasets with hfATLAS data
# Instructions:
# Make this script executable using: chmod +x regn_all_proc.sh
# Run by calling in terminal: ./regn_all_proc.sh

# -----------------------------------------------------------------------------
# ERROR HANDLING
# -----------------------------------------------------------------------------
# -e: Exit immediately if a command exits with a non-zero status.
# -u: Treat unset variables as an error and exit immediately.
# -o pipefail: Ensure errors in piped commands are caught.
set -euo pipefail || { echo "..."; exit 1; }

# -----------------------------------------------------------------------------
# UNIVERSAL PATH DEFINITIONS
# -----------------------------------------------------------------------------
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/rafts"
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/00example_configs/clustering_regn_casam_jul26"
DIR_PREP="${DIR_REPO}/pkg/rafts_prep/rafts_prep/flow"
DIR_PY="${DIR_REPO}/pkg/rafts_algo/rafts_algo/flow"

echo "Running processing from $DIR_CONFIG"

# -----------------------------------------------------------------------------
# EXECUTION WORKFLOW
# -----------------------------------------------------------------------------
# Define the unique prefixes for each model to iterate over
MODELS=("casam")

for MODEL in "${MODELS[@]}"; do
    echo "========================================================================"
    echo "Starting execution of hfATLAS parameter regionalization for: ${MODEL}"
    echo "========================================================================"

    # Define the yaml configurations for the current model in the loop
    PREP_CONF="regn_${MODEL}_agg_prep_config.yaml"
    ATTR_CONF="regn_${MODEL}_attr_config.yaml"
    ALGO_CONF="regn_${MODEL}_algo_config.yaml"
    PRED_CONF="regn_${MODEL}_pred_config_hf4.yaml"

    # 1. Prepare the initial dataset
    echo "--> Preparing the initial dataset..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_CONFIG}/prep_regn_test_agg.py" "${DIR_CONFIG}/${PREP_CONF}" || {
        echo "ERROR: Dataset preparation failed for ${MODEL}. Exiting."
        exit 1
    }

    # 2. Run the hfATLAS standardized prep script
    echo "--> Grabbing attributes..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/rafts_agg_hfatl_basin.py" \
        --path_prep_config "${DIR_CONFIG}/${PREP_CONF}" \
        --path_attr_config "${DIR_CONFIG}/${ATTR_CONF}" || {
        echo "ERROR: Attribute grabbing failed for ${MODEL}. Exiting."
        exit 1
    }

    # 3. Train the algorithms 
    echo "--> Training & testing algorithms..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_proc_algo_pool.py" "${DIR_CONFIG}/${ALGO_CONF}" --chunk_size 4 || {
        echo "ERROR: Algorithm training failed for ${MODEL}. Exiting."
        exit 1
    }

    # 4. Perform the prediction
    echo "--> Performing cluster predictions..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pred_algo.py" "${DIR_CONFIG}/${PRED_CONF}" || {
        echo "ERROR: Cluster predictions failed for ${MODEL}. Exiting."
        exit 1
    }

    # 5. Pair the donor-receivers
    echo "--> Performing donor-receiver pairing..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pair_donors.py" "${DIR_CONFIG}/${PRED_CONF}" || {
        echo "ERROR: Donor-receiver pairings failed for ${MODEL}. Exiting."
        exit 1
    }

    # 6. Map the predictions
    echo "--> Plotting the cluster predictions on static map..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_map_pred_hfatl.py" "${DIR_CONFIG}/${PRED_CONF}" || {
        echo "ERROR: Prediction mapping failed for ${MODEL}. Exiting."
        exit 1
    }

    # 7. Write Parameters to Compiled GeoPackage
    echo "--> Compiling regionalized parameters into master GPKG..."
    uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_regn_params_gpkg.py" "${DIR_CONFIG}/${PRED_CONF}" || {
        echo "ERROR: GPKG compilation failed for ${MODEL}. Exiting."
        exit 1
    }
done


echo "========================================================================"
echo "SUCCESS: Finished ALL hfATLAS regionalization predictions!"
echo "========================================================================"
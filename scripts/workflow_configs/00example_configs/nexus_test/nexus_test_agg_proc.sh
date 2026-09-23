# nexus_test_agg_proc.sh
#!/bin/bash

# RaFTS processing the regionalization testing dataset with hfATLAS data
set -euo pipefail || { echo "..."; exit 1; }

# -----------------------------------------------------------------------------
# PATH DEFINITIONS
# -----------------------------------------------------------------------------
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/rafts"
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/00example_configs/nexus_test"
DIR_PREP="${DIR_REPO}/pkg/rafts_prep/rafts_prep/flow"
DIR_PY="${DIR_REPO}/pkg/rafts_algo/rafts_algo/flow"

echo "Running processing from $DIR_CONFIG"

# -----------------------------------------------------------------------------
# EXECUTION WORKFLOW
# -----------------------------------------------------------------------------

# 1. Prepare the initial dataset & Custom Nexus GPKG
echo "Starting execution of hfATLAS parameter regionalization scripts..."
echo "--> Preparing the initial dataset..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_CONFIG}/prep_nexus_test.py" "${DIR_CONFIG}/nex_test_agg_prep_config.yaml" || {
    echo "ERROR: Dataset preparation failed. Exiting."
    exit 1
}

# 2. Build the Divide-to-Nexus Crosswalk (Training)
echo "--> Building spatial crosswalk mappings..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/map_nexus_divides.py" "${DIR_CONFIG}/nex_test_agg_prep_config.yaml" || {
    echo "ERROR: Nexus-Divide mapping failed. Exiting."
    exit 1
}

# 3. Run the Custom Nexus Attribute Aggregator (Training Mode)
echo "--> Grabbing and aggregating attributes by custom Nexus ID for training..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PREP}/rafts_agg_nexus_hfatl.py" \
    --path_attr_config "${DIR_CONFIG}/nex_test_attr_config.yaml" || {
    echo "ERROR: Training attribute grabbing failed. Exiting."
    exit 1
}

# 4. Train the algorithms 
echo "--> Training & testing algorithms..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_proc_algo_pool.py" "${DIR_CONFIG}/nex_test_algo_config_uncn.yaml" --chunk_size 4 || {
    echo "ERROR: Algorithm training failed. Exiting."
    exit 1
}

# 5. Perform the prediction
echo "--> Performing process predictions across v2.2..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_pred_algo.py" "${DIR_CONFIG}/nex_test_pred_config_hf22.yaml" || {
    echo "ERROR: Process predictions failed. Exiting."
    exit 1
}

# 6. Map the predictions (Optional, uncomment if static maps are desired)
echo "--> Plotting the process predictions on static map..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_map_pred_hfatl.py" "${DIR_CONFIG}/nex_test_pred_config_hf22.yaml" || {
    echo "ERROR: Prediction mapping failed. Exiting."
    exit 1
}

# 7. Write Parameters to Compiled GeoPackage
echo "--> Compiling regionalized parameters into master GPKG..."
uv run --project "${DIR_REPO}/pkg" python "${DIR_PY}/rafts_regn_params_gpkg.py" "${DIR_CONFIG}/nex_test_pred_config_hf22.yaml" || {
    echo "ERROR: GPKG compilation failed. Exiting."
    exit 1
}

echo "========================================================================"
echo "SUCCESS: Finished the hfATLAS regionalization predictions!"
echo "========================================================================"
# RaFTS processing the xssaus dataset, from data acquisition to 

# Instructions:
# Make this script executable using
# chmod +x xssaus_proc_rafts_all.sh
# Run by calling in terminal ./xssaus_proc_rafts_all.sh

#!/bin/bash
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/rafts/" # The system-specific path to the rafts repo
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/legacy/xssa_us/"
DIR_PRED="${DIR_REPO}/scripts/prediction/rfc_locs/"
DIR_PY="${DIR_REPO}/pkg/rafts_algo/rafts_algo/flow/"
DIR_R="${DIR_REPO}/pkg/proc.attr.hydfab/flow/"

echo "Running processing from $DIR_CONFIG"

# Prepare the initial dataset here (only needs to happen once)
"${DIR_CONFIG}prep_xssaus_metrics.py" "${DIR_CONFIG}xssaus_prep_config.yaml"

# Print a message to indicate the script is running
echo "Starting execution of xssa_us process sensitivity scripts..."

# Run the R script to grab attributes
echo "Grabbing attributes"
Rscript "${DIR_R}rafts_attrs_grab.R" "${DIR_CONFIG}xssaus_attr_config.yaml"
echo "Attribute grabbing completed!"

# Run attribute transformer
echo "Generating transformed attributes"
python3 "${DIR_PY}rafts_tfrm_attrs.py" "${DIR_CONFIG}xssaus_attrs_tform.yaml"
echo "Attribute transformations completed!"

# Train the algorithms
echo "Training & testing algorithms..."
python3 "${DIR_PY}rafts_proc_algo_viz.py" "${DIR_CONFIG}xssaus_attr_config.yaml"
echo "Algorithm training completed!"

# Print a message to indicate all scripts have finished executing
echo "Attribute grabbing, transformation, and algorithm training executed successfully!"

# 4.1 Identify which locations will be used for prediction, and generate the attributes (and metadata file for predictions)
echo "Retrieve prediction location attribute data and geometry data"
# CAUTION: The following Rscript has some custom dependencies in identifying which locations need predicting. Refer to script for details.
Rscript "${DIR_PRED}gen_pred_locs_xssaus_map.R" "${DIR_CONFIG}xssaus_pred_config.yaml"
echo "Acquired prediction location attribute data and geometry data"

# 4.2 Perform transformations on prediction locations
echo "Transforming prediction location attribute data"
python3 "${DIR_PY}rafts_tfrm_attrs.py"   "${DIR_CONFIG}xssaus_attrs_tform.yaml"
echo "Transformed prediction location attribute data"

# 4.3 Perform the prediction
echo "Performing process predictions"
python3 "${DIR_PY}rafts_pred_algo.py" "${DIR_CONFIG}xssaus_pred_config.yaml"

# 4.4 Map the predictions (static map)
echo "Plotting the process predictions on static map"
python3 "${DIR_CONFIG}rafts_proc_viz_xssaus.py" "${DIR_CONFIG}xssaus_pred_config.yaml"
echo "Completed prediction mapping"

echo "Finished the xSSA process sensitivity mapping predictions"
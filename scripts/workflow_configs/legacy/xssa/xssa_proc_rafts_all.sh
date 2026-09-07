# RaFTS processing the Mai et al, 2022 model metrics 
#  (denoted xssa in the dir structure/filenames)

# Instructions:
# 1. Must first modify all config files (and the dir paths in this file) to your needs!
# 2. Make this script executable using
# chmod +x xssa_proc_rafts_all.sh
# 3. Run by calling in terminal ./xssa_proc_rafts_all.sh

#!/bin/bash
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/rafts/" # The system-specific path to the rafts repo
DIR_CONFIG="${DIR_REPO}/scripts/workflow_configs/legacy/xssa/"
DIR_PRED="${DIR_REPO}/scripts/prediction/xssa_sub/"
DIR_PY="${DIR_REPO}/pkg/rafts_algo/rafts_algo/flow/"
DIR_R="${DIR_REPO}/pkg/proc.attr.hydfab/flow/"

echo "Running processing from $DIR_CONFIG"

# 1. Prepare the initial dataset here with a custom python script (only need to run this once and then it may be commented out)
python3 "${DIR_CONFIG}prep_xssa_metrics.py" "${DIR_CONFIG}xssa_prep_config.yaml"

# The following steps do not require user-input (beyond defining the config files)
# Print a message to indicate the script is running
echo "Starting execution of xssa process sensitivity scripts..."

# 2. Run the R script to grab attributes
echo "Grabbing attributes"
Rscript "${DIR_R}rafts_attrs_grab.R" "${DIR_CONFIG}xssa_attr_config.yaml"
echo "Attribute grabbing completed!"

# 2.5 Run attribute transformer
echo "Generating transformed attributes"
python3 "${DIR_PY}rafts_tfrm_attrs.py" "${DIR_CONFIG}xssa_attrs_tform.yaml"
echo "Attribute transformations completed!"

# 3. Train the algorithms
echo "Training & testing algorithms..."
python3 "${DIR_PY}rafts_proc_algo_viz.py" "${DIR_CONFIG}xssa_algo_config.yaml"
echo "Algorithm training completed!"

# Print a message to indicate all scripts have finished executing
echo "Attribute grabbing, transformation, and algorithm training executed successfully!"

# 4.1 Identify which locations will be used for prediction, and generate the attributes (and metadata file for predictions)
echo "Retrieve prediction location attribute data and geometry data"
# CAUTION: The following Rscript has some custom dependencies in identifying which locations need predicting. Refer to script for details.
Rscript "${DIR_PRED}gen_pred_locs_xssa.R" "${DIR_CONFIG}xssa_pred_config.yaml"
echo "Acquired prediction location attribute data and geometry data"

# 4.2 Perform transformations on prediction locations
echo "Transforming prediction location attribute data"
python3 "${DIR_PY}rafts_tfrm_attrs.py"   "${DIR_CONFIG}xssa_attrs_tform.yaml"
echo "Transformed prediction location attribute data"

# 4.3 Perform the prediction & plotting
echo "Performing process predictions"
python3 "${DIR_PY}rafts_pred_algo.py" "${DIR_CONFIG}xssa_pred_config.yaml"

echo "RaFTS COMPLETED PROCESSING of xSSA performance metrics"
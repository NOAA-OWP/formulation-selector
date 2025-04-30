# RaFTS processing the xssaus dataset, from data acquisition to 

# Instructions:
# Make this script executable using
# chmod +x xssaus_proc_rafts_all.sh
# Run by calling in terminal ./xssaus_proc_rafts_all.sh

#!/bin/bash
echo "Using system home directory as basis for all paths: $HOME"
DIR_REPO="$HOME/git/formulation-selector/" # The system-specific path to the formulation-selector repo
DIR_CONFIG="${DIR_REPO}/scripts/eval_ingest/xssa_us/"
DIR_PRED="${DIR_REPO}/scripts/prediction/rfc_locs/"
DIR_PY="${DIR_REPO}/pkg/fs_algo/fs_algo/"
DIR_R="${DIR_REPO}/pkg/proc.attr.hydfab/flow/"

echo "Running processing from $DIR_CONFIG"

# 1. Prepare the initial dataset here with a custom python script (only need to run this once and then it may be commented out)
# "${DIR_CONFIG}prep_xssaus_metrics.py" "${DIR_CONFIG}xssaus_prep_config.yaml"

# The following steps do not require user-input (beyond defining the config files)
# Print a message to indicate the script is running
echo "Starting execution of xssa_us process sensitivity scripts..."

# 2. Run the R script to grab attributes
echo "Grabbing attributes"
Rscript "${DIR_R}fs_attrs_grab.R" "${DIR_CONFIG}xssaus_attr_config.yaml"
if [ $? -ne 0 ]; then
  echo "Attribute grabbing failed. Attempting next step."
else
    echo "Attribute grabbing completed!"
fi

# 2.5 Run attribute transformer
echo "Generating transformed attributes"
python3 "${DIR_PY}fs_tfrm_attrs.py" "${DIR_CONFIG}xssaus_attrs_tform.yaml"
if [ $? -ne 0 ]; then
  echo "Attribute transformation failed. Attempting next step."
else
    echo "Attribute transformations completed!"
fi

# 3. Train the algorithms
echo "Training & testing algorithms..."
python3 "${DIR_PY}fs_proc_algo_viz.py" "${DIR_CONFIG}xssaus_algo_config.yaml"
if [ $? -ne 0 ]; then
  echo "Algorithm training failed. Attempting next step."
else
    echo "Algorithm training completed!"
fi

# Print a message to indicate all scripts have finished executing
echo "Attribute grabbing, transformation, and algorithm training steps executed."

# 4.1 Identify which locations will be used for prediction, and generate the attributes (and metadata file for predictions)
echo "Retrieve prediction location attribute data and geometry data"
# CAUTION: The following Rscript has some custom dependencies in identifying which locations need predicting. Refer to script for details.
Rscript "${DIR_PRED}gen_pred_locs_xssaus_map.R" "${DIR_CONFIG}xssaus_pred_config.yaml"
if [ $? -ne 0 ]; then
  echo "Prediction location & attribute grabbing failed. Attempting next step."
else
    echo "Acquired prediction location attribute data and geometry data"
fi

# 4.2 Perform transformations on prediction locations
echo "Transforming prediction location attribute data"
python3 "${DIR_PY}fs_tfrm_attrs.py"   "${DIR_CONFIG}xssaus_attrs_tform.yaml"
if [ $? -ne 0 ]; then
  echo "Prediction attribute transformations failed. Attempting next step."
else
   echo "Transformed prediction location attribute data"
fi

# 4.3 Perform the prediction
echo "Performing process predictions"
python3 "${DIR_PY}fs_pred_algo.py" "${DIR_CONFIG}xssaus_pred_config.yaml"
if [ $? -ne 0 ]; then
  echo "Prediction step failed. Attempting next step."
else
    echo "Predictions completed. Attempting next step."
fi


# 4.4 Map the predictions (static map)
echo "Plotting the process predictions on static map"
python3 "${DIR_CONFIG}fs_proc_viz_xssaus.py" "${DIR_CONFIG}xssaus_pred_config.yaml"
if [ $? -ne 0 ]; then
  echo "Prediction mapping step failed."
else
    echo "Completed prediction mapping"
fi

echo "Finished the xSSA process sensitivity mapping predictions workflow"
# RaFTS Overview

The Regionalization and Formulation Testing & Selection (RaFTS) tool tests how hydrologically-relevant response variables may be predicted across space from hydrologic predictors using modular sci-kit learn supervised regressor and unsupervised clustering algorithms. Response variables may include formulation metrics (e.g. KGE), xSSA process sensitivities (Mai et al 2022), or parameter values.

# RaFTS Installation

The following installs the `rafts_prep` and `rafts_algo` packages:
```bash
cd pkg/
uv sync --all-groups
```



# RaFTS Workflow: hydrofabric and custom-generated predictors

This document describes the workflow for preparing, aggregating, and training (pooling) models within the RaFTS (Regionalization and Formulation Testing System) framework using the hydrofabric and corresponding predictors (e.g. hfATLAS). 
---

## I. Workflow Overview

The RaFTS hfATLAS workflow is executed in a specific sequence to process raw input datasets, aggregate spatial attributes & format them, train machine learning algorithms, and ultimately perform out-of-sample predictions using algorithms deemed acceptable for prediction by the user. A shell script contained in the same workflow directory as the corresponding config files is recommended for running all of these steps sequentially (e.g., `hfatl_test_proc_rafts_all.sh`).

Refer to scripts/workflow_configs/00example_configs/*/ and scripts/workflow_configs/legacy/*/ for many examples of different workflows. Note additional configurations/workflows may not be tracked in this repo, but stored in [NOAA gdrive](https://drive.google.com/drive/folders/1ghSVlE890S3LXir1-JhexDlNf1zT6T6h?usp=drive_link)

1. **Preparation**: Custom dataset munging is performed first to prepare the initial response variable dataset and write to file in a standardized NetCDF (`.nc`). Typically named `prep_*.py` inside the same directory as the corresponding config files (e.g. [scripts/workflow_configs/00example_configs/xgb_adaboost_regn_casam_jul26/prep_regn_test_agg.py](scripts/workflow_configs/00example_configs/xgb_adaboost_regn_casam_jul26/prep_regn_test_agg.py). The prep script should culminate into properly calling `rafts_prep.proc_eval_metrics.proc_col_schema()`


2. **Aggregation**: Hydrofabric-based watershed attributes are aggregated based on the gage_id representing the basins of interest. Both methods create the RaFTS-standard form of watershed attribute data, whose column names include `['featureID', 'featureSource',  'data_source', 'dl_timestamp', 'attribute', 'value']`.
 - `rafts_agg_hfatl_basin.py`: aggregates hydrofabric divides to a larger basin scale. Find it in [pkg/rafts_prep/rafts_prep/flow/rafts_agg_hfatl_basin.py](pkg/rafts_prep/rafts_prep/flow/rafts_agg_hfatl_basin.py)
 - `hfatlas_to_rafts_prep.py`: uses existing location identifiers (e.g. `divide_id`) and performs no aggregation. Find it in [pkg/rafts_prep/rafts_prep/flow/hfatlas_to_rafts_prep.py](pkg/rafts_prep/rafts_prep/flow/hfatlas_to_rafts_prep.py)
 - `map_nexus_divides.py`: Optional for **nexus**-oriented workflows (e.g. ensemble algorithm applications). Routes the hydrofabric flowpath network to identify the downstream-most terminal nexus for each gaged location subset and creates a crosswalk mapping every upstream divide to that specific nexus. Find it in [pkg/rafts_prep/rafts_prep/flow/map_nexus_divides.py](pkg/rafts_prep/rafts_prep/flow/map_nexus_divides.py)
 - `rafts_agg_nexus_hfatl.py`: Optional for **nexus**-oriented workflows. A "universal aggregator" that uses the crosswalk mappings from `map_nexus_divides.py` to perform area-weighted aggregations of raw divide-level hfATLAS attributes to the custom nexus point level. Intended for preparing training datasets. Note that prediction datasets are expected to already be prepared in the appropriate format using `hfATLAS` nexus-based processing. The same nexus-based `hfATLAS` workflow may also be used for the RaFTS training data, also preventing the need to run `rafts_agg_nexus_hfatl.py` entirely. Find it in [pkg/rafts_prep/rafts_prep/flow/rafts_agg_nexus_hfatl.py](pkg/rafts_prep/rafts_prep/flow/rafts_agg_nexus_hfatl.py)

### Understanding `rafts_agg_hfatl_basin.py` vs. `hfatlas_to_rafts_prep.py`

Both scripts prepare the watershed attribute data and the choice depends on whether the input data have been aggregated to the desired scale (i.e. basin size). Preferably, the input watershed attribute data have already been aggregated to same scale as the response variables. In that case, `hfatlas_to_rafts_prep.py` is the method.
These run after the initial custom prep script that generates the response variable `.nc` file. 


* **`hfatlas_to_rafts_prep.py`**:  This script formats hfATLAS attributes into RaFTS-compatible attributes. It is intended to run when the raw response variable and corresponding attribute data are already described at the native `featureID` level such as a USGS gaged basin and therefore need no additional aggregation. 


* **`rafts_agg_hfatl_basin.py`**: Not recommended unless attribute data have not been pre-processed to the desired basin scale. This script is used specifically in cases where hydrofabric divides need to be aggregated to a larger scale. It reads a hydrofabric GPKG, extracts the divide-to-gage mapping, loads the raw hfATLAS attributes, and aggregates them to the gage level. It outputs analysis-ready aggregated attributes. Note that aggregation is assumed to take the area-weighted average of attributes across divides, unless it is an area column in which case the sum is taken. Code modification will be required for exceptions. A simpler approach would be to use aggregation methods via the custom attribute pre-processing tool `hfATLAS`.


3. **Training & Testing**: Algorithms are trained and tested in parallel on the catchment attribute data to predict formulation metrics or hydrologic signatures. There are a few different algorithm training scripts contained inside [`pkg/rafts_algo/rafts_algo/flow/`](pkg/rafts_algo/rafts_algo/flow/):
 - `rafts_proc_algo_pool.py`: The computationally-efficient parallelized algorithm training script. Recommended, especially when using the current workflow, with pre-processed attribute data. See [rafts_proc_algo_pool.py](pkg/rafts_algo/rafts_algo/flow/rafts_proc_algo_pool.py).
 - `rafts_proc_algo_viz.py`: The legacy script which is kept in case historic workflow runs are desired (e.g. `/scripts/workflow_configs/legacy/xssa_us/`). See [rafts_proc_algo_viz.py](pkg/rafts_algo/rafts_algo/flow/rafts_proc_algo_viz.py).

Algorithm choices include supervised (i.e. random forest and MLP), and unsupervised (e.g. gower's distance, kmeans). **Develop separate workflows based on algorithm type - supervised or unsupervised.** In other words, build out separate processing workflows for supervised algorithms, and another workflow for unsupervised algorithms. Do not mix supervised and unsupervised algorithms together in the same workflow.

4. **Prediction**  Using trained algorithms to make predictions of response variables in out-of-sample locations. The resulting predictions and their associated uncertainties are plotted onto static spatial maps across the hydrofabric.

 - `rafts_pred_algo.py`: Generates the predictions and optionally calculates uncertainty bounds (e.g., MAPIE prediction intervals or ForestCI). See [rafts_pred_algo.py](pkg/rafts_algo/rafts_algo/flow/rafts_pred_algo.py).


5. **Mapping**: The resulting predictions and their associated uncertainties are plotted onto static spatial maps across the hydrofabric.


 - `rafts_map_pred_hfatl.py`: Generates static `.png` maps of the predicted values and uncertainty bounds joined dynamically to the hydrofabric geometries. See [rafts_map_pred_hfatl.py](pkg/rafts_algo/rafts_algo/flow/rafts_map_pred_hfatl.py).

6. **Donor-Receiver Pairing**: Only used for unsupervised clustering algorithms. 

- `rafts_pair_donors.py`: Pairs donor and receiver basins within the same cluster based on euclidean distance. See [rafts_pair_donors.py](pkg/rafts_algo/rafts_algo/flow/rafts_pair_donors.py).

Note: The attribute transformation workflow has been deprecated for the current processing workflows. It's recommended to perform desired transformations on the input attribute data beforehand. If attribute transformation is desired, updates will need to be made to the prediction step.

7. **Regionalized Parameter Integration with Hydrofabric**: This prepares the hydrofabric .gpkg to a standardized form of regionalized parameters accepted by nextgen. For regionalization purposes only.

 - `rafts_regn_params_gpkg.py`: Designed for unsupervised and supervised algorithms. Writes sqlite databases of regionalized parameters, writes selected parameters per formulation as new layers in a copy of the hydrofabric .gpkg. See [rafts_regn_params_gpkg.py](pkg/rafts_algo/rafts_algo/flow/rafts_regn_params_gpkg.py).


### Workflow Summary

That's a lot of steps! Within a config file subdirectory, you can observe examples of how individual steps are selected within corresponding shell scripts. In some cases, there are multiple datasets being prepared, trained, and predicted, each with their own subset of shell scripts and config files. An overarching shell script (e.g. [`regn_all_proc.sh`](scripts/workflow_configs/00example_configs/clustering_regn_casam_jul26/regn_all_proc.sh)) may demonstrate how to run the workflow for each dataset in one go.


---

## II. Configuration Files

A RaFTS workflow relies on a suite of YAML configuration files to dictate file I/O, dataset schemas, and algorithm hyperparameters. Different datasets/workflows have different sets of config files, as stored inside `scripts/workflow_configs/{00example_configs,legacy}/{workflow_subdir}/`. All config files for a given workflow must be in the same directory!

### TL;DR - Configuration Tips:
When configuring a new workflow, the following are common considerations/gotchas. 
 - Best practice is to copy-paste a directory containing pre-existing config files representing a similar type of workflow. You'll then need to rename that directory, and make sure the new name is reflected in the shell script's `DIR_CONFIG`. Example shell scripts include `regn_all_proc.sh` or `xssaus_proc_rafts_all.sh`.

 - Next, `dataset_name` in the prep config needs to be unique for each workflow. The `dataset_name` is used as a unique identifier in new subdirectories and filenames that are created when running a workflow. 

- Point to the new response variable dataset's location in the prep config's `path_data`. Ensure `respvar_cols` and `respvar_mappings` appropriately define the data columns of interest. Then, as-needed, adapt the custom prep python script in the same directory as the config files to appropriately munge those data.

 - `algo_response_vars` are listed out in the prediction config from the prep config's  `respvar_mappings` for _supervised_ prediction (if appropriate). In _unsupervised_ situations, you'll simply specify `- "cluster_labels"` as the only `algo_response_vars` entry in the prediction config'.

- **Defining Paths**. This can be one of the more challenging aspect of configuration. More details in the following config-specific subsections.

  - **prep config**:
    - Point to the hydrofabric geopackage In `path_hf_gpkg`. This should be the entire hydrofabric .gpkg. This differs from `path_hf_basins_gpkg`, which represents the subset of the hydrofabric of interest. `path_hf_basins_gpkg` is intended to represent aggregates of divides (i.e. basins) using their unique basin id (e.g. USGS gage ID). 
    - **Nexus**-based workflows *may* need to define the flowpath components when input training data are not preprocessed into a form that is aggregated by divides (this can be done in `hfATLAS` nexus-based workflows). When data need aggregated to nexus form, you need to provide the hydrofabric's flowpath layer `hf_fp_layer` and flowpath ID column `hf_fp_id_col` to create divide(s)-to-nexus mappings.
  - **attr config**:
    - `home_dir`: the home directory. Default assumes `~/`
    - `dir_base`: the base directory location for RaFTS datasets. Recommended to mimic what is (generally) consistently used across all the other attribute configs.
    - `dir_std_base`:  The location of standardized response-variable data generated by rafts_prep python package. Recommended to mimic what is (generally) consistenly used across all the other attribute configs.
    - `dir_db_attrs`: Where organized attribute data get stored. To avoid overwriting data, ensure that the final subdirectory contains the f-string `{ds}` so that the `dataset_name` from the prep config is included in the directory name. 
    - `paths_hfatl` Path(s) to tabular HydrofabricATLAS parquet file(s) of algorithm training attributes (aka watershed predictors) extracted to hydrofabric divides or larger aggregated scales. Expected to be provided in list form, e.g. `  - "{home_dir}/path_to/attrs.parquet"`.  Not needed when using the legacy `proc.attr.hydfab` workflow.

  - **algo config**: no paths needed here.

  - **pred config**:
    - `path_meta` points to the prediction watershed attribute dataset. This dataset must contain the same column names used for training.
    - `path_gpkg_pred` points to the corresponding .gpkg providing geospatial context to the locations in `path_meta`. Optional, but strongly recommended when dealing with customized prediction locations (e.g. hydrofabric divides aggregated to a larger scale.)
    - `path_crosswalk_ids` Optional. This is the crosswalk (.csv or parquet file) translates the aggregated basin identifiers to individual hydrofabric divide ids. This file is only guaranteed to work by containing two columns for both identifiers. Use the `crosswalk_target_col` to specify the column name of the gpkg-standard identifier for the target of interest (e.g. 'divide_id').
    - `path_hf_finl_gpkg` This is only used when running `rafts_regn_params_gpkg.py`. This is the path to the 'official' hydrofabric .gpkg file that will be used for `ngen` simulations. A copy of the hydrofabric .gpkg will be made within a RaFTS regionalization subdirectory, and populated with new tables for each `ngen` formulation containing the regionalized parameters. Also specify `layr_hf_finl_gpkg` for good measure.
    - 

### 1. Preparation Config (e.g. `*_prep_config.yaml`)

Used for _preparing_ the raw input data into standardized forms. Originally, this was just the raw response variable data, but now custom attribute data (e.g. `hfATLAS`) are also configured here. The prep config provides the required column mappings, file paths, and response variable metadata. Remember, when preparing the raw response variable data (which can take many forms), a custom, user-coded prep script using the prep config is REQUIRED.

* **`col_schema`**:
  * `gage_id`: The basin identifier/gage id used for each modeled location from the raw response variable data. (Required).


  * `featureID`: The Python f-string format converting the `gage_id` to a standardized featureID. (Required).


  * `featureSource`: The standardized nhdplusTools featureSource (e.g., `hfv22_id`). (Required). This is used to distinguish different types of watershed attribute datasets and is assigned to the `featureSource` column in the attribute data.  In legacy forms of RaFTS that use the `proc.attr.hydfab` R-package, it may be used to designate the data source from NHDPlus attribute retrieval (e.g. 'nwissite'). In normal hydrofabric-based workflows using pre-existing attribute data, it is used to represent the hydrofabric version corresponding to the attribute data (e.g. `hfv22_id`, or `hfv40_id`).


  * `respvar_cols` & `respvar_mappings`: Column(s) in the raw response variables dataset (`'respvar_cols'`) and the mapped column names to be used for the dataset and all further processing. In other words, `'respvar_cols'` gives the user the option to rename the response variables' data columns. (Required).

    - Note that `respvar_mappings` originally existed in order to standardize the nomenclature of what is being predicted. With a standardized nomenclature, expected min/max bounds may then be defined to constrain predictions within the theoretical limits of a 'metric' e.g. KGE must be between 0 and 1. 
    - Note the standardized nomenclature enforcement can be activated by adding `'val_respvar': 'True'`, which references [rafts_categories.yaml](pkg/rafts_prep/rafts_prep/data/rafts_categories.yaml) where the user may enforce specific limits/allowed names for response variables.


* **`file_io`**:
  * `home_dir`: The base home directory. If not specified, the default `~/` will be used. (Optional).

  * `dir_data` or `path_data`: Where the raw response variable data are stored. This is flexible according to the custom prep script created by the user to ingest & munge the data. (Required). 

  * `data_source`: This is a column in the attribute dataset to specify the data source. Required when providing attribute data using the standard RaFTS workflow with pre-processed attribute data. This specifies attribute dataset version (may need to update with major version changes). If using the legacy attribute retrieval workflow (aka `proc.attr.hydfab` R-package), then this is not required. The point is to distinguish where attribute data came from when sourced from a custom dataset. For custom datasets, recommended options are explicit on 1) where the data came from, and 2) the corresponding hydrofabric version, e.g. `'hfATLAS_hf22'` or `'hfATLAS_hf4'`.


  * `dir_save`: The save location of standardized output. Practically all workflows use `'{home_dir}/noaa/regionalization/data/input'`. A standardized directory structure will then be created relative to this path, e.g. `{home_dir}/noaa/regionalization/data/output/` (Required).


  * `save_type`: Save as hierarchical files. Should be `netcdf`. (Required).


  * `save_loc`: Use `local` for saving to a local path. (Required).


  * `path_hf_gpkg`: The path to the gpkg containing the hfATLAS divides. This is used for mapping the divide_id to the standardized featureID and featureSource. In other words, needed for mapping the divide_id. (Required).


  * `path_hf_basins_gpkg`: The path to the gpkg containing the divide_ids as they correspond to basins of interest. Useful when performing regionalization workflows where basin-aggregated hydrofabrics matter. (Optional; expected by `rafts_agg_hfatl_basin.py` for aggregation).


  * `gage_id_col_gpkg`: The gage_id column in the `path_hf_basins_gpkg`, if present. Otherwise do not provide this entry in the config file and specify `gpkg_filename_pattern` instead, where the gage_id is contained inside the filenames of many hydrofabric files representing basins.

  * `gpkg_filename_pattern`: The pattern used to extract the gage_id from the .gpkg filenames contained inside path_hf_basins_gpkg when it's a dir w/ many gpkg files. Default `'gage_(.*).gpkg'`. Use `gage_id_col_gpkg` instead if gage_id is specified in a column inside the .gpkg.

  * `hfatl_id_format` In some cases, the `hfATLAS` workflow may create it's own unique identifier, often as a combination of the USGS gage ID and a hydrofabric ID. Provide a python f-string format for this string type, e.g .`"USGS-{gage_id}_{divide_id}"`. This is an edge case under certain scenarios.

### Attribute prep config requirements
Some options are specific to the next step in the standard workflow using pre-defined attributes. These requirements may vary by the choice of script (`hfatlas_to_rafts_prep.py` vs. `rafts_agg_hfatl_basin.py`).

#### `hfatlas_to_rafts_prep.py`
When working on the individual divide scale, the entire hydrofabric may be considered as an input dataset. Organizing the attributes and hydrofabric by vpu subdirectories offers file reading efficiencies. Otherwise, smaller datasets do not need to be organized by vpu and this section may be ignored.
* **`file_io`**:
  * `vpu_mapped`:  Boolean str. Should output attribute data be organized by vpu? Recommended to be True for large datasets, e.g. entire CONUS scale. If set to False, the vpuid will be assigned as 'all' (appropriate for smaller datasets). More details in `rafts_algo.utils.hfatl_hf_cmbo_wrap()`. The following flowpath and vpu config spec options pertain to `vpu_mapped=True`.

  * `hf_fp_layer` Hydrofabric name for the flowpaths layer, used for organizing file write of data by vpu.

  * `hf_fp_id_col` The column name in the flowpaths layer corresponding to the flowpath outlet of the divide, used for organizing file write of data by vpu.

  * `vpu_id_col` The column name in the hydrofabric flowpaths layer, used for organizing file write of data by vpu

#### Both `rafts_agg_hfatl_basin.py` and `hfatlas_to_rafts_prep.py`
When wanting to aggregate hydrofabric divides to a larger scale, the following config options in the prep config specify the aggregation scale for algorithm training. Ideally, this capability is ignored if the attribute data have already been aggregated in a previous step.
* **`file_io`**
  * `path_hf_basins_gpkg`  The filepath or dir to the gpkg(s) containing the divide_ids as they correspond to basins of interest (e.g. individual .gpkg files representing each calibration basin).
  * `gpkg_filename_pattern` Optional string pattern used to isolate the gage_id from the gpkg filenames inside the `path_hf_basins_gpkg` directory. (Default 'gage_{gage_id}.gpkg')

**`formulation_metadata**:
  * `dataset_name`: The name to be assigned to this dataset. This name will be used to create a subdirectory inside `user_data_std` and is also used in various filenames. This serves as a unique identifier, so make it different from previous workflow runs! (Required).
  **NOTE** a legacy form of allows `dataset_name` to additionally be specified in the attribute config under the subsection `formulation_metadata`.
  This was initially created to handle processing multiple datasets all at once, but `hfATLAS` workflows have made it only possible to processing one dataset per config file (e.g. a required assumption in `rafts_agg_hfatl_basin.py`). 
  Refer to [`scripts/workflow_configs/legacy/ealstm/`](scripts/workflow_configs/legacy/ealstm/) for an example of processing multiple datasets.



### 2. Attribute Config (e.g.`*_attr_config.yaml`)

Configures the acquisition of catchment attributes corresponding to standard-named locations.

* **`file_io`**:
  * `dir_base`: The base save location. (Required). 
  #TODO remove this and base it instead from the `save_loc` in the prep config.


  * `dir_std_base`: The location of standardized data generated by the `rafts_prep` package. (Required).
  #TODO remove this and instead use the `save_loc` as a the core for creating this directory

  * `dir_db_attrs`: The parent dir where each dataset's parquet attributes are stored. Recommended default `'{dir_base}/input/attrs_hfatl/{ds}/'` (Required).


  * `ds_type`: A string used in the filename of the output metadata to discern whether a dataset is a training or prediction dataset. Options are `'training'` or `'prediction'`. In the common situations using custom hfATLAS attribute data, only `'training'` is used. This is used as a string inserted into `path_meta`, but note that `path_meta` is ignored when using the custom-generated attribute data (e.g. hfATLAS source). (Required in legacy workflows acquiring attribute data via `proc.attr.hydfab`).


  * `name_prep_config`: The name of the prep config file. Only used when running the hfatlas-based workflow.  This should be `None` when running the legacy `proc.attr.hydfab` component of the workflow. Note that `rafts_pred_algo.py` uses logic on whether this is present to determine how to read predictor data (aka basin attributes).


  * `path_meta`: Ignored when processing pre-existing attribute data (e.g. hfATLAS), although not ignored in the prediction config when part of the workflow. For the attribute config, this is used in the legacy RaFTS workflow's `proc.attr.hydfab` processing. Training attribute metadata filepath formatted for R's glue or py f-string, as generated using `proc.attr.hydfab::write_meta_nldi_feat()`. Strongly suggested default:  "{dir_std_base}/{ds}/nldi_feat_{ds}_{ds_type}.parquet"


* **`formulation_metadata`**:
  * `datasets`: The dataset names to select for further processing. (Required).
    * **NOTE** the dataset names of interest must also be specified in the prep config.
    * This was initially created to handle processing multiple datasets all at once, but present workflows have drifted towards just processing one dataset at a time. Refer to `scripts/workflow_configs/legacy/ealstm/` for an example of processing multiple datasets.


* **`attr_select`**:
  * `hfatl_id_col`: The unique location identifier column name used in `paths_hfatl`


  * `paths_hfatl`: Path to tabular HydrofabricATLAS parquet files. This is required in the current workflow where the user provides the attribute data. This can be the CONUS-scale attribute data when performing basin aggregation via `rafts_agg_hfatl_basin.py`. (Required).


  * `hfatl_vars`: A list of the specific attribute data column names to use as predictors when training algorithms. (Required).





### 3. Algorithm Config (e.g. `*_algo_config.yaml`)

Configures the training and testing of algorithms that predict response variables (e.g. formulation metrics or hydrologic signatures).

* `task_type`: The type of machine learning task. Explicitly enter `clustering` if you desire to run unsupervised clustering. Otherwise the default `'regression'` will be considered supervised.

* `save_all_clusters`: Boolean.  Should every distinct algorithm combination be saved, or just the best-performing algorithm based on the silhouette score? Only applicable to `task_type="clustering"`. Default `False`.

* `algorithms`: Selected algorithm(s) to run, such as `kmeans`, `gower_agglomerative`, `rf`, or `mlp`. (Required). If more algorithms are desired, they may be inserted in the [rafts_algo_train.py](pkg/rafts_algo/rafts_algo/rafts_algo_train.py). Note that new supervised algorithms need a little more effort by also integrating them into the uncertainty pipeline.

  * Custom configurations are then provided as nested subsets with the algorithm section. The first nesting level is the algorithm standard name e.g. (`rf:` or `kmeans`), which is followed by another nested level of optional algorithm hyperparameters e.g.:
  ```yaml
  algorithms:
   rf:
     - n_estimators: 300
   mlp:
     - max_iter: [20000,80000,160000]
  ```
  Note that lists of hyperparameters (e.g. `max_iter` in the example above) means that `scikit-learn`'s `GridSearchCV` will be employed.

* `test_size`: The proportion of the dataset reserved for testing. Default 0.3. (Required).


* `seed`: The starting point for the random number generator. Default 32. (Required).

* `n_jobs`: Only applicable for GridSearchCV operations. Default 1 when running `rafts_proc_algo_pool.py` and -1 when running `rafts_proc_algo_viz.py`. Number of jobs for grid search operations. Recommended to stay with the defaults, but this is configurable.

* `name_attr_config`: Name of the corresponding dataset's attribute configuration file. (Required).


* `read_type`: Must use `all` for anything using custom-generated predictor (attributes) data. (Required).


* `verbose`: Should the train/test/eval provide printouts on progress? (Optional).


* `make_plots`: Should plots be created & saved to file? (Optional).

* `uncertainty`: Defines methods to quantify uncertainty in model training and predictions for regression-based algorithms, supporting methods like `bagging`, `forestci`, and `mapie`. (Optional).

 - Example of the uncertainy section:
    ```yaml
    uncertainty: # OPTIONAL. Defines methods to quantify uncertainty in model training and predictions.
      confidence_levels: [90,95,99] # OPTIONAL list object, e.g. [90,95]. REQUIRED if a value is assigned to n_algos. Confidence levels between 50 and 100 for bootstrap ci calculation in an array format.
      uncn_bnd_algo: False  # Optional. Default False. Should the minimum and maximum bounds be applied when calculating the uncertainty? Strongly recommended to keep the flag 'False'. 
      forestci:  # OPTIONAL. Used only with Random Forest (rf). Applies forestci to estimate confidence intervals for the model training based on the variance of predictions from trees in the random forest model. For more details, see: https://github.com/scikit-learn-contrib/forest-confidence-interval
        - fci_flag: True # Boolean. Forestci model to calculate confidence interval for rf model.
      bagging:  # OPTIONAL. Enables bootstrap aggregating (bagging) to calculate confidence intervals during the model training by training multiple models on resampled data. More broadly applicable than forestci, as it works with the algorithm types other than rf as well.
        - n_algos: 10 # OPTIONAL. Enabled if not empty. Number of bootstrap runs for Bagging confidence interval calculation (integer). Bagging ci calculation is disabled if n_algos is empty.
      mapie:  # OPTIONAL. Applies the MAPIE (Model Agnostic Prediction Interval Estimator) framework to estimate **prediction intervals**, which provide bounds around individual predicted values. Supports many model types. See documentation for details: https://mapie.readthedocs.io/en/stable/index.html
        - alpha: [0.05, 0.32] # OPTIONAL list object, e.g. [0.05, 0.32]. MAPIE prediction interval estimation will be enabled if not empty. Alpha parameter (0 < α < 1) in an array format to calculate MAPIE prediction intervals. If empty, MAPIE is not calculated. Note: 1/α (or 1/(1 - α)) must be lower than the number of samples.
        - method: 'plus' #  OPTIONAL. But REQUIRED if MAPIE_alpha provided. MAPIE method: 'plus' (CV+) or 'minmax' (CV-minmax). For more information and other methods, refer to: https://mapie.readthedocs.io/en/stable/theoretical_description_regression.html
        - cv: 10 # OPTIONAL integer. REQUIRED if MAPIE_alpha provided. Specifies the number of cross-validation folds.
        - agg_function: 'median' #OPTIONAL. But REQUIRED if MAPIE_alpha provided. Option: 'mean', 'median'.
    ```
Note that if uncertainty quantifications are desired in the prediction step, appropriate configurations must also be specified in the prediction config (e.g. specify `MAPIE_alpha` for the `mapie` configuration).

### 4. Prediction Config (e.g. *_pred_config.yaml)

Configures the out-of-sample prediction step and downstream mapping.

* `name_attr_config`: Name of the corresponding attribute configuration file. (Required).


* `name_algo_config`: The name of the trained algorithm configuration file. (Required).


* `name_tfrm_config`: Deprecated with the custom attribute (e.g. hfATLAS) workflow. The name of the transformation configuration file. (Required if transforming predictor data). Present workflows should perform desired transformations on attribute data beforehand, not during RaFTS processing.


* `ds_type`: A string identifying the output dataset, highly recommended to be set to `prediction`. This is used as a string inserted into `path_meta`, but note that `path_meta` is ignored when using the custom-generated attribute data (e.g. hfATLAS source). (Required in legacy workflows acquiring attribute data via `proc.attr.hydfab`).

* `path_meta`: This is where the prediction attribute data are stored. Not to be confused with `path_meta` in the attribute config file, which is what is used for defining the predictor dataset location.  

* `pred_file_comid_colname`: The column name containing the location identifiers used for prediction within the `path_meta` file. (Required).

* `path_gpkg_pred`: Strongly recommended for custom prediction locations (e.g. aggregated locations). If not provided, the `path_gpkg_rafts_prep` will be used, which may not have any required data points corresponding to prediction locations. This is required when running `rafts_map_pred_hfatl.py` in order to generate maps of prediction locations.

* `pred_gpkg_lyr`: The layer name corresponding to `path_gpkg_pred` to read from the prediction geopackage. Default None. The fallback reads the gpkg used in the response variable preparation (`path_gpkg_rafts_prep`).

* `pred_gpkg_id_col`: The target location identifier column name corresponding to `path_gpkg_pred`. Crucially, when path_crosswalk_ids is specified, this also serves as the formal join key column name inside the crosswalk file that corresponds to your initial prediction identifiers. It is used to merge predictions with the crosswalk dataset in `rafts_pair_donors.py` and `rafts_regn_params_gpkg.py`. If not explicitly mapped, the fallback reads the gpkg used in the response variable preparation (`path_gpkg_rafts_prep`). Default None. 

* `path_crosswalk_ids`: Optional. Path to the .parquet file used to crosswalk aggregated identifiers (e.g. `'huc12'`, `'gage_id'`) to the standard identifier (e.g. `'divide_id'`). Used in `rafts_agg_nexus_hfatl.py`, `rafts_map_pred_hfatl.py`, `rafts_regn_params_gpkg.py` and `rafts_pair_donors.py`. Must also specify `crosswalk_target_col` and `path_hf_finl_gpkg` in order to execute the merge operation.

* `crosswalk_target_col`: The column name in `path_crosswalk_ids` representing the gpkg target identifier of interest  that is used inside `path_hf_finl_gpkg`. In the case of hydrofabric divides, this is usually `'divide_id'`. When the crosswalk executes, this col will become the new primary key in the resulting SQLite database and .gpkg layers (when running `rafts_regn_params_gpkg.py`).

* `overwrite_sql`: Boolean. Should the sqlite tables for each parameter set be overwritten? Recommended when running `rafts_regn_params_gpkg.py`. Default `False`. 

* `path_hf_finl_gpkg`  Required when running `rafts_regn_params_gpkg.py`. The hydrofabric gpkg containing the divides specified in the path_crosswalk_ids. e.g. `'{home_dir}/noaa/hydrofabric/v2.2_2025Apr/conus_nextgen'`.gpkg'. Should also specify `path_crosswalk_ids`. Note that this is also referenced in the mapping script `rafts_map_pred_hfatl.py` when the workflow includes `rafts_regn_params_gpkg.py`.

*  `layr_hf_finl_gpkg` This is the layer name of the corresponding path_hf_finl_gpkg. Generally, this is going to be 'divides', but the default is None in case the .gpkg doesn't have layer names.

* `algo_select` The specfic algorithm string to use for the final integration into the regionalization gpkg (ie a new layer added to the copy of path_hf_finl_gpkg). Used in `rafts_regn_params_gpkg.py`. e.g. 'gower_agglomerative_k12' 

* `path_tfrm_script` & `conda_env`: Filepath to the transformation script and its execution environment. (Required if transforming data). Not used with the modern `hfATLAS` workflow, but this was used in legacy workflows that employed `proc.attr.hydfab`.


* `algo_response_vars`: A list of the desired response variables or metrics to predict. (Required).


* `algo_type`: A list of the trained regressor algorithms desired for prediction, such as `rf` or `mlp`. (Required).


* `MAPIE_alpha`: Alpha parameters (between 0 and 1) in an array format to calculate MAPIE prediction intervals. Only applicable when using supervised regression algorithms. (Optional).


* `uncn_bnd_pred`: Boolean flag determining whether physical minimum/maximum bounds should be applied when calculating uncertainty. Only applicable when using supervised regression algorithms. (Optional).

---

## III. Input Dataset Description Template

When describing the input datasets within the RaFTS workflow, use the following template based on the `formulation_metadata` and `references` YAML schema. These metadata are mostly optional/ignored in further processing step.

```yaml
formulation_metadata:  
  - 'dataset_name': '' # [Required] The unique name of the dataset folder (e.g., 'hfatl_huc12_clust')
  - 'formulation_base': '' # [Ignore] Legacy use, ignore this.
  - 'formulation_id': '' # [Required] Response variable identifier (pertaining to the formulation)
  - 'formulation_ver': '' # [Ignore] Legacy use, ignore this.
  - 'temporal_res': '' # [Optional] The temporal resolution corresponding to the modeled data
  - 'target_var': '' # [Optional] The target variable modeled (e.g., 'param')
  - 'start_date': '' # [Optional] The YYYY-MM-DD start date of the modeled timeseries
  - 'end_date': '' # [Optional] The YYYY-MM-DD end date of the modeled timeseries
  - 'modeled notes': '' # [Optional] Any notes describing the dataset or test case
  - 'cal_status': '' # [Optional] Was the formulation model fully calibrated? ('Y','N', or 'S')
  - 'start_date_cal': '' # [Optional] The YYYY-MM-DD start date of the calibration period
  - 'end_date_cal': '' # [Optional] The YYYY-MM-DD end date of the calibration period
  - 'cal_notes': '' # [Optional] Notes regarding the calibration process

references: 
  - 'input_filepath': '' # [Optional] Path to the raw input data file
  - 'source_url': '' # [Optional] URL where the data was sourced
  - 'dataset_doi': '' # [Optional] DOI for the dataset
  - 'literature_doi': '' # [Optional] DOI for associated literature

```


## IV. Data Requirements

To successfully execute the RaFTS hfATLAS workflow, you must provide three primary categories of input data: the target response variables, the spatial hydrofabric framework, and the predictor attributes. If you intend to run out-of-sample predictions, a fourth dataset of prediction locations is also required.

### 1. Response Variable Data (The "Targets")
This dataset contains the known values that the machine learning algorithms will be trained to predict. These are typically modeled outputs such as calibrated parameters, hydrologic signatures, parameter sensitivities, or formulation evaluation metrics (e.g., NSE, KGE).
* **Format:** Varies originally (e.g., `.csv`, `.parquet`, `.txt`), but your custom `prep_*.py` script is responsible for ingesting it and standardizing it into a NetCDF (`.nc`) file.
* **Key Constraints:** 
  * Must contain a distinct location identifier column (e.g., `site_id` or `gage_id`).
  * This identifier must map cleanly to the spatial hydrofabric.
* **Config Link:** Defined by `path_data` (or `dir_data`) in the Preparation Config.

### 2. Catchment Predictor Data (e.g., hfATLAS)
These are the physical, climatic, or anthropogenic characteristics (watershed attributes) used as the features/predictors during algorithm training. 
* **Format:** Tabular Parquet files (`.parquet`).
* **Key Constraints:**
  * Must contain a location identifier column that matches the hydrofabric (e.g., `divide_id` or `comid`).
  * Must contain the exact column names specified in the attribute config file's `hfatl_vars`.
  * *Note:* The RaFTS workflow is designed to automatically clean and parse complex PyArrow struct/tuple column headers commonly found in hfATLAS data as a stringified tuple (e.g. `('TOT_AET', 'mm')`), so use the column name without the pint unit.
* **Config Link:** Defined by `paths_hfatl` in the Attribute Config. If performing the basin aggregation step `rafts_map_pred_hfatl.py`, the `paths_hfatl` may be from the entire hydrofabric domain.

### 3. Spatial Framework (Hydrofabric Geometries)
The spatial datasets provide the geographical backbone for the workflow, allowing RaFTS to map tabular data to real-world coordinates and generate  maps.
* **Format:** GeoPackage (`.gpkg`), provided as either a single consolidated file or a directory of subset files.
* **Key Constraints:**
  * Must contain the target geometric layers (e.g., `flowpaths`, `divides`).
  * If you are running `rafts_agg_hfatl_basin.py` to aggregate attributes to a larger scale, the `.gpkg` **must** contain an explicit mapping linking the internal native divides (e.g., `divide_id`) to the terminal aggregated basin (e.g., `gage_id`).
  * Must contain the Vector Processing Unit identifier (`vpuid`) if VPU-partitioned processing is enabled.
* **Config Link:** Defined by `path_hf_gpkg` and `path_hf_basins_gpkg` in the Preparation Config.

### 4. Prediction Location Metadata (For Out-of-Sample Inference)
If you are moving beyond training/testing and want to use your trained algorithms to predict values in un-modeled locations, you must provide a list of those target locations.
* **Format:** Typically `.parquet` or `.csv`.
* **Key Constraints:** Must contain the location identifiers (e.g., `divide_id` or `featureID`) corresponding to the areas where you have predictor data but lack response variables. 
* **Config Link:** Defined by `path_meta` and `pred_file_comid_colname` in the Prediction Config.




---

## V. Usage Example & Execution Workflow

To run the end-to-end RaFTS pipeline using the modern `uv` Python package manager, execute the following scripts in order. *(Note: Adjust the configuration file paths to match your active directory structure).*

**1. Prepare the initial dataset:**

```bash
uv run python pkg/rafts_prep/rafts_prep/flow/prep_hfatl_test.py "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_prep_config.yaml"

```

**2. Grab or Aggregate Attributes:**
*(For native divides)*:

```bash
uv run python pkg/rafts_prep/rafts_prep/flow/hfatlas_to_rafts_prep.py \
    --path_prep_config "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_prep_config.yaml" \
    --name_attr_config "hfatl_attr_config.yaml"

```

*(For basin aggregation)*:

```bash
uv run python pkg/rafts_prep/rafts_prep/flow/rafts_agg_hfatl_basin.py \
    --path_prep_config "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_prep_config.yaml" \
    --path_attr_config "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_attr_config.yaml"

```

**3. Train & Test Algorithms:**

```bash
uv run python pkg/rafts_algo/rafts_algo/flow/rafts_proc_algo_pool.py "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_algo_config_uncn.yaml" --chunk_size 4

```

**4. Perform Out-of-Sample Predictions:**

```bash
uv run python pkg/rafts_algo/rafts_algo/flow/rafts_pred_algo.py "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_pred_config_uncn.yaml"

```

**5. Map Predictions:**

```bash
uv run python pkg/rafts_algo/rafts_algo/flow/rafts_map_pred_hfatl.py "scripts/workflow_configs/00example_configs/hfatl_test/hfatl_pred_config_uncn.yaml"

```

**6. Pair Donors and Receivers:**
(Only for unsupervised clustering algorithms)
```bash
uv run python pkg/rafts_algo/rafts_algo/flow/rafts_pair_donors.py "scripts/workflow_configs/path_to/*_pred_config.yaml"

```

**7. Populate the hydrofabric .gpkg with selected regionalized parameters:**

```bash
uv run python pkg/rafts_algo/rafts_algo/flow/rafts_regn_params_gpkg.py "scripts/workflow_configs/path_to/*_pred_config.yaml"
```
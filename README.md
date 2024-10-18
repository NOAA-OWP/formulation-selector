
----

# Regionalization and Formulation Testing and Selection (RaFTS)

**Description**:  
The formulation-selector tool, aka Regionalization and Formulation Testing & Selection (RaFTS), is under development. For more information, see the [Wiki](https://github.com/NOAA-OWP/formulation-selector/wiki). 

As NOAA OWP builds the model-agnostic NextGen framework, the hydrologic modeling community will need to know how to optimally select model formulations and estimate parameter values across ungauged catchments. This problem becomes intractable when considering the unique combinations of current and future model formulations combined with the innumerable possible parameter combinations across the continent. To simplify the model selection problem, we apply an analytical tool that predicts hydrologic formulation performance (Bolotin et al., 2022, Liu et al., 2022) using community-generated data. The regionalization and formulation testing and selection (RaFTS) tool readily predicts how models might perform across catchments based on catchment attributes. This decision support tool is designed such that as the hydrologic modeling community generates more results, better decisions can be made on where formulations would be best suited.

**Technology stack**: 
  - **Python:** The features of the formulation-selector that ingest model results and catchment attributes to predict model performances based on catchment attributes is written in Python. 
  - **R:** The features of the formulation-selector that acquire catchment attributes that feed into the model prediction algorithm (which, as noted above, is in Python) are written in R to promote compatibility with the [NOAA-OWP/hydrofabric](https://github.com/NOAA-OWP/hydrofabric). 

**Status**:  Preliminary development. [CHANGELOG](CHANGELOG.md).
  - **Technology stack**: python. The formulation-selection decision support tool is intended to be a standalone analysis, though integration with pre-existing formulation evaluation metrics tools will eventually occur.
  - **Status**:  Preliminary development. [CHANGELOG](CHANGELOG.md).
  - **Links to production or demo instances**
  - _Describe what sets this apart from related-projects. Linking to another doc or page is OK if this can't be expressed in a sentence or two._


**Screenshot**: If the software has visual components, place a screenshot after the description; e.g.,
N/A

## Dependencies

#### R Packages
#### Python Packages
Thus far, `formulation-selector` has been developed in and tested with Python versions 3.11 and 3.12, so these are currently the recommended versions. 

You may consider creating a new virtual environment for employing `formulation-selector` with the following packages:  

- [pynhd](https://github.com/hyriver/pynhd)
- dask
- joblib
- netcdf4
- numpy
- pandas
- pyyaml
- scikit_learn
- setuptools
- xarray


## Installation - `fs_proc` Python package

### TL;DR
- [NOAA-OWP/hydrofabric](https://github.com/NOAA-OWP/hydrofabric)
  - Note that the arrow package needs `arrow::arrow_with_s3() == TRUE`. If `FALSE`, consider downloading arrow via [apache's r-universe](https://apache.r-universe.dev/arrow)
  - Steps to install hydrofabric: Refer to wiki
- [USGS nhdplusTools](https://github.com/doi-usgs/nhdplusTools/)
- [pynhd](https://github.com/hyriver/pynhd)


## Installation - fs_proc python package

### TLDR
 - Install `fs_proc` package
   `pip install /path/to/pkg/fs_proc/fs_proc/.`
 - Build a yaml config file `/sripts/eval_metrics/name_of_dataset_here/name_of_dataset_schema.yaml` [refer to this template](https://github.com/NOAA-OWP/formulation-selector/blob/main/scripts/eval_ingest/xssa/xssa_schema.yaml)
 - Create a script that reads in the data and runs the standardization processing. [Example script here](https://github.com/NOAA-OWP/formulation-selector/blob/main/scripts/eval_ingest/xssa/proc_xssa_metrics.py)
 - Then run the following:
  ```
  cd /path/to/scripts/eval_metrics/name_of_dataset_here/
  python proc_name_of_dataset_here_metrics.py "name_of dataset_here_schema.yaml"
  ```

### 1. Install the `fs_proc` package, which standardizes raw input data into a common format.
```
> cd /path/to/pkg/fs_proc/fs_proc
> pip install .
```

### 2. Build a custom model metrics data ingest
Ingesting raw data describing model metrics (e.g. KGE, NSE) from modeling simulations requires two tasks:
   1. Creating a custom configuration schema as a .yaml file
   2. Modify a dataset ingest script

We track these tasks inside `formulation-selector/scripts/eval_ingest/_name_of_raw_dataset_here_/`
#### 1. `data_schema.yaml`
The data schema yaml file contains the following fields:
 - `col_schema`:  required column mappings in the evaluation metrics dataset. These describe the column names in the raw data and how they'll map to standardized column names. 
    - for `metric_mappings` refer to the the [fs_categories.yaml](https://github.com/NOAA-OWP/formulation-selector/blob/main/pkg/fs_proc/fs_proc/data/fs_categories.yaml) 
 - `file_io`: The location of the input data and desired save location. Also specifies the save file format.
 - `formulation_metadata`: Descriptive traits of the model formulation that generated the metrics. Some of these are required fields while others are optional.
 - `references`: Optional but _very_ helplful metadata describing where the data came from.

#### 2. `proc_data_metrics.py`
The script that converts the raw data into the desired format. This performs the following tasks:
 - Read in the data schema yaml file (standardized)
 - Ingest the raw data (standardized)
 - Modify the raw data to become wide-format where columns consist of the gage id and separate columns for each formulation evaluation metric (user-developed munging)
 - Call the `fs_proc.proc_col_schema()` to standardize the dataset into a common format (standardized function call)



## Configuration

If the software is configurable, describe it in detail, either here or in other documentation to which you link.

## Usage

### raw metrics dataset processing
  ```
  cd /path/to/scripts/eval_metrics/name_of_dataset_here/
  python proc_name_of_dataset_here_metrics.py "name_of dataset_here_schema.yaml"
  ```

## How to test the software

You may also run unit tests on `fs_proc`:
```
> cd /path/to/formulation-selection/pkg/fs_proc/fs_proc/tests
> python -m unittest test_proc_eval_metrics.py
```
To assess code coverage:
```
python -m coverage run -m unittest
python -m coverage report
```

## Known issues

Document any known significant shortcomings with the software.

## Getting help

If you have questions, concerns, bug reports, etc, please file an issue in this repository's Issue Tracker.

## Getting involved

This section should detail why people should get involved and describe key areas you are
currently focusing on; e.g., trying to get feedback on features, fixing certain bugs, building
important pieces, etc.

General instructions on _how_ to contribute should be stated with a link to [CONTRIBUTING](CONTRIBUTING.md).

# Attribute Grabber
**Description**:  
Attributes from non-standardized datasets may need to be acquired for RaFTS modeling and prediction. The R package `proc.attr.hydfab` performs the attribute grabbing.

## Installation - `proc.attr.hydfab` R package
Run [`flow.install.proc.attr.hydfab.R`](https://github.com/NOAA-OWP/formulation-selector/blob/main/pkg/proc.attr.hydfab/flow/flow.install.proc.attr.hydfab.R) to install the package. Note that a user may need to modify the section that creates the `fs_dir` for their custom path to this repo's directory.

## Usage - `proc.attr.hydfab`
The following is an example script that runs the attribute grabber: [`fs_attrs_grab`](https://github.com/NOAA-OWP/formulation-selector/blob/main/pkg/proc.attr.hydfab/flow/fsds_attrs_grab.R).

This script grabs attribute data corresponding to locations of interest, and saves those attribute data inside a directory as multiple parquet files. The `proc.attr.hydfab::retrieve_attr_exst()` function may then efficiently query and then retrieve desired data by variable name and comid from those parquet files.

Note that this script was designed to process data that have already been generated by the `fs_proc` python package, but users may want to grab attributes from additional locations that have not been processed by `fs_proc` (e.g. attributes from ungaged basins to use for prediction). 

 - To independently process attributes for locations without running `fs_proc` python package beforehand: A user may ignore previously-processed data by setting `Retr_Params$datasets` as `NULL` and specifying the path to a file containing gage_ids inside the `Retr_Params$loc_id_read` list.
 - In the context of reading in a processed dataset from `fs_proc` or reading in a separate file specifying locations of interest, the `Retr_Params$datasets` uses directory names inside `input/user_data_std/` (or simply `all` to process all datasets). The additional file with location ids may also be read in, or ignored entirely. In summary, the either-or or both approaches are options, and is defined by how the `Retr_Params` parameter list object is populated.
 - The 'independent' data file for processing attributes has been tested for .csv and .parquet file formats. Other formats compatible with `arrow::open_dataset()` should be possible but have not been tested.

----

## Open source licensing info
1. [TERMS](TERMS.md)
2. [LICENSE](LICENSE)


----
## Credits and references

Bolotin, LA, Haces-Garcia F, Liao, M, Liu, Q, Frame, J, Ogden FL (2022). Data-driven Model Selection in the Next Generation Water Resources Modeling Framework. In Deardorff, E., A. Modaresi Rad, et al. (2022). [National Water Center Innovators Program - Summer Institute, CUAHSI Technical Report](https://www.cuahsi.org/uploads/library/doc/SI2022_Report_v1.2.docx.pdf), HydroShare, http://www.hydroshare.org/resource/096e7badabb44c9f8c29751098f83afa

Liu, Q, Bolotin, L, Haces-Garcia, F, Liao, M, Ogden, FL, Frame JM (2022) Automated Decision Support for Model Selection in the Nextgen National Water Model. Abstract (H45I-1503) presented at 2022 AGU Fall Meeting 12-16 Dec.

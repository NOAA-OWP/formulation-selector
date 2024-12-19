""" Remove bad variables from the attribute dataset
THIS DOESN'T SEEM TO WORK DUE TO DIFFERENCES IN PARQUET FILES WRITTEN BY R vs python
USE remove_bad_tfrms.R INSTEAD!!


Could this relate to parquet files being created using arrow, not dask?
This may need to be performed using the R package proc.attr.hydfab's capabilities.
"""
import fs_algo.fs_algo_train_eval as fsate
import yaml
from pathlib import Path
import dask.dataframe as dd

path_attr_config = "~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attr_config.yaml"
attr_cfig = fsate.AttrConfigAndVars(path_attr_config) 
attr_cfig._read_attr_config()

# list the bad attribute transformations here
bad_vars = ['TOT_WB5100_yr_np.mean']

dir_db_attrs = attr_cfig.get("dir_db_attrs")
# All transformation files in in dir_db_attrs
p = Path(dir_db_attrs).glob('*_tfrmattr.parquet')
all_tfrmattr_files = [x for x in p if x.is_file]

for filename_parq in all_tfrmattr_files:
    attr_ddf_subloc = dd.read_parquet(filename_parq, storage_options=None)

    all_attr_names = attr_ddf_subloc['attribute'].compute()
    rm_attrs = [x for x in all_attr_names  if x in bad_vars]
    if rm_attrs:
        
        filtered_ddf = attr_ddf_subloc[~attr_ddf_subloc['attribute'].isin(bad_vars)]
        if Path(filename_parq).exists():
            Path(filename_parq).unlink()
        filtered_ddf.to_parquet(filename_parq,overwrite=True)

# Call in the package
library(proc.attr.hydfab)
library(tidyverse)
library(dataRetrieval)

# Set important params (Retr_Params) ----------------------------------
home_dir <- Sys.getenv("HOME")
path_cfig_pred <- glue::glue("{home_dir}/Lauren/FSDS/formulation-selector/scripts/eval_ingest/xssa_NWM_domain/xssanwm_pred_config.yaml")
subsamp_n <- 20 # how is this decided? see how this impacts processing
subsamp_seed <- 432

# Read in config file
if(!base::file.exists(path_cfig_pred)){
  stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
}


cfig_pred <- yaml::read_yaml(path_cfig_pred)
ds_type <- base::unlist(cfig_pred)[['ds_type']]
write_type <- base::unlist(cfig_pred)[['write_type']]
path_meta <- base::unlist(cfig_pred)[['path_meta']] # The filepath of the file that generates the list of comids used for prediction

# READ IN ATTRIBUTE CONFIG FILE
path_attr_config <- glue::glue(cfig_pred[['path_attr_config']])
cfig_attr <- yaml::read_yaml(path_attr_config)

# Defining directory paths as early as possible:
io_cfig <- cfig_attr[['file_io']]
dir_base <- glue::glue(base::unlist(io_cfig)[['dir_base']])
dir_std_base <- glue::glue(base::unlist(io_cfig)[['dir_std_base']])
dir_db_hydfab <- glue::glue(base::unlist(io_cfig)[['dir_db_hydfab']])
dir_db_attrs <- glue::glue(base::unlist(io_cfig)[['dir_db_attrs']])

# ------------------------ ATTRIBUTE CONFIGURATION --------------------------- #
hfab_cfg <- cfig_attr[['hydfab_config']]

names_hfab_cfg <- unlist(lapply(hfab_cfg, function(x) names(x)))
names_attr_sel_cfg <- unlist(lapply(cfig_attr[['attr_select']], function(x) names(x)))
s3_base <- glue::glue(base::unlist(hfab_cfg)[['s3_base']]) # s3 path containing hydrofabric-formatted attribute datasets
s3_bucket <- glue::glue(base::unlist(hfab_cfg)[['s3_bucket']]) # s3 bucket containing hydrofabric data
s3_path_hydatl <- glue::glue(unlist(cfig_attr[['attr_select']])[['s3_path_hydatl']]) # path to hydroatlas data formatted for hydrofabric

form_cfig <- cfig_attr[['formulation_metadata']]
datasets <- form_cfig[[grep("datasets",form_cfig)]]$datasets

# Additional config options
hf_cat_sel <- base::unlist(hfab_cfg)[['hf_cat_sel']]#c("total","all")[1] # total: interested in the single location's aggregated catchment data; all: all subcatchments of interest

# The names of attribute datasets of interest (e.g. 'ha_vars', 'usgs_vars', etc.)
names_attr_sel <- base::lapply(cfig_attr[['attr_select']],
                               function(x) base::names(x)[[1]]) %>% unlist()

# Generate list of standard attribute dataset names containing sublist of variable IDs
ls_vars <- names_attr_sel[grep("_vars",names_attr_sel)]
vars_ls <- base::lapply(ls_vars, function(x) base::unlist(base::lapply(cfig_attr[['attr_select']], function(y) y[[x]])))
names(vars_ls) <- ls_vars

# The attribute retrieval parameters
Retr_Params <- list(paths = list(# Note that if a path is provided, ensure the
  # name includes 'path'. Same for directory having variable name with 'dir'
  dir_db_hydfab=dir_db_hydfab,
  dir_db_attrs=dir_db_attrs,
  s3_path_hydatl = s3_path_hydatl,
  dir_std_base = dir_std_base,
  path_meta=path_meta),
  vars = vars_ls,
  datasets = datasets,
  ds_type = ds_type,
  write_type = write_type
)

# Get COMIDS -------------------------------------
home_dir <- Sys.getenv("HOME")

# COMID for most downstream portion of flowpath intersecting HUC08 boundaries
lowest_hs <- read.csv(glue('{home_dir}/Lauren/regionalization/comids_lowest_hf_hydroseq.csv'))

# COMID for most upstream portion of the flowpath intersecting HUC08 boundaries
highest_hs <- read.csv(glue('{home_dir}/Lauren/regionalization/comids_highest_hf_hydroseq.csv'))

comids <- unique(highest_hs$hf_id)

# Grab attributes ------------------------------
# For some reason, running the following got this working
library(future)
library(future.apply)
dt_site_feat <- proc_attr_mlti_wrap(comids = comids, Retr_Params = Retr_Params, 
                    lyrs = "network", overwrite = FALSE)
# Run this^^, run attribute transformation, and then run it again???


for(ds in datasets){
  path_nldi_out <- glue::glue(path_meta)
  
  proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat,
                                         path_meta = path_nldi_out)
}

#' @title Retrieve attributes for RFC locations (as available!)
#' @author Guy Litt
#' @description Given the comids of RFC forecast locations, grab NHDPlus 
#' catchment attributes

library(nhdplusTools)
library(proc.attr.hydfab)

library(dplyr)
library(glue)
library(tidyr)
library(yaml)



main <- function(){
  args <- commandArgs(trailingOnly = TRUE)
  # Check if the input argument is provided
  if (length(args) < 1) {
    stop("Input prediction configuration file must be specified")
  }
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml")
  # subsamp_n <- ifelse(length(args) >= 2, base::as.integer(args[2]), 20) #subsamp_n <- 20
  # subsamp_seed <- ifelse(length(args) >=3, base::as.integer(args[2]), 432) # subsamp_seed <- 432
  # 
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
  ###################### DATASET-SPECIFIC CUSTOM MUNGING #########################
  # USER INPUT: Paths to relevant config files
  # Read file and remove poorly-parsed rows
  df <- read.delim(file="~/git/formulation-selector/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt", # Obtained from Gautam Sood at OWP: a file of all RFC locations
                   skip=0,sep = "|",col.names = c("nws_station_id","comid")) 
  df <- df[-base::grep("-------+-----", df$nws_station_id),]
  df <- df[-which(base::is.na(df$comid)),]
  
  ############################ END CUSTOM MUNGING ##############################
  
  message(glue::glue("Processing {nrow(df)} locations"))
  # ---------------------- Grab all needed attributes ---------------------- #
  # --- Create the path to the geopackage:
  # Define the standardized path to the geopackage based on the input dataset
  path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
    dir_std_base = Retr_Params$paths$dir_std_base,ds = Retr_Params$datasets[[1]])
  

  seq_nums <- c(seq(from=1,nrow(df),350),nrow(df))[-1]
  for(seq_num in seq_nums){
    sub_df <- df[1:seq_num,]
    # Now acquire the attributes:
    dt_site_feat <- proc.attr.hydfab::proc_attr_gageids(gage_ids=sub_df$comid,
                                                        featureSource='comid',
                                                        featureID='{gage_id}',
                                                        Retr_Params=Retr_Params,
                                                        path_save_gpkg = path_save_gpkg,
                                                        lyrs=lyrs,
                                                        overwrite=overwrite)
    Sys.sleep(60*61) # 400 NLDI queries per hour
  }
  
  
 
  # # --------------------------- INPUT DATA READ -------------------------------- #
  # raw_cfg <- yaml::read_yaml(path_raw_config)
  # 
  # # Read in the xssa dataset, remove extraneous spaces, subselect USGS gages
  # path_data <- glue::glue(raw_cfg[['file_io']][[grep("path_data",raw_cfg[['file_io']])]]$path_data)
  # df_all_xssa <- utils::read.csv(path_data,sep = ';', colClasses=c("basin_id"="character"))
  # 
  # # Read in the CAMELS dataset so we can pick non-CAMELS locations for testing
  # path_camels <-  glue::glue(raw_cfg[['file_io']][[grep("path_camels",raw_cfg[['file_io']])]]$path_camels)
  # df_camels <- utils::read.csv(path_camels,sep=';',colClasses=c("gauge_id"="character"))
}
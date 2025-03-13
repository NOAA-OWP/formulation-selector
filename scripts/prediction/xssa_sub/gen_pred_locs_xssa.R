#' @title Test case to use for algorithm prediction
#' @author Guy Litt
#' @description Selects a small sample of US locations (20) from the Julie Mai xSSA
#' dataset and generates attributes to use for testing algo prediction capabilities
#' @reference https://www.nature.com/articles/s41467-022-28010-7
#' @param path_cfig_pred The path to the prediction configuration yaml file. May use glue formatting for {home_dir}
#' @examples
#' \dontrun{Rscript gen_pred_locs_xssa.R --path_cfig_pred "{home_dir}/git/formulation-selector/path/to/pred_config.yaml"
#' }
#' # When wanting to randomly subsample from a dataset, set the total # of samples and optionally the seed number
#' \dontrun{Rscript gen_pred_locs_xssa.R --path_cfig_pred "{home_dir}/git/formulation-selector/path/to/pred_config.yaml"
#'                                       --subsamp_n 20
#'                                       --subsamp_seed 123
#' }
#'

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
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa/xssa_pred_config.yaml")
  subsamp_n <- ifelse(length(args) >= 2, base::as.integer(args[2]), 20) #subsamp_n <- 20
  subsamp_seed <- ifelse(length(args) >=3, base::as.integer(args[2]), 432) # subsamp_seed <- 432

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
  path_raw_config <- glue::glue("{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa/xssa_config.yaml")



  # --------------------------- INPUT DATA READ -------------------------------- #
  raw_cfg <- yaml::read_yaml(path_raw_config)

  # Read in the xssa dataset, remove extraneous spaces, subselect USGS gages
  path_data <- glue::glue(raw_cfg[['file_io']][[grep("path_data",raw_cfg[['file_io']])]]$path_data)
  df_all_xssa <- utils::read.csv(path_data,sep = ';', colClasses=c("basin_id"="character"))

  # Read in the CAMELS dataset so we can pick non-CAMELS locations for testing
  path_camels <-  glue::glue(raw_cfg[['file_io']][[grep("path_camels",raw_cfg[['file_io']])]]$path_camels)
  df_camels <- utils::read.csv(path_camels,sep=';',colClasses=c("gauge_id"="character"))

  # --------------------------- INPUT DATA MUNGE ------------------------------- #
  # Remove extraneous spaces, subselect USGS gages from the xssa dataset
  df_all_xssa <- utils::read.csv(path_data,sep = ';', colClasses=c("basin_id"="character"))
  df_all_xssa[['basin_id']] = base::gsub("\\ ","",df_all_xssa[['basin_id']])
  df_all_xssa[['basin_id_num']] <- as.numeric(df_all_xssa[['basin_id']] )
  df_us_xssa <- df_all_xssa %>% tidyr::drop_na() # Canadian gages have letters


  non_intersect_xssa <- base::setdiff(df_us_xssa$basin_id, df_camels$gauge_id)
  non_intersect_camels <- base::setdiff(df_camels$gauge_id,df_all_xssa$basin_id)

  # Randomly sample non_intersecting, since this is just for testing
  if(subsamp_n > 0){
    set.seed(subsamp_seed)
    samp_locs <- base::sample(non_intersect_xssa,size=20)
  } else {
    samp_locs <- non_intersect_xssa
  }
  ############################ END CUSTOM MUNGING ##############################

  message(glue::glue("Processing {length(samp_locs)} locations"))
  # ---------------------- Grab all needed attributes ---------------------- #
  # Now acquire the attributes:
  dt_site_feat <- proc.attr.hydfab::proc_attr_gageids(gage_ids=samp_locs,
                                                   featureSource='nwissite',
                                                   featureID='USGS-{gage_id}',
                                                   Retr_Params=Retr_Params,
                                                   lyrs=lyrs,
                                                   overwrite=overwrite)



  for(ds in datasets){
    path_nldi_out <- glue::glue(path_meta)

    proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat,
                                           path_meta = path_nldi_out)
  }


}


main()


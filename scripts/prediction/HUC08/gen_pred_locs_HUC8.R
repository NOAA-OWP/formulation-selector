#' @title Generate attributes for specified HUC-level prediction locations
#' @author Lauren Bolotin
#' @description Prediction locations largely generated from sub_hf_huc_conus()
#' which identifies the most downstream stream segment in each HUC at the 
#' specified level. Locations with terminal nexi are grabbed separately.
#' @param path_cfig_pred The path to the prediction configuration yaml file. May use glue formatting for {home_dir}
#' @param dir_base_huc The directory containing analyses on HUC08 data. Created using https://github.com/bolotinl/NWM_process_mapping
#' @examples
#' \dontrun{Rscript gen_pred_locs_HUC8.R "{repo_dir}formulation-selector/scripts/eval_ingest/xssa_NWM_domain/xssanwm_pred_config.yaml" 
#' }

library(dplyr)
library(glue)
library(tidyr)
library(yaml)
library(sf)
library(future) #IMPORTANT Must call to avoid import error
library(future.apply) #IMPORTANT Must call to avoid import error


main <- function(){
  args <- commandArgs(trailingOnly = TRUE)
  # Check if the input argument is provided
  if (length(args) < 1) {
    stop("Input prediction configuration file must be specified")
  }
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml")
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
  # TODO: incorporate new function for parsing config file (Guy will provide example)
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
  print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
  print("WARNING! THIS SECTION IS HIGHLY MANUAL AND REQUIRES USER-DRIVEN DATA MUNGING UNTIL THIS SECTION IS FORMALIZED.")
  
  # TODO: see if this should always be the case:
  dir_save_nhdp <- NULL
  
  if (!file.exists(glue::glue('{home_dir}/noaa/regionalization/data/analyses/basin_selection/conus_nextgen_huc8_comids.csv'))){
    message(glue::glue("Generating IDs for HUC level 8..."))
    proc.attr.hydfab::sub_hf_huc_conus(huc_level = 8)
  } else{
    message(glue::glue("IDs for HUC level 8 already exist. Retrieving..."))
    df_huc08 <- read.csv(glue::glue('{home_dir}/noaa/regionalization/data/analyses/basin_selection/conus_nextgen_huc8_comids.csv'))
  }
  df_huc08 <- df_huc08 %>% dplyr::select(comid)
  df_huc08$source <- 'gen_pred_locs_HUC8.R' # Add source column
  df <- base::rbind(df_huc08)
  df <- unique(df)
  col_comid <- 'comid'
  
  ############################ END CUSTOM MUNGING ##############################
  for(ds in datasets){
    message(glue::glue("Processing {nrow(df)} locations"))
    # ---------------------- Grab all needed attributes ---------------------- #
    
    # --- Create the path to the geopackage:
    # Define the standardized path to the geopackage based on the input dataset
    path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
      dir_std_base = Retr_Params$paths$dir_std_base,ds = ds)
    
    ls_site_feat <- list()
    seq_nums <- c(seq(from=1,nrow(df),390),nrow(df))[-1]
    ctr <- 0
    for(seq_num in seq_nums){ #
      ctr <- ctr + 1
      sub_df <- df[1:seq_num,]
      # The unique comids for each location
      gage_ids <- base::unique(sub_df[[col_comid]])
      base::message(glue::glue(
        "Acquiring attributes for seq_num {seq_num} of {nrow(df)}"))
      
      # Now acquire the attributes:
      dt_site_feat <- proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_ids,
                                                          featureSource='comid',
                                                          featureID='{gage_id}',
                                                          Retr_Params=Retr_Params,
                                                          path_save_gpkg = path_save_gpkg,
                                                          lyrs='network',
                                                          overwrite=FALSE)
      ls_site_feat[[ctr]] <- dt_site_feat
    }
    
    base::message(glue::glue("Completed attribute retrieval to
    {Retr_Params$paths$dir_db_attrs}
    & outlet coordinate retrieval to
    {path_save_gpkg} "))
    
    # Combine all chunked site feature data
    dt_site_feat_all <- data.table::rbindlist(ls_site_feat)
    # Generate the prediction metadata
    path_nldi_out <- glue::glue(path_meta)
    proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat_all,
                                           path_meta = path_nldi_out)
    
    # Generate the NLDI full geometries ( outlet, flowlines, catchment )
    if(base::is.null(dir_save_nhdp)){
      dir_save_nhdp <- base::dirname(path_save_gpkg)
    }
  }
}

main()


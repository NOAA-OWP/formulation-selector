#' @title Generate attributes for prediction locations used in the process mapping exercise for RFC locations
#' @author Guy Litt
#' @description Prediction locations largely generated from Lauren Bolotin's
#' analyses documented here (non-public) https://github.com/bolotinl/NWM_process_mapping
#' @details Read the following locations:
#' @seealso Final_COMID_Selection.R representing approximate HUC08 locations
#' https://github.com/bolotinl/NWM_process_mapping/blob/main/Final_Comid_Selection.R
#' @seealso flow.comid.terminal.R representing terminal locations (e.g. flowlines into coasts)
#' https://github.com/bolotinl/NWM_process_mapping/blob/guy/flow.comid.terminal.R
#' @reference https://www.nature.com/articles/s41467-022-28010-7
#' @param path_cfig_pred The path to the prediction configuration yaml file. May use glue formatting for {home_dir}
#' @param dir_base_huc08 The directory containing analyses on HUC08 data. Created using https://github.com/bolotinl/NWM_process_mapping
#' @examples
#' \dontrun{Rscript gen_pred_locs_xssaus_map.R "{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml" 
#' "{home_dir}/noaa/regionalization/data/analyses/basin_selection" "{home_dir}/git/formulation-selector/"
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
  if (length(args) < 2) {
    stop("Input prediction configuration file must be specified")
  }
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/formulation-selector/scripts/eval_ingest/xssa_us/xssaus_pred_config.yaml")
  dir_base_huc08 <- glue::glue(as.character(args[2]))# dir_base_huc08 <- dir_repo <- glue::glue("{home_dir}/noaa/regionalization/data/analyses/basin_selection" 
  dir_repo <- glue::glue(as.character(args[3])) #dir_repo <- glue::glue("{home_dir}/git/formulation-selector/")
  # Read in config file
  if(!base::file.exists(path_cfig_pred)){
    stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
  }

  # TODO consider defining dir_save_nhdp inside prediction config. Presently we just save the geometries (outlet, flowlines, catchment) in the dataset directory
  dir_save_nhdp <- NULL

  cfig_pred <- yaml::read_yaml(path_cfig_pred)
  ds_type <- base::unlist(cfig_pred)[['ds_type']]
  write_type <- base::unlist(cfig_pred)[['write_type']]
  path_meta <- base::unlist(cfig_pred)[['path_meta']] # The filepath of the file that generates the list of comids used for prediction
  # READ IN ATTRIBUTE CONFIG FILE
  path_attr_config <- file.path(base::dirname(path_cfig_pred),unlist(cfig_pred)[['name_attr_config']])

  #path_attr_config <- glue::glue(cfig_pred[['path_attr_config']])
  cfig_attr <- yaml::read_yaml(path_attr_config)

  # Defining directory paths as early as possible:
  io_cfig <- cfig_attr[['file_io']]
  dir_base <- glue::glue(base::unlist(io_cfig)[['dir_base']])
  dir_std_base <- glue::glue(base::unlist(io_cfig)[['dir_std_base']])
  dir_db_hydfab <- glue::glue(base::unlist(io_cfig)[['dir_db_hydfab']])
  dir_db_attrs <- glue::glue(base::unlist(io_cfig)[['dir_db_attrs']])

  # ----------------------- TRANSFORMATION CONFIGURATION --------------------- #
  path_attr_config <- base::file.path(base::dirname(path_cfig_pred),
                                base::unlist(cfig_pred)[['name_tfrm_config']])
  path_tfrm_script <- glue::glue(base::unlist(cfig_pred)[['path_tfrm_script']])
  conda_env <- base::unlist(cfig_pred)[['conda_env']]

  # TODO auto-determine the transformation config file from the prediction (or attribute?) config
  # TODO perform transformations during attribute grabbing!
  # TODO add in new changes from xssaus_attr_config.yaml


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
  # Read file and remove poorly-parsed rows
  # HUC08 approximations based on comids generated by Lauren Bolotin in https://github.com/bolotinl/NWM_process_mapping
  print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
  print("WARNING! THIS SECTION IS HIGHLY MANUAL AND REQUIRES USER-DRIVEN DATA MUNGING UNTIL THIS SECTION IS FORMALIZED.")
  # Generated by Final_COMID_Selection.R
  df_huc08 <- read.csv(glue::glue("{dir_base_huc08}/comids_highest_hf_hydroseq.csv"))
  col_comid_huc08 <- "hf_id"
  path_gpkg_comids <- glue::glue("{dir_base_huc08}terminal_nonhuc08_with_comids.gpkg")
  # Generated using flow.comid.terminal.R in https://github.com/bolotinl/NWM_process_mapping
  path_gpkg_comids <- glue::glue("{dir_base_huc08}/terminal_locs/nhdp_cat_line_out_tnx_above10sqkm.gpkg") 
  #sf::st_layers(path_gpkg_comids)
  df_tnx <- sf::st_read(path_gpkg_comids,"outlet")
  col_comid_tnx <- 'comid'


  # Combine huc08 and terminal comids:
  df1 <- base::data.frame(comid = df_huc08[,col_comid_huc08])
  df2 <-df_tnx %>% base::as.data.frame() %>% select('comid')
  dfall <- rbind(df1,df2)
  df <- base::data.frame(comid = unique(dfall$comid),
                         source = "gen_pred_locs_xssaus_map.R")
  col_comid <- 'comid'
  
 
  # Read in locations generated by ID_term_coast.R in bolotinl/NWM_process_mapping/
  path_huc08_10sqkm <- glue::glue("{dir_base_huc08}/tnx_comids_highest_hf_hydroseq.csv") 
  df_huc08_10sqkm <- read.csv(path_huc08_10sqkm)
    
  idxs_need <- which(!df_huc08_10sqkm$hf_id %in% df[,col_comid])
  
  df_add <- base::data.frame(comid=df_huc08_10sqkm$hf_id[idxs_need],
                             source = "gen_pred_locs_xssaus_map.R")
  df <- base::rbind(df,df_add)

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

    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #
    library(reticulate)

    # TODO add in attribute transformation of prediction variables by calling python transformation script
    # TODO make sure user activates appropriate conda environment before running!

    path_tfrm_script <- glue::glue("{dir_repo}/pkg/fs_algo/fs_algo/fs_tfrm_attrs.py")
    path_tfrm_config <- glue::glue("{dir_repo}/scripts/eval_ingest/xssa_us/xssaus_attrs_tform.yaml")
    if(!file.exists(path_tfrm_script)){
      stop(glue::glue("Does not exist: {path_tfrm_script}"))
    }
    if(!file.exists(path_tfrm_config)){
      stop(glue::glue("Does not exist: {path_tfrm_config}"))
    }
    text_script <- glue::glue('python {path_tfrm_script} "{path_tfrm_config}"')
    source(text_script)

    # Run python function from the tfrm_attr.py file:
    reticulate::use_condaenv(condaenv="py312",required=TRUE) # The anaconda environment that has the fs_algo RaFTS package installed
    fta <- reticulate::import("fs_algo.tfrm_attr")
    result <- try(fta$tfrm_attr_comids_wrap(comids = df[,col_comid],
                                        path_tfrm_cfig = path_tfrm_config))
    if("try-error" %in% class(result)){
      warning(glue::glue("Could not call python transformation script using
      R's reticulate. To complete transformations, run this transformation
      script directly from the shell or terminal:
      {path_tfrm_script}") )
    }

    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #
    # Generate the NLDI full geometries ( outlet, flowlines, catchment )
    if(base::is.null(dir_save_nhdp)){
      dir_save_nhdp <- base::dirname(path_save_gpkg)
    }

    ls_compiled_data <- proc.attr.hydfab::dl_nhdplus_geoms_wrap(df=df,col_id=col_comid,
                                              dir_save_nhdp = dir_save_nhdp,
                                              filename_str=paste0(glue::glue("{datasets}_{ds_type}")),
                                              id_type = "comid",
                                              keep_cols="all",
                                              seq_size = 391,
                                              overwrite_chunk=FALSE)

    base::message(glue::glue(
    "Completed geopackage saving of outlet, flowlines, and catchment boundaries
    to {dir_save_nhdp} ") )
  } # End loop over datasets
}

main()


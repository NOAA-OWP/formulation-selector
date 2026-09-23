#' @title Retrieve attributes for RFC locations (as available!)
#'
#' @author Guy Litt
#' @description Given the comids of RFC forecast locations, grab NHDPlus
#' catchment attributes
#' @details Sections of code embedded inside if(FALSE){} were created to
#' munge through the patchy nature of NLDI connection limits. If intended to
#' run continuously, set `pause_nldi_conns` to TRUE and let it run for about 9
#' hours or so. Once the data have been acquired, pause_nldi_conns may be set to
#' FALSE and full generation of the prediction metadata parquet file will take
#' tens of minutes instead (because some locations will never be found)
#' @example \dontrun{Rscript gen_pred_locs_rfcs_bm25test.R
#' "{home_dir}/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm25_pred_config.yaml"
#' "{home_dir}/git/rafts/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt"}

# Changelog/contributions
#. 2025-05-21 adapted from gen_pred_locs_rfcs.R for bm25 oconus testing
#. 2025-06-10 in a stable form
library(nhdplusTools)
library(proc.attr.hydfab)
library(dplyr)
library(glue)
library(tidyr)
library(yaml)
library(future)
library(future.apply)
library(logr)

main <- function(){
  args <- commandArgs(trailingOnly = TRUE)
  # Check if the input argument is provided
  if (length(args) < 2) {
    stop("Input prediction configuration filepath and full path to nws_nwm_crosswalk.txt must be specified.")
  }
  pause_nldi_conns <- FALSE # Should NLDI connections be paused?
  testing_dataset <- FALSE
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm25_pred_config.yaml")
  path_nwm_crosswalk <- glue::glue(as.character(args[2])) #path_nwm_crosswalk <- "~/git/rafts/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt"
  # Read in config file
  if(!base::file.exists(path_cfig_pred)){
    stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
  }
  cfig_pred <- yaml::read_yaml(path_cfig_pred)
  print(names(cfig_pred))
  ds_type <- base::unlist(cfig_pred)[['ds_type']] # Used to generate path_meta
  write_type <- base::unlist(cfig_pred[['write_type']]) # Used to generate path_meta
   # READ IN ATTRIBUTE CONFIG FILE

  name_attr_config <- cfig_pred[['name_attr_config']]
  path_attr_config <- proc.attr.hydfab::build_cfig_path(path_cfig_pred,name_attr_config)

  # ------------------------ ATTRIBUTE CONFIGURATION --------------------------- #
  Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
  dir_log <- proc.attr.hydfab::std_dir_logs(Retr_Params$paths$dir_db_attrs)
  path_log <- proc.attr.hydfab::std_path_log(dir_log,path_attr_config,script = "gen_pred_locs_rfcs_bm25test")
  logr::log_open(path_log)#file_name=base::basename(path_log),logdir=base::dirname(path_log))
  logr::log_print(glue::glue("Running rafts_attrs_miss.R {path_attr_config} at {Sys.time()}"))
  if(base::length(args)!=2){
    logr::log_print("Expected to have two arguments in
                  Rscript gen_pred_locs_rfcs_bm25test.R
                  {home_dir}/git/rafts/scripts/workflow_configs/legacy/bm_test25/bm25_pred_config.yaml
                  {home_dir}/git/rafts/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt",
                    level="ERROR")
  }
  logr::log_print("Retrieving comid-attribute pairings for RFC locations using gen_pred_locs_rfcs_bm25test.R",level="INFO")
  #-----------------------------------------------------

  message(glue::glue("Parsed the attribute config file {path_attr_config}"))

  datasets <- Retr_Params$datasets
  dir_std_base <- Retr_Params$paths$dir_std_base

  for(ds in datasets){ # {ds} used to generate path_meta
    message(glue::glue("Processing dataset {ds}"))
    # Populate path_meta using the pre-defined ds, dir_std_base, ds_type, write_type
    path_meta <- glue::glue(Retr_Params$paths$path_meta) # The filepath of the file that generates the list of comids used for prediction
    if(is.null(path_meta)){
      stop("Could not populate path_meta. Investigate glue formatting.")
    }

    ###################### DATASET-SPECIFIC CUSTOM MUNGING #########################
    # USER INPUT: Paths to relevant config files
    # Read file and remove poorly-parsed rows
    if(base::grepl("nws_nwm_crosswalk.txt",path_nwm_crosswalk)){
      message("Processing the nws_nwm_crosswalk.txt for prediction")
      df <- read.delim(file=path_nwm_crosswalk, # Obtained from Gautam Sood at OWP: a file of all RFC station locations
                       skip=0,sep = "|",col.names = c("nws_station_id","comid"))
      df <- df[-base::grep("-------+-----", df$nws_station_id),]
      df_nwm <- df[-which(base::is.na(df$comid)),]

      df_nwm$nws_station_id <- base::gsub(" ","",df_nwm$nws_station_id)

      # Read in the HADS sites
      df_hads <- proc.attr.hydfab:::read_noaa_hads_sites()
      df_cmbo_hads <- base::merge(x=df_nwm,y=df_hads,by.x = "nws_station_id", by.y="lid",all.x = TRUE)
      df_cmbo_miss_h <- df_cmbo_hads[which(is.na(df_cmbo_hads$GOES)),]

      # Read in NWPS:
      df_nwps <- proc.attr.hydfab::read_noaa_nwps_gauges()
      df_cmbo_nwps <- base::merge(x=df_nwm,y=df_nwps, by.x = "nws_station_id",by.y="nws_shef_id", all.x=TRUE)
      df_cmbo_miss_n <- df_cmbo_nwps[which(is.na(df_cmbo_nwps$usgs_id)),]

      # The unknown locations and known locations
      nws_ids_unkn <- base::intersect(df_cmbo_miss_n$nws_station_id,df_cmbo_miss_h$nws_station_id)
      nws_ids_have <- base::which(!df_nwm$nws_station_id %in% nws_ids_unkn)

      # TODO identify which locations are oCONUS and consider how to explicitly process using hf_uid
      oconus_states <- c("AK","HI","PR","VI")
      base::which(df_cmbo_nwps$state %in% oconus_states)
      # Next step: refactor proc_attr_gageids to allow different featureSources to be called separately (one for hf_uid, one for comid)
      #. One idea - allow queries using lat/lon when first query fails (e.g. comid) Would need to make sure to reduce NLDI hits per hour in this case.
      # TODO allow option to pass in lat/lon to proc_attr_gageids to avoid having to query locations

      if(FALSE){
        # Retrieve state postal codes (this takes a few mins)
        hads_postal <- lapply(1:nrow(df_cmbo_hads), function(i)  proc.attr.hydfab::retr_state_terr_postal(
          lat=df_cmbo_hads$latitude[i],lon=df_cmbo_hads$longitude[i]))
        df_cmbo_hads$state <- base::unlist(hads_postal)
        #  Observations: No HI locations recognized after HADS merge: grep("HI", df_cmbo_hads$state)
      }
      # --------------------
      # Simplify - just pick everything with a USGS gage id from NWPS
      df <- df_cmbo_nwps[!base::is.na(df_cmbo_nwps$usgs_id),]
      # --------------------
      col_comid <- 'usgs_id'
      featureSource <- "nwissite"
      featureID <- "USGS-{gage_id}"



      if(FALSE){ # short-term munging, reducing the total df based on known data availability
        path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
          dir_std_base = Retr_Params$paths$dir_std_base,ds = Retr_Params$datasets[[1]])
        gpk <- sf::st_read(path_save_gpkg)
        need_ids <- lapply(df$usgs_id, function(x) base::paste0("USGS-",x)) %>% unlist()
        reduced_df <- df[which(!need_ids %in% gpk$featureID),]
        df <- reduced_df
      }

    } else {
      stop("NOT PROCESSING - EDIT HERE")
      df <- read.csv(path_nwm_crosswalk)
      col_comid <- "hf_id"
      featureSource <- "comid"
      featureID <- "{gage_id}"
    }

    # Reduce the df:
    if(base::any(base::duplicated(df[[col_comid]]))){
      df <- df[-base::which(base::duplicated(df[[col_comid]])),]
    }

    ############################ END CUSTOM MUNGING ##############################

    message(glue::glue("Processing {nrow(df)} locations"))
    # ---------------------- Grab all needed attributes ---------------------- #
    # --- Create the path to the geopackage:
    # Define the standardized path to the geopackage based on the input dataset
    path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
      dir_std_base = Retr_Params$paths$dir_std_base,ds = ds)

    if(testing_dataset){
      gage_ids <- c("15294005","50147800","50043800")

      # Problematic locations with NLDI queries that need further investigation
      gage_ids <- c("02339400","08170950","390707081443202","15200280",
                  "15292000","15266150","06145500","15290000","15284000","0165258890",
                  "02393500","15292800","15292700","15272380","15266110","05114000")
      featureSource <- "nwissite"
      featureID <- "USGS-{gage_id}"
      Retr_Params$paths$path_hf <- "~/noaa/hydrofabric/v2.2/ls_conus.gpkg"
      test_df <- df[which(df$usgs_id %in% gage_ids),]

      # TODO add xy location subsetter, and use it for calling hfsubsetR::get_subset()

      # TODO convert x and y columns to geopackage geometry column as a pre-proecessor for retr_hf_id_xy()

      test_df$geometry <- sf::st_as_sf(test_df,coords = c("longitude","latitude"))






      dt_site_feat <- proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_ids,
                                         featureSource=featureSource,
                                         featureID=featureID,
                                         Retr_Params=Retr_Params,
                                         path_save_gpkg = path_save_gpkg,
                                         lyrs='network',
                                         overwrite=FALSE)

      dt_site_feat[,c("featureID","featureSource","gage_id")] %>% unique()

    } else { # Standard processing
      tot_increment <- 50
      seq_nums <- base::c(base::seq(from=1,nrow(df),tot_increment),nrow(df))[-1]
      seq_num_bgn <- 1
      ls_dt_site_feat <- list()
      ctr <- 0
      for(seq_num in seq_nums){
        print(" ----------------------------------------------------- ")
        print(glue::glue("Acquiring {seq_num} of {nrow(df)}"))
        ctr <- ctr+1
        sub_df <- df[seq_num_bgn:seq_num,]
        seq_num_bgn <- seq_num+1
        # The unique comids for each location
        gage_ids <- base::unique(sub_df[[col_comid]])


        # Now acquire the attributes:
        sub_dt_site_feat <- try(proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_ids,
                                                            featureSource=featureSource,
                                                            featureID=featureID,
                                                            Retr_Params=Retr_Params,
                                                            path_save_gpkg = path_save_gpkg,
                                                            lyrs='network',
                                                            overwrite=FALSE))
        if(!"try-error" %in% class(sub_dt_site_feat)){
          ls_dt_site_feat[[ctr]] <- sub_dt_site_feat
        } else { # Reduce increments to gageids 1 by 1 in lieu of large chunks:
          ls_subsub <- list()
          for(gage_id in gage_ids){
            subsub_dt_site_feat <- try(proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_id,
                                                                        featureSource=featureSource,
                                                                        featureID=featureID,
                                                                        Retr_Params=Retr_Params,
                                                                        path_save_gpkg = path_save_gpkg,
                                                                        lyrs='network',
                                                                        overwrite=FALSE))
            if(!"try-error" %in% class(subsub_dt_site_feat)){
              ls_subsub[[gage_id]] <- subsub_dt_site_feat
            } else {
              print(glue::glue("skipping gage_id : {gage_id}"))
            }
            ls_dt_site_feat[[ctr]] <- data.table::rbindlist(ls_subsub,fill=TRUE)
          }
        }
        if(pause_nldi_conns){#base::any(base::grepl("usgs_vars",base::names(Retr_Params$vars)))){
          # will be hitting NLDI and need to limit that
          max_inc_per_hr <- 380  # max 400 NLDI queries per hour
          frac_inc_per_hr <- tot_increment/max_inc_per_hr
          Sys.sleep(60*61*frac_inc_per_hr)
        }
      }
    }
    # -------------generate the prediction.parquet mapper
    dt_site_feat <- data.table::rbindlist(ls_dt_site_feat)
    proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat,
                                           path_meta = path_meta)



  }
}

main()

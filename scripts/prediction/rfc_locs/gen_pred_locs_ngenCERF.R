#' @title Retrieve attributes for Headwater Basin gaged locations under
#' consideration for ngen-CERF
#' @author Guy Litt
#' @description Given the gageids of ngenCERF forecast locations, grab NHDPlus
#' catchment attributes to use for prediction (particularly the xSSA process sensitivities)
#' @details Sections of code embedded inside if(FALSE){} were created to
#' munge through the patchy nature of NLDI connection limits. If intended to
#' run continuously, set `pause_nldi_conns` to TRUE and let it run for about 9
#' hours or so. Once the data have been acquired, pause_nldi_conns may be set to
#' FALSE and full generation of the prediction metadata parquet file will take
#' tens of minutes instead (because some locations will never be found)
#' @example \dontrun{Rscript gen_pred_locs_rfcs_bm25test.R
#' "{home_dir}/git/rafts/scripts/workflow_configs/legacy/xssa_us/xssaus_pred_config.yaml"
#' "{home_dir}/noaa/regionalization/data/analyses/basin_selection/HeadwaterBasinGages_ngenCERF_PI3_2024-12-09Calibratable.csv"}

# Changelog/contributions
#. 2025-05-21 adapted from gen_pred_locs_rfcs.R for bm25 oconus testing

library(nhdplusTools)
library(proc.attr.hydfab)
library(dplyr)
library(glue)
library(tidyr)
library(yaml)
library(future)
library(future.apply)


main <- function(){
  args <- commandArgs(trailingOnly = TRUE)
  # Check if the input argument is provided
  if (length(args) < 2) {
    stop("Input prediction configuration filepath and full path to nws_nwm_crosswalk.txt must be specified.")
  }
  pause_nldi_conns <- FALSE
# Should NLDI connections be paused?

  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/rafts/scripts/workflow_configs/legacy/xssangencerf/xssangencerf_pred_config.yaml")
  path_file_read <- glue::glue(as.character(args[2])) #path_file_read <- "~/noaa/regionalization/data/analyses/basin_selection/HeadwaterBasinGages_ngenCERF_PI3_2024-12-09Calibratable.csv"
  # Read in config file
  if(!base::file.exists(path_cfig_pred)){
    stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
  }
  cfig_pred <- yaml::read_yaml(path_cfig_pred)
  ds_type <- base::unlist(cfig_pred)[['ds_type']]
  write_type <- base::unlist(cfig_pred[['write_type']])
   # READ IN ATTRIBUTE CONFIG FILE

  name_attr_config <- cfig_pred[['name_attr_config']]
  path_attr_config <- proc.attr.hydfab::build_cfig_path(path_cfig_pred,name_attr_config)

  # ------------------------ ATTRIBUTE CONFIGURATION --------------------------- #
  Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
  message(glue::glue("Parsed the attribute config file {path_attr_config}"))

  datasets <- Retr_Params$datasets
  dir_std_base <- Retr_Params$paths$dir_std_base
  # ds <- datasets[1]
  for(ds in datasets){
    message(glue::glue("Processing dataset {ds}"))
    # Populate path_meta using the pre-defined ds, dir_std_base, ds_type, write_type
    path_meta <- glue::glue(Retr_Params$paths$path_meta) # The filepath of the file that generates the list of comids used for prediction
    if(is.null(path_meta)){
      stop("Could not populate path_meta. Investigate glue formatting.")
    }

    ###################### DATASET-SPECIFIC CUSTOM MUNGING #########################
    # path_file_read <- "~/noaa/regionalization/data/analyses/basin_selection/HeadwaterBasinGages_ngenCERF_PI3_2024-12-09Calibratable.csv"
    df <- read.csv(path_file_read)
    col_comid <- "Gage.ID"
    featureSource <- "nwissite"
    featureID <- "USGS-{gage_id}"
    if(TRUE){ # temporarily subset to just CONUS locations
      df <- df[df$Domain == "CONUS",]
    }

    ############################ END CUSTOM MUNGING ##############################

    message(glue::glue("Processing {nrow(df)} locations"))
    # ---------------------- Grab all needed attributes ---------------------- #
    # --- Create the path to the geopackage:
    # Define the standardized path to the geopackage based on the input dataset
    path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
      dir_std_base = Retr_Params$paths$dir_std_base,ds = ds)

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
    # -------------generate the prediction.parquet mapper
    dt_site_feat <- data.table::rbindlist(ls_dt_site_feat)
    proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat,
                                           path_meta = path_meta)



  }
}

main()

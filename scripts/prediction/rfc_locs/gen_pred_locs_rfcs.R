#' @title Retrieve attributes for RFC locations (as available!)
#' @author Guy Litt
#' @description Given the comids of RFC forecast locations, grab NHDPlus
#' catchment attributes
#' @example \dontrun{gen_pred_locs_rfcs.R
#' "{home_dir}/git/rafts/scripts/workflow_configs/legacy/xssa_us/xssaus_pred_config.yaml"
#' "~/git/rafts/scripts/prediction/rfc_locs/nws_nwm_crosswalk.txt"}


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
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  path_cfig_pred <- glue::glue(as.character(args[1])) # path_cfig_pred <- glue::glue("{home_dir}/git/rafts/scripts/workflow_configs/legacy/xssa_us/xssaus_pred_config.yaml")
  path_nwm_crosswalk <- glue::glue(as.character(args[2]))
  # Read in config file
  if(!base::file.exists(path_cfig_pred)){
    stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
  }
  cfig_pred <- yaml::read_yaml(path_cfig_pred)
  ds_type <- base::unlist(cfig_pred)[['ds_type']]
  write_type <- base::unlist(cfig_pred)[['write_type']]
  path_meta <- base::unlist(cfig_pred)[['path_meta']] # The filepath of the file that generates the list of comids used for prediction
  # READ IN ATTRIBUTE CONFIG FILE

  name_attr_config <- cfig_pred[['name_attr_config']]
  path_attr_config <- proc.attr.hydfab::build_cfig_path(path_cfig_pred,name_attr_config)

  # ------------------------ ATTRIBUTE CONFIGURATION --------------------------- #
  cfig_attr <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
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
  Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
  datasets <- Retr_Params$datasets

  ###################### DATASET-SPECIFIC CUSTOM MUNGING #########################
  # USER INPUT: Paths to relevant config files
  # Read file and remove poorly-parsed rows
  if("nws_nwm_crosswalk.txt" %in% path_nwm_crosswalk){
    df <- read.delim(file=path_nwm_crosswalk, # Obtained from Gautam Sood at OWP: a file of all RFC station locations
                     skip=0,sep = "|",col.names = c("nws_station_id","comid"))
    df <- df[-base::grep("-------+-----", df$nws_station_id),]
    df <- df[-which(base::is.na(df$comid)),]
    col_comid <- 'comid'
    df$nws_station_id <- base::gsub(" ","",df$nws_station_id)

    # Read in the HADS sites
    df_hads <- proc.attr.hydfab:::read_noaa_hads_sites()
    df_cmbo_hads <- base::merge(x=df,y=df_hads,by.x = "nws_station_id", by.y="lid",all.x = TRUE)
    df_cmbo_miss_h <- df_cmbo_hads[which(is.na(df_cmbo_hads$GOES)),]

    # Read in NWPS:
    df_nwps <- proc.attr.hydfab::read_noaa_nwps_gauges()
    df_cmbo_nwps <- base::merge(x=df,y=df_nwps, by.x = "nws_station_id",by.y="nws_shef_id", all.x=TRUE)
    df_cmbo_miss_n <- df_cmbo_nwps[which(is.na(df_cmbo_nwps$usgs_id)),]

    # The unknown locations and known locations
    nws_ids_unkn <- base::intersect(df_cmbo_miss_n$nws_station_id,df_cmbo_miss_h$nws_station_id)
    nws_ids_have <- base::which(!df$nws_station_id %in% nws_ids_unkn)

    # TODO identify which locations are oCONUS and consider how to explicitly process using hf_uid
    oconus_states <- c("AK","HI","PR","VI")
    base::which(df_cmbo_nwps$state %in% oconus_states)
    # Next step: refactor proc_attr_gageids to allow different featureSources to be called separately (one for hf_uid, one for comid)
    #. One idea - allow queries using lat/lon when first query fails (e.g. comid) Would need to make sure to reduce NLDI hits per hour in this case.


    if(FALSE){
      # Retrieve state postal codes (this takes a few mins)
      hads_postal <- lapply(1:nrow(df_cmbo_hads), function(i)  proc.attr.hydfab::retr_state_terr_postal(
        lat=df_cmbo_hads$latitude[i],lon=df_cmbo_hads$longitude[i]))
      df_cmbo_hads$state <- base::unlist(hads_postal)
      #  Observations: No HI locations recognized after HADS merge: grep("HI", df_cmbo_hads$state)
    }


  } else { # HUC08 approximations based on comids generated by Lauren Bolotin
    df <- read.csv("~/noaa/regionalization/data/rfc_locs/comids_highest_hf_hydroseq.csv")
    col_comid <- "hf_id"
  }



  ############################ END CUSTOM MUNGING ##############################

  message(glue::glue("Processing {nrow(df)} locations"))
  # ---------------------- Grab all needed attributes ---------------------- #
  # --- Create the path to the geopackage:
  # Define the standardized path to the geopackage based on the input dataset
  path_save_gpkg <- proc.attr.hydfab::std_path_retr_gpkg_wrap(
    dir_std_base = Retr_Params$paths$dir_std_base,ds = Retr_Params$datasets[[1]])


  seq_nums <- c(seq(from=1,nrow(df),390),nrow(df))[-1]
  for(seq_num in seq_nums){
    sub_df <- df[1:seq_num,]
    # The unique comids for each location
    gage_ids <- base::unique(sub_df[[col_comid]])
    # Now acquire the attributes:
    dt_site_feat <- proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_ids,
                                                        featureSource='comid',
                                                        featureID='{gage_id}',
                                                        Retr_Params=Retr_Params,
                                                        path_save_gpkg = path_save_gpkg,
                                                        lyrs='network',
                                                        overwrite=FALSE)
    #Sys.sleep(60*61) # 400 NLDI queries per hour
  }

}

main()

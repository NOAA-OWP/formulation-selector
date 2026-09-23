#' @title Generate attributes for CAMELS basins
#' @description This script uses the proc.attr.hydfab package to acquire attributes
#' of interest.
#' @usage Rscript attr_gen_camels.R "~/git/formulation-selector/scripts/config/attr_gen_camels_config.yaml"
#'


library(dplyr)
library(glue)
library(tidyr)
library(yaml)
library(proc.attr.hydfab)

main <- function(){
  # Define args supplied to command line
  home_dir <- Sys.getenv("HOME")
  cmd_args <- commandArgs("trailingOnly" = TRUE)
  if(base::length(cmd_args)!=1){
    warning("Unexpected to have more than one argument in Rscript fs_attrs_grab.R /path/to/attribute_config.yaml.")
  }
  home_dir <- Sys.getenv("HOME")
  # Read in config file, e.g.
  path_config <- glue::glue(cmd_args[1]) # path_config <- "~/git/formulation-selector/scripts/config/attr_gen_camels_config.yaml"
  raw_config <- yaml::read_yaml(path_config)

  dir_std_base <- glue::glue(raw_config$dir_std_base)
  ds_type <- raw_config$ds_type
  datasets <- raw_config$datasets
  ############################ BEGIN CUSTOM MUNGING ############################

  # ----------------------=-- Read in CAMELS gage ids ------------------------ #
  path_gages_ii <- glue::glue(raw_config$path_in_gages_ii)
  dat_gages_ii <- read.csv(path_gages_ii)
  gage_ids <- base::lapply(1:nrow(dat_gages_ii), function(i)
    tail(strsplit(dat_gages_ii[i,],split = ' ',fixed = TRUE)[[1]],n=1)) |>
    unlist() |>
    lapply(function(x)
    gsub(pattern=".gpkg",replacement = "",x = x)) |>
    unlist() |>
    lapply( function(x) gsub(pattern = "Gage_", replacement = "",x=x)) |>
    unlist()

  utils::write.table(gage_ids,glue::glue(raw_config$path_out_gages_ii),row.names = FALSE,col.names = FALSE)

  # --------------------- Read in usgs NHD attribute IDs --------------------- #
  # Read desired usgs nhdplus attributes, stored in NOAA shared drive here:
  # https://docs.google.com/spreadsheets/d/1h-630L2ChH5zlQIcWJHVaxY9YXtGowcCqakQEAXgRrY/edit?usp=sharing
  attrs_nhd_df <- read.csv(glue::glue(raw_config$path_attrs_list_nhd))

  attrs_nhd <-   attrs_nhd_df$ID

  Retr_Params <- list(paths = list(dir_db_attrs = glue::glue(raw_config$dir_db_attrs),
                                   dir_std_base = glue::glue(raw_config$dir_std_base)),
                      vars = list(usgs_vars = attrs_nhd),
                      datasets = raw_config$datasets,
                      xtra_hfab = list(hfab_retr=FALSE))


  ############################ END CUSTOM MUNGING ##############################

  # ---------------------- Grab all needed attributes ---------------------- #
  # Now acquire the attributes:

  dt_comids <- proc.attr.hydfab::proc_attr_gageids(gage_ids=gage_ids,
                                                   featureSource='nwissite',
                                                   featureID='USGS-{gage_id}',
                                                   Retr_Params=Retr_Params,
                                                   overwrite=FALSE)

  # dir_metadata_out <- file.path(Retr_Params$paths$dir_std_base,Retr_Params$datasets)
  # dir.create(dir_metadata_out,recursive = TRUE,showWarnings = FALSE)
  ds <- datasets
  path_metadata <- file.path(glue::glue( "{dir_std_base}/{ds}/nldi_feat_{ds}_{ds_type}.csv"))
  proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat = dt_comids,
                                         path_meta = path_metadata)

  message(glue::glue("Completed attribute acquisition for {Retr_Params$paths$dir_db_attrs}"))
}


main()

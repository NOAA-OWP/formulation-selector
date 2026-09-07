
#' @title Query datasets for missing comid-attribute pairings
#' @description
#' Processing after rafts_attrs_grab.R may identify missing data, for example if
#' data are missing to perform attribute aggregation & transformation from
#' `rafts_tfrm_attrs.py`. This checks to see if those missing data can be
#' acquired.
#'
#' @seealso `rafts_tfrm_attrs.py`
# USAGE
# Rscript rafts_attrs_miss.R "path/to/attr_config.yaml"

# Changelog / Contributions
#   2024-11-18 Originally created, GL


# Read in attribute config file and extract the following:
library(proc.attr.hydfab)
library(dplyr)
library(future)
library(future.apply)
library(logr)
library(glue)
cmd_args <- commandArgs("trailingOnly" = TRUE)

if(base::length(cmd_args)!=1){
  warning("Unexpected to have more than one argument in Rscript rafts_attrs_grab.R /path/to/attribute_config.yaml.")
}

# Read in config file
path_attr_config <- cmd_args[1] # "~/git/rafts/scripts/workflow_configs/legacy/xssa/xssa_attr_config.yaml"

#-----------------------------------------------------
Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
dir_log <- proc.attr.hydfab::std_dir_logs(Retr_Params$paths$dir_db_attrs)
path_log <- proc.attr.hydfab::std_path_log(dir_log,path_attr_config)
logr::log_open(path_log)#file_name=base::basename(path_log),logdir=base::dirname(path_log))
logr::log_print(glue::glue("Running rafts_attrs_miss.R {path_attr_config} at {Sys.time()}"))
if(base::length(cmd_args)!=1){
  logr::log_print("Unexpected to have more than one argument in
                  Rscript rafts_attrs_miss.R /path/to/attribute_config.yaml.",
                  level="WARN")
}
logr::log_print("Querying datasets for missing comid-attribute pairings using rafts_attrs_miss.R",level="INFO")
#-----------------------------------------------------

# Run the wrapper function to read in missing comid-attribute pairings and search
#  for those data in existing databases.
proc.attr.hydfab::rafts_attrs_miss_mlti_wrap(path_attr_config)
logr::log_close()

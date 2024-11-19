
#' @title Query datasets for missing comid-attribute pairings
#' @description
#' Processing after fs_attrs_grab.R may identify missing data, for example if
#' data are missing to perform attribute aggregation & transformation from
#' `fs_tfrm_attrs.py`. This checks to see if those missing data can be
#' acquired.
#'
#' @seealso `fs_tfrm_attrs.py`
# USAGE
# Rscript fs_attrs_miss.R "path/to/attr_config.yaml"

# Changelog / Contributions
#   2024-11-18 Originally created, GL


# Read in attribute config file and extract the following:
library(proc.attr.hydfab)

cmd_args <- commandArgs("trailingOnly" = TRUE)

if(base::length(cmd_args)!=1){
  warning("Unexpected to have more than one argument in Rscript fs_attrs_grab.R /path/to/attribute_config.yaml.")
}

# Read in config file, e.g.  "~/git/formulation-selector/scripts/eval_ingest/SI/SI_attr_config.yaml"
path_attr_config <- cmd_args[1] # "~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attr_config.yaml"

# Run the wrapper function to read in missing comid-attribute pairings and search
#  for those data in existing databases.
proc.attr.hydfab::fs_attrs_miss_wrap(path_attr_config)


# proc_attr_mlti_wrap

# Call in the package
library(proc.attr.hydfab)
library(tidyverse)
library(dataRetrieval)

# Set important params (Retr_Params) ----------------------------------
home_dir <- Sys.getenv("HOME")
path_cfig_pred <- glue::glue("{home_dir}/Lauren/FSDS/rafts/scripts/workflow_configs/legacy/xssa_us/xssaus_pred_config.yaml")
subsamp_n <- 20 # how is this decided? see how this impacts processing
subsamp_seed <- 432

# Read in config file
if(!base::file.exists(path_cfig_pred)){
  stop(glue::glue("The provided path_cfig_pred does not exist: {path_cfig_pred}"))
}


cfig_pred <- yaml::read_yaml(path_cfig_pred)
ds_type <- base::unlist(cfig_pred)[['ds_type']]
write_type <- base::unlist(cfig_pred)[['write_type']]
path_meta <- base::unlist(cfig_pred)[['path_meta']] # The filepath of the file that generates the list of comids used for prediction


# ------------------------ ATTRIBUTE CONFIGURATION --------------------------- #
# READ IN ATTRIBUTE CONFIG FILE
name_attr_config <- cfig_pred[['name_attr_config']]
path_attr_config <- proc.attr.hydfab::build_cfig_path(path_cfig_pred,name_attr_config)

Retr_Params <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)


# Get COMIDS -------------------------------------
home_dir <- Sys.getenv("HOME")
path_cfig_pred <- glue::glue("{home_dir}/Lauren/FSDS/rafts/scripts/workflow_configs/legacy/xssa_us/xssaus_pred_config.yaml")

### intersect approach -----
file_list <- list.files(glue::glue("{home_dir}/Lauren/regionalization"), pattern = '*_hf_huc8_int.csv', full.names = TRUE)
# Remove oCONUS files, these will need to be processed separately
file_list <- file_list[!grepl("ak_", file_list)]

# Read in all these files and merge into one dataframe 
huc08_int_df <- do.call(rbind, lapply(file_list, function(file) {
  read.csv(file)
}))
huc08_int_df <- huc08_int_df %>% rename(id = hf_id) # Change this earlier on to avoid confusion

# Read in the CONUS hydrofab so we can get hydrofabr IDs/COMIDs for these nextgen hydrofabric IDs
hf_conus <- sf::st_read(glue::glue('{home_dir}/Lauren/hydrofabric/data/v2.2/conus_nextgen.gpkg'), layer = 'network')

# Subset for the IDs of interest
hf_conus <- hf_conus %>% 
  filter(id %in% huc08_int_df$id) 

# # See what is in hf_conus$id that is not in huc08_int_df$id
# hf_conus %>% 
#   filter(!id %in% huc08_int_df$id) %>% 
#   select(id) %>% 
#   distinct() %>% 
#   arrange(id)
# 
# # See vice versa
# huc08_int_df %>% 
#   filter(!id %in% hf_conus$id) %>% 
#   select(id) %>% 
#   distinct() %>% 
#   arrange(id)

# Join the two dataframes to get the COMIDs
# merged_df <- merge(huc08_int_df, hf_conus, by = "id")

# For each id, subset merged_df for the row where the hf_hydroseq is the lowest
# This allows us to get the hf_id/COMID for the most downstream stream segment
hf_conus_sub <- hf_conus %>%
  filter(id %in% huc08_int_df$id) 

hf_conus_sub <- hf_conus_sub %>%
  group_by(id) %>%
  slice(which.min(hf_hydroseq)) %>%
  ungroup()

# # Print the maximum number of times any "id" shows up in huc08_int_df
# max_count <- max(table(huc08_int_df$id))
# 
# # Identify which ones have this many entries
# ids_with_max_count <- names(which(table(huc08_int_df$id) == max_count))

comids <- unique(hf_conus_sub$hf_id)

# Grab attributes ------------------------------
# For some reason, running the following got this working
library(future)
library(future.apply)
dt_site_feat <- proc_attr_mlti_wrap(comids = comids, Retr_Params = Retr_Params,
                    lyrs = "network", overwrite = FALSE)


for(ds in datasets){
  path_nldi_out <- glue::glue(path_meta)

  proc.attr.hydfab::write_meta_nldi_feat(dt_site_feat=dt_site_feat,
                                         path_meta = path_nldi_out)
}

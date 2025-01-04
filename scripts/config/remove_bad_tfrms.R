library(arrow)
library(dplyr)
library(proc.attr.hydfab)
library(glue)

# Path to attribute configuration file
path_attr_config <- "~/git/formulation-selector/scripts/eval_ingest/xssa/xssa_attr_config.yaml"
attr_cfig <- proc.attr.hydfab::attr_cfig_parse(path_attr_config)
# List of bad attribute transformations
bad_vars <- c('TOT_WB5100_yr_np.mean')

# Directory containing transformation files
dir_db_attrs <-attr_cfig$paths$dir_db_attrs

# List all transformation files in the directory
all_tfrmattr_files <- base::list.files(path = dir_db_attrs, pattern = "*_tfrmattr.parquet")

for (fn_parq in all_tfrmattr_files) {
  filename_parq <- file.path(dir_db_attrs,fn_parq)
  # Read the Parquet file into a DataFrame

  attr_df_subloc <- try(arrow::read_parquet(filename_parq))
  if ("try-error" %in% base::class(attr_df_subloc)){
    next()
  }

  # Filter the DataFrame
  filtered_df <- attr_df_subloc %>%
    filter(!attribute %in% bad_vars) %>% distinct()

  # # Delete the original Parquet file
  # file_delete(filename_parq)
  if(nrow(filtered_df) < nrow(attr_df_subloc)){
    print(glue::glue("Removing {bad_vars} from {fn_parq}"))
    attr_df_subloc <- attr_df_subloc %>% distinct()
    if( nrow(attr_df_subloc) -nrow(filtered_df) != length(bad_vars) ){
      stop(glue::glue("Unexpected dimensional differences for {fn_parq}"))
    }
    # Write the filtered DataFrame back to Parquet
    arrow::write_parquet(filtered_df, filename_parq)
  }

}

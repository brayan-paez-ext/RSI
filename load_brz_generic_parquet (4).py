# Databricks notebook source
# MAGIC %sql
# MAGIC DROP TABLE IF EXISTS brewdat_uc_maz_dev.brz_maz_supply_sap_pr0.mx_afvv

# COMMAND ----------

import json

dbutils.widgets.text("brewdat_library_version", "v0.9.0", "01 - brewdat_library_version")
brewdat_library_version = dbutils.widgets.get("brewdat_library_version")
print(f"{brewdat_library_version = }")


dbutils.widgets.text("source_system", "sap_g_erp", "02 - source_system")
source_system = dbutils.widgets.get("source_system")
print(f"{source_system = }")

dbutils.widgets.text("source_table", "bsak", "03 - source_table")
source_table = dbutils.widgets.get("source_table")
print(f"{source_table = }")

dbutils.widgets.text("target_zone", "europe", "04 - target_zone")
target_zone = dbutils.widgets.get("target_zone")
print(f"{target_zone = }")

dbutils.widgets.text("target_business_domain", "supl", "05 - target_business_domain")
target_business_domain = dbutils.widgets.get("target_business_domain")
print(f"{target_business_domain = }")

dbutils.widgets.text("target_business_subdomain", "supl", "06 - target_business_subdomain")
target_business_subdomain = dbutils.widgets.get("target_business_subdomain")
print(f"{target_business_subdomain = }")

dbutils.widgets.text("target_database", "brz_eur_supl_sap_g_erp", "07 - target_database")
target_database = dbutils.widgets.get("target_database")
print(f"{target_database = }")

dbutils.widgets.text("target_table", "bsak", "08 - target_table")
target_table = dbutils.widgets.get("target_table")
print(f"{target_table = }")

dbutils.widgets.text("reset_stream_checkpoint", "false", "09 - reset_stream_checkpoint")
reset_stream_checkpoint = dbutils.widgets.get("reset_stream_checkpoint")
print(f"{reset_stream_checkpoint = }")

dbutils.widgets.text("source_raw_zone", "copec", "10 - source_raw_zone")
source_raw_zone = dbutils.widgets.get("source_raw_zone")
print(f"{source_raw_zone = }")

dbutils.widgets.text("source_system_raw", "sap_ecc", "11 - source_system_raw")
#source_system_raw = dbutils.widgets.get("source_system_raw")
source_system_raw = 'sap_pr3'
print(f"{source_system_raw = }")

dbutils.widgets.text("additional_parameters", " { \"partition_column\":  \"erdat\", \"partition_date_format\" : \"yyyyMM\" } ","12 - additional_parameters")
additional_parameters = dbutils.widgets.get("additional_parameters")
additional_parameters = json.loads(additional_parameters)
print(f"{additional_parameters = }")

# COMMAND ----------

import sys
from pyspark.sql import functions as F

# Import BrewDat Library modules and share dbutils globally
sys.path.append(f"/Workspace/Repos/brewdat_library/{brewdat_library_version}")
from brewdat.data_engineering import common_utils, lakehouse_utils, read_utils, transform_utils, write_utils
common_utils.set_global_dbutils(dbutils)

# Print a module's help
# help(read_utils)

# COMMAND ----------

# MAGIC %run "../set_project_context"

# COMMAND ----------

# Configure SPN for all ADLS access using AKV-backed secret scope
common_utils.configure_spn_access_for_adls(
    storage_account_names=[
        adls_raw_bronze_storage_account_name,adls_raw_storage_account_name,
    ],
    key_vault_name=key_vault_name, 
    spn_client_id=spn_client_id,
    spn_secret_name=spn_secret_name 
)



# COMMAND ----------

raw_location = f"{lakehouse_raw_root}/data/{target_zone}/{target_business_domain}/{source_system}/{source_table}"
print(f"{raw_location = }")

# COMMAND ----------

 target_location = lakehouse_utils.generate_bronze_table_location(
     lakehouse_bronze_root=lakehouse_bronze_root,
     target_zone=target_zone,
     target_business_domain=target_business_domain,
     source_system=source_system,
     table_name=target_table,
  
 )
 print(f"{target_location = }")

target_location= f"{lakehouse_bronze_root}/data/{target_zone}/{target_business_domain}/{source_system}/{target_table.lower()}"
print(f"{target_location = }")

# COMMAND ----------

import datetime as datetime
current_date = datetime.datetime.now()
current_date_str = current_date.strftime("%Y-%m-%d")
print(current_date_str)

# COMMAND ----------

import os
environment = os.getenv("ENVIRONMENT")
print(environment)

# COMMAND ----------

raw_df = (
    read_utils.read_raw_streaming_dataframe(
            file_format=read_utils.RawFileFormat.PARQUET,
            location=f"{raw_location}/*/*.parquet",
            schema_location=target_location,
            cast_all_to_string=True,
            handle_rescued_data=False,
            additional_options={
                    "cloudFiles.useIncrementalListing": "false",
            },
    )
    .withColumn("__src_file", F.input_file_name())
    .withColumn("__ref_date", F.to_date("TARGET_APPLY_DT", format="yyyy-MM-dd"))
    .withColumn("__partition_column", F.date_format(F.lit(current_date_str),additional_parameters['partition_date_format'] ).cast("int"))
    .transform(transform_utils.clean_column_names)
    .drop("aerunid", "aerecno", "aedattm","__process_date",)  # Columns to be dropped
    .transform(transform_utils.create_or_replace_audit_columns)
)
# display(raw_df)

# COMMAND ----------

from pyspark.sql.functions import lower
for col_name in raw_df.columns: 
    lower_col_name=col_name.lower()
    raw_df=raw_df.withColumnRenamed(col_name,lower_col_name)

for col_name in raw_df.columns:
    if col_name == 'opflag':
        col_name_changed = 'op_ind'
    else:
        col_name_changed = col_name
    
    raw_df=raw_df.withColumnRenamed(col_name,col_name_changed)

#display(raw_df)

# COMMAND ----------

if environment == 'qa' and source_table == 'mx_AFVV':
    spark.conf.set("spark.sql.files.ignoreMissingFiles", "true")

# COMMAND ----------

"""def create_table(raw_df):
    results = write_utils.write_stream_delta_table(
    df=raw_df,
    location=target_location,
    database_name=target_database,
    table_name=target_table,
    load_type=write_utils.LoadType.APPEND_ALL,
    partition_columns=["__partition_column"],
    schema_evolution_mode=write_utils.SchemaEvolutionMode.ADD_NEW_COLUMNS,
    enable_change_data_feed=True,
    enable_caching=False,
    reset_checkpoint=(reset_stream_checkpoint.lower() == "true"),
    )
    print(results)"""

# COMMAND ----------

"""if not spark.catalog.tableExists(f"brewdat_uc_maz_dev.{target_database}.{target_table}"):
    display(raw_df)
    raw_short = raw_df.filter(raw_df.target_apply_dt == F.to_date("2023-09-05", format="yyyy-MM-dd"))
    create_table(raw_short)
    create_table(raw_df)

else:
    output_df = get_data(start_date, end_date)
    update_table(output_df)"""

# COMMAND ----------

results = write_utils.write_stream_delta_table(
    df=raw_df,
    location=target_location,
    database_name=target_database,
    table_name=target_table,
    load_type=write_utils.LoadType.APPEND_ALL,
    partition_columns=["__partition_column"],
    schema_evolution_mode=write_utils.SchemaEvolutionMode.ADD_NEW_COLUMNS,
    enable_change_data_feed=True,
    enable_caching=False,
    reset_checkpoint=(reset_stream_checkpoint.lower() == "true"),
)
print(results)

# COMMAND ----------

common_utils.exit_with_object(results)

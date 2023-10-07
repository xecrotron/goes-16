import shutil
import os
import logging

import psycopg2
import psycopg2.extras as extras
import datetime

logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename="mosaic_update.log", 
    filemode="w"
)

# Absolute paths
DATA_DIR = '/app/DATA'
MOSAIC_DIR = '/app/geoserver/datadir/mosaic_dir'

REGIONS = ['happy_camp', 'bigwood', 'carson', 'oakland']
BANDS = ['wld_map']
DIRS_TO_BE_DELETED = ['cloud', 'mask', 'wld_map']

POSTGRES_CONNECTION_KWARGS = {
    'user':'postgres',
    'password':'postgres',
    'dbname':'postgres',
    'host':'postgres',
    'port':5432
}
connection = psycopg2.connect(**POSTGRES_CONNECTION_KWARGS)
cursor = connection.cursor()

def export_files_to_mosaic_dir(region, band):
    region_mosaic_dir_name = f"{region}_{band}"
    region_mosaic_dir = os.path.join(MOSAIC_DIR, region_mosaic_dir_name)
    if not os.path.exists(region_mosaic_dir):
        os.mkdir(region_mosaic_dir)
        logging.info(f"{region_mosaic_dir} dir created")
    else:
        logging.info(f"{region_mosaic_dir} already exists")

    region_dir = os.path.join(DATA_DIR, region, band)
    files_list = [os.path.join(region_dir, file) for file in os.listdir(region_dir) if file.find('.tif') > -1]
    logging.info(f"{len(files_list)} files found in {region_dir}")

    exported_files_list = []
    for file in files_list:
        # First rename and move the files
        old_file_name = os.path.basename(file)
        file_name_prefix = old_file_name[:old_file_name.find('T')+1:]
        truncated_file_timestamp_string = old_file_name[old_file_name.find('T')+1:-2:][:6:]

        granuel_prefix = band.replace('_', '') + '_'
        new_file_name = granuel_prefix + file_name_prefix + truncated_file_timestamp_string + 'Z.tif'
        new_file_path = os.path.join(region_mosaic_dir, new_file_name)

        if not os.path.exists(new_file_path):
            os.rename(file, new_file_path)
            exported_files_list.append(new_file_path)
        else:
            os.remove(file)
            logging.info(f"{new_file_name} already in target dir... deleting from source dir")
    logging.info(f"Files renamed successfully and moved to {region_mosaic_dir}")
    return exported_files_list

def update_db(region, band, imported_files):
    table_name = f"public.{region}_{band}"
    region_mosaic_dir_name = f"{region}_{band}"
    region_mosaic_dir = os.path.join(MOSAIC_DIR, region_mosaic_dir_name)

    # Fetch only last row to get the bounding box polygon and id
    try:
        sql = f"SELECT fid, ST_AsText(the_geom) FROM {table_name} ORDER BY fid DESC LIMIT 1;"
        cursor.execute(sql)
        fid, polyon_txt_str = cursor.fetchone()

        filename_list_sql = f"SELECT location FROM {table_name};"
        cursor.execute(filename_list_sql)
        existing_filenames = [os.path.join(region_mosaic_dir, result[0]) for result in cursor.fetchall()]
    except Exception as e:
        logging.warning(f"Skipping region- {region} band- {band}")
        cursor.execute("ROLLBACK")
        connection.commit()
        return
    
    # Removing files from list to be imported, which are already in table
    imported_files = list(set(imported_files) - set(existing_filenames))
    logging.info(f"{len(imported_files)} files to be imported to database")

    if not len(imported_files):
        logging.warning("No files to be imported")

    # Creating tuples for insertion into table
    tuples = []
    granuel_prefix = band.replace('_', '') + '_'
    for file in imported_files:
        file_name = os.path.basename(file)
        fid = fid + 1
        ingestion_timestamp = file_name.replace(granuel_prefix, '').replace('_', '').replace('T', '').replace('Z', '').replace('.tif', '')
        ingestion = datetime.datetime.strptime(ingestion_timestamp, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        values = (
            fid,
            polyon_txt_str,
            file_name,
            ingestion
        )
        tuples.append(values)
    
    if not len(tuples):
        logging.info("No values to be inserted into table")
        return

    # Inserting tuples
    insert_query = """
        INSERT INTO {} ("fid", "the_geom", "location", "ingestion") VALUES """.format(table_name)
    args_str = ','.join(cursor.mogrify("(%s, ST_GeomFromText(%s, 3857), %s, %s::timestamp)", x).decode('utf-8') for x in tuples)
    cursor.execute(insert_query + args_str)
    connection.commit()
    logging.info("Successfully updated mosaic!")

def clear_downloaded_files(region):
    region_dir = os.path.join(DATA_DIR, region)
    for dir_name in DIRS_TO_BE_DELETED:
        target_dir = os.path.join(region_dir, dir_name)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            logging.info(f"{target_dir} has been removed.")
        else:
            logging.warning(f"{target_dir} not found for removal.")

if __name__ == '__main__':
    for region in REGIONS:
        for band in BANDS:
            exported_files_list = export_files_to_mosaic_dir(region, band)
            update_db(region, band, exported_files_list)
            clear_downloaded_files(region)
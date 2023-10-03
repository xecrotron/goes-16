import os
import logging
#import psycopg2

logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename="goes_downloader.log", 
    filemode="w"
)

DATA_DIR = '/home/ubuntu/goes-16/DATA'
MOSAIC_DIR = '/home/ubuntu/goes-16/geoserver/datadir/mosaic_dir'

REGIONS = ['bbox_A', 'bbox_B', 'bbox_C', 'happy_camp', 'bigwood', 'carson', 'oakland']
BAND = 'wld_map'

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
        logging.debug(new_file_name)

        if not os.path.exists(new_file_path):
            os.rename(file, new_file_path)
            exported_files_list.append(new_file_path)
        else:
            logging.debug(f"{new_file_name} already in target dir")
    logging.info(f"Files renamed successfully and moved to {region_mosaic_dir}")
    return exported_files_list


if __name__ == '__main__':
    exported_files_list = export_files_to_mosaic_dir('happy_camp', 'wld_map')
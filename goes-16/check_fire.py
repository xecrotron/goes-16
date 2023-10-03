import os
from random import randint

import numpy as np
from osgeo import gdal

data_dir = '/app/DATA'
regions = ['bbox_A', 'bbox_B', 'bbox_C', 'happy_camp', 'bigwood', 'carson', 'oakland']
band = 'wld_map'

def __tif_validity(f_path):
    ds = gdal.Open(f_path)
    raster_array = np.array(ds.GetRasterBand(1).ReadAsArray())

    fire_found_raster = raster_array[raster_array > 0]
    if fire_found_raster.size:
        print(f_path, '\n', fire_found_raster)

for region in regions:
    region_dir = os.path.join(data_dir, region, band)
    tif_files = [os.path.join(region_dir, file) for file in os.listdir(region_dir) if file.find('.tif') > -1]
    for tif_file in tif_files:
        __tif_validity(tif_file)

'''for tif_file in tif_files:
    seconds = randint(0, 59)
    seconds = str(seconds) if seconds > 10 else '0' + str(seconds) 

    minutes = randint(0, 59)
    minutes = str(minutes) if minutes > 10 else '0' + str(minutes) 

    hour = randint(0, 23)
    hour = str(hour) if hour > 10 else '0' + str(hour)

    new_file_name = "{}T{}{}{}Z.tif".format(
        os.path.basename(tif_file).replace('.tif', ''),
        hour,
        minutes,
        seconds
    )
    new_file_name = os.path.basename(tif_file).lower()
    new_file_path = os.path.join(current_dir, new_file_name)
    #os.rename(tif_file, new_file_path)
    print(new_file_path)'''
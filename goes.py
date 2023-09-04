from datetime import datetime, timedelta
from osgeo import gdal, gdal_array, osr
import xarray as xr
import pathlib
import numpy as np
from collections import defaultdict
import s3fs
from tqdm import tqdm
import os

from src.conversion_options import ConversionOptions
from src.goes16_converter import Goes16Converter

FS = s3fs.S3FileSystem(anon=True)
ROOT_DIR = "DATA"
DAY, MONTH, YEAR = 20, 8, 2023
DATE_DELTA = 0
FREQ = 12


def rebin(arr, new_shape):
    shape = (new_shape[0], arr.shape[0] // new_shape[0], new_shape[1], arr.shape[1] // new_shape[1])
    return arr.reshape(shape).mean(-1).mean(1)

def create_rgb_new(r, g, b, store):
    goes16        = Goes16Converter(verbose=False, debug=False)
    blue_options  = ConversionOptions(filename=f"{store}/{b}")
    red_options   = ConversionOptions(filename=f"{store}/{r}")
    green_options = ConversionOptions(filename=f"{store}/{g}")
    store         = store + f"/{store.split('/')[-1]}.tif"
    goes16.extract_and_merge_rgb_bands(red_options, green_options, blue_options, store)

def create_temp(r, g, b, store):
    goes = Goes16Converter()
    blue_options  = ConversionOptions(filename=f"{store}/{b}")
    red_options   = ConversionOptions(filename=f"{store}/{r}")
    green_options = ConversionOptions(filename=f"{store}/{g}")
    store         = store + "/temp.tif"

def calc_cloud_cover(file_name):
    file = xr.open_dataset(file_name)
    data = np.array(file["DQF"].values)
    unique, counts = np.unique(data, return_counts=True)
    ans = dict(zip(unique, counts))
    h, w = data.shape
    return ans[0.0]/ (h*w)

def calc_dataset_cloud_cover():
   files = pathlib.Path("DATA").glob("**/**/**/*-ACHAC-*.nc")
   for f in files:
       print(calc_cloud_cover(f))

def create_rgb(r, g, b, store):
    R = xr.open_dataset(f"{store}/{r}")
    B = xr.open_dataset(f"{store}/{b}")
    G = xr.open_dataset(f"{store}/{g}")

    band_1 = R['Rad'].values
    band_1 = rebin(np.array(band_1), [3000, 5000])
    band_2 = G['Rad'].values  
    band_3 = B['Rad'].values

    stacked_bands = np.stack((band_1, band_2, band_3), axis=-1)

    projection_attrs = B['goes_imager_projection'].attrs
    semi_major_axis = projection_attrs['semi_major_axis']
    inverse_flattening = projection_attrs['inverse_flattening']
    latitude_of_projection_origin = projection_attrs['latitude_of_projection_origin']
    longitude_of_projection_origin = projection_attrs['longitude_of_projection_origin']
    perspective_point_height = projection_attrs['perspective_point_height']
    x_image = B['x_image'].values
    y_image = B['y_image'].values


    x_resolution = semi_major_axis * (3.14159265359 / 180.0) * x_image
    y_resolution = semi_major_axis * (3.14159265359 / 180.0) * y_image
    x_start = -x_resolution * (B.dims['x'] / 2)
    y_start = -y_resolution * (B.dims['y'] / 2)

    geotransform = (x_start, x_resolution, 0, y_start, 0, y_resolution)


    # Create a GeoTIFF file
    output_path = store + "/rgb.tif"
    driver = gdal.GetDriverByName('GTiff')
    out_tif = driver.Create(output_path, stacked_bands.shape[1], stacked_bands.shape[0], stacked_bands.shape[2], gdal_array.NumericTypeCodeToGDALTypeCode(stacked_bands.dtype))
    out_tif.SetGeoTransform(geotransform)

    # Set projection information (replace this with your actual projection)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)  # Example: WGS 84
    out_tif.SetProjection(srs.ExportToWkt())
    for i in range(stacked_bands.shape[2]):
        out_band = out_tif.GetRasterBand(i + 1)
        out_band.WriteArray(stacked_bands[:, :, i])

    return

def parse_filename(filename: str) -> dict:
    if filename.startswith("OR_"):
        filename = filename[3:]  # Remove "OR_" prefix

    parts = filename.split('_')

    if len(parts) != 5:
        raise ValueError(f"Invalid filename format")

    channel = parts[0][-3:]
    satellite_id = parts[1]
    start_time = parts[2][1:]
    end_time = parts[3][1:]
    creation_time = parts[4][1:-3]

    start_dt = datetime.strptime(start_time, "%Y%j%H%M%S%f")
    end_dt = datetime.strptime(end_time, "%Y%j%H%M%S%f")
    creation_dt = datetime.strptime(creation_time, "%Y%j%H%M%S%f")

    parameters = {
        "channel": channel,
        "satellite_id": satellite_id,
        "start_time": start_dt,
        "end_time": end_dt,
        "creation_time": creation_dt,
    }

    return parameters

def datetime_to_time_string(dt):
    day_of_year = dt.timetuple().tm_yday
    tenth_of_second = dt.microsecond // 100000
    
    time_string = f"s{dt.year:04d}{day_of_year:03d}{dt.hour:02d}{dt.minute:02d}{dt.second:02d}{tenth_of_second}"
    return time_string

def download_day(url):
    files = FS.ls(url)
    days_year_start = int(url.split("/")[-1])
    day = (datetime(YEAR, 1, 1) + timedelta(days=days_year_start))
    day_dir = ROOT_DIR + f"/{day.day - 1}-{day.month}-{day.year}"
    os.mkdir(day_dir)
    bar = tqdm(files[::2], desc=f"Date: {day.day -1}-{day.month}-{day.year}")
    for hour in bar:
        hrs = hour.split("/")[-1]
        hrs_dir = day_dir + f"/{hrs}"
        os.mkdir(hrs_dir)
        channel_dict = defaultdict(list)
        img_files = FS.ls(hour)
        for img in img_files[::FREQ]:
            par = parse_filename(img.split("/")[-1])
            channel_dict[par["start_time"]].append(img)
        for k, v in channel_dict.items():
            img_dir = hrs_dir + f"/{str(k).replace(' ', '-')}"
            os.mkdir(img_dir)
            bar.set_description(f"Downloading {k}")
            try:
                day, hour = v[0].split("/")[-3], v[0].split("/")[-2]
                file = f"s3://noaa-goes16/ABI-L2-LSTC/{YEAR}/{day}/{hour}"
                v.append(FS.ls(file)[0])
                file = f"s3://noaa-goes16/ABI-L2-FDCC/{YEAR}/{day}/{hour}"
                v.append(FS.ls(file)[0])
                file = f"s3://noaa-goes16/ABI-L2-ACHAC/{YEAR}/{day}/{hour}"
                v.append(FS.ls(file)[0])
                FS.get(v, f"{img_dir}/")
                temp = sorted(os.listdir(img_dir))
                loc = img_dir
                create_rgb_new(temp[1], temp[2], temp[0], loc)

            except Exception as e:
                print(f"Error: {e}")
            
if __name__ == "__main__":
    os.mkdir(ROOT_DIR)
    
    start_date = datetime(YEAR, MONTH, DAY)
    days_since_year_start = (start_date - datetime(YEAR, 1, 1)).days

    files = FS.ls(f"s3://noaa-goes16/ABI-L1b-RadC/{YEAR}/")
    end_date = start_date + timedelta(days=DATE_DELTA)
    if end_date > datetime.now():
        raise ValueError("End days is past today")
    for f in files[days_since_year_start: days_since_year_start + DATE_DELTA + 1]:
        download_day(f)

from osgeo import gdal, gdal_array, osr
from src.conversion_options import ConversionOptions
from src.goes16_converter import Goes16Converter
import xarray as xr
import numpy as np

Esun_Ch_01 = 726.721072
Esun_Ch_02 = 663.274497
Esun_Ch_03 = 441.868715
d2 = 0.3

def rebin(arr, new_shape):
    shape = (new_shape[0], arr.shape[0] // new_shape[0], new_shape[1], arr.shape[1] // new_shape[1])
    return arr.reshape(shape).mean(-1).mean(1)

def create_rgb(r, g, b):
    b_nc = "./DATA/15-8-2023/00/2023-08-15 00:16:17.300000/OR_ABI-L1b-RadC-M6C01_G16_s20232270016173_e20232270018546_c20232270018575.nc"
    r_nc = "./DATA/15-8-2023/00/2023-08-15 00:16:17.300000/OR_ABI-L1b-RadC-M6C02_G16_s20232270016173_e20232270018546_c20232270018571.nc"
    g_nc = "./DATA/15-8-2023/00/2023-08-15 00:16:17.300000/OR_ABI-L1b-RadC-M6C03_G16_s20232270016173_e20232270018546_c20232270018583.nc"

    R = xr.open_dataset(r)
    print(R)
    B = xr.open_dataset(g)
    G = xr.open_dataset(b)

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
    output_path = "output.tif"
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

    print("Merged GeoTIFF file created successfully!")


def create_band(band, store):
    goes16        = Goes16Converter(verbose=False, debug=False)
    store         = store + f"/{store.split('/')[-1]}.tif"
    band  = ConversionOptions(filename=f"{band}")
    goes16.extract_bands(band, store)

# goes16 = Goes16Converter(verbose=True, debug=True)
store = "output.tif"
# ds = xr.open_dataset("./DATA/15-8-2023/20/2023-08-15 20:01:17.300000/OR_ABI-L1b-RadC-M6C07_G16_s20232272001173_e20232272003558_c20232272004000.nc")
# print(ds)
# red_options = ConversionOptions(filename="./DATA/15-8-2023/20/2023-08-15 20:01:17.300000/OR_ABI-L1b-RadC-M6C07_G16_s20232272001173_e20232272003558_c20232272004000.nc")
# green_options = ConversionOptions(filename="./DATA/15-8-2023/20/2023-08-15 20:01:17.300000/OR_ABI-L1b-RadC-M6C06_G16_s20232272001173_e20232272003552_c20232272003586.nc")
# blue_options  = ConversionOptions(filename="./DATA/15-8-2023/20/2023-08-15 20:01:17.300000/OR_ABI-L1b-RadC-M6C05_G16_s20232272001173_e20232272003547_c20232272003580.nc")
# # goes16.extract_and_merge_rgb_bands(red_options, green_options, blue_options, store)
# goes16.extract_and_merge_temp_bands(red_options, green_options, blue_options, store)
# # goes16.extract(extract_args, "Rad")
file = "./DATA/20-8-2023/00/2023-08-20-00:01:17/OR_ABI-L2-FDCC-M6_G16_s20232320001170_e20232320003543_c20232320004418.nc"
x = xr.open_dataset(file)
# print(x)
create_band(file, "./")
# x = xr.open_dataset("../DATA/20-8-2023/00/2023-08-20-00:00:27.800000/OR_ABI-L2-FDCM1-M6_G18_s20232320000278_e20232320000335_c20232320000528.nc")

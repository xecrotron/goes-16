import numpy as np
import osgeo
from osgeo import gdal, gdal_array, osr

from src.converters import Converters
from src.geotiff_options import GeoTIFF_Options
from src.metadata.goes16_filename_metadata import Goes16FileNameMetadata
from src.netcdf_reader import NetCDFReader
from src.transforms import GoesResolution

def rebin(arr, new_shape):
    shape = (new_shape[0], arr.shape[0] // new_shape[0], new_shape[1], arr.shape[1] // new_shape[1])
    return arr.reshape(shape).mean(-1).mean(1)

def normalize(value, lower_limit, upper_limit, clip=True):
    norm = (value - lower_limit) / (upper_limit - lower_limit)
    if clip:
        norm = np.clip(norm, 0, 1)
    return norm

def breakpoint_stretch(C, breakpoint):
    lower = normalize(C, 0, 10)  # Low end
    upper = normalize(C, 10, 255)  # High end
    combined = np.minimum(lower, upper)

    return combined

def gamma_correction(a, gamma, verbose=False):
    return np.power(a, 1 / gamma)


class Goes16Converter(Converters):

    @property
    def extents(self):
        return [-5434894.885056, -5434894.885056, 5434894.885056, 5434894.885056] # From a raw gdal conversion

    @property
    def extents_WGS84(self):
        return [-160, -80.0, 0.0, 80.0] # Reference extents

    @staticmethod
    def geo_transform(extent, y_rows, x_columns):
        # Compute resolution based on data dimension
        res_x = (extent[2] - extent[0]) / x_columns
        res_y = (extent[3] - extent[1]) / y_rows
        return [extent[0], res_x, 0, extent[3], 0, -res_y]

    def _extract_projection_def(self, options, variable_name):
        netcdf_file = NetCDFReader(netcdf_file=options.input_file, debug=self.debug, verbose=self.verbose)
        attribs = netcdf_file.variable_projection(variable_name)
        projection = osgeo.osr.SpatialReference()
        params = ["+proj=geos", # The projection name is very important this means geostationary
                  "+lon_0={0}".format(attribs['longitude_of_projection_origin']),
                  "+h={0}".format(attribs['perspective_point_height']),
                  "+a={0}".format(attribs['semi_major_axis']),
                  "+b={0}".format(attribs['semi_minor_axis']),
                  "+units={0}".format('m'),
                  "+sweep={0}".format(attribs['sweep_angle_axis']),
                  "+no_defs"]
        command_text = " ".join(params)
        projection.ImportFromProj4(command_text)
        return projection

    def _cmip_to_visible(self, data_values, channel, bit_depth=np.uint8):
        """
        Converts GOES-R16 CMIP (cloud and moisture product) netCDF values into
        the solrad geotiff scale. These are always on a uint8 scale (0 - 255).
        For reflective channels, this is 0: 0% reflectance, 255: 100% reflectance.
        For emissive channels, this is the inverse of the solrad IRCT formula
        (https://gitlab.com/solcast/solcast-alpha/blob/04da0b0c0d04577b5309b5f9ab6ff0c2f843dfeb/src/matlab/cloud-advection/computeCloudLayersFromSatImagery.m#L21)
        i.e. `uint8_value = -1 * (degreesC - 55) / 0.4870`, e.g. 0: 55 degC, 255: -70 degC

        Parameters
        ----------
        values: numpy.ma.MaskedArray
            values to convert, with a mask
        channel: int

        Returns
        -------
            numpy.ndarray: `values` converted to uint8, with all masked
                values set to 0
        """

        data_desc = np.iinfo(bit_depth)
        converted = data_values

        # Replace designated fill value with 0 for nice GDAL TIFF conversion
        converted[data_values.mask] = 0

        # convert to uint8 (will overflow if not capped)
        converted = np.round(converted)
        converted = converted.clip(min=data_desc.min, max=data_desc.max)
        converted = converted.astype(bit_depth)

        return converted

    def _extract_netcdf_image(self, options, extract_key):
        netcdf_file = NetCDFReader(netcdf_file=options.input_file, debug=self.debug, verbose=self.verbose)
        extracted_data = netcdf_file.read(extract_key)
        filename_metadata = Goes16FileNameMetadata.parse(options.input_file)
        if filename_metadata is not None:
            channel_text = filename_metadata.sensor.channel
            scaled_data = self._cmip_to_visible(data_values=extracted_data, channel=int(channel_text))
            return scaled_data
        return extracted_data

    def _transform_extents(self, options):
        transform = options.extents
        if transform is not None:
            return transform
        (y_res, x_res) = options.data.shape
        transform = Goes16Converter.geo_transform(self.extents , y_res, x_res)
        return transform

    def _write_to_memory(self, options):
        transform = self._transform_extents(options)
        (y_res, x_res) = options.data.shape
        driver = osgeo.gdal.GetDriverByName('MEM')
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(options.gdal_type)
        image_mem = driver.Create('grid', x_res, y_res, eType=export_type)
        projection = options.projection
        if transform is not None:
            image_mem.SetGeoTransform(transform)
        if projection is not None:
            image_mem.SetProjection(projection.ExportToWkt())
        band = image_mem.GetRasterBand(1)
        if options.empty is not None:
            band.SetNoDataValue(options.empty)
        band.WriteArray(options.data)
        band.FlushCache()
        return image_mem

    @staticmethod
    def latlng_projection():
        projection = osr.SpatialReference()
        projection.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        return projection


    def _to_geotiff(self, options):

        (y_res, x_res) = options.data.shape
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(options.gdal_type)
        image_mem = self._write_to_memory(options)
        target_proj_wkt = Goes16Converter.latlng_projection().ExportToWkt()

        gtiff_driver = osgeo.gdal.GetDriverByName('GTiff')
        image = gtiff_driver.Create(options.output_file, x_res, y_res, eType=export_type)
        image.SetProjection(target_proj_wkt)
        image.SetGeoTransform(Goes16Converter.geo_transform(self.extents_WGS84, y_res, x_res))

        osgeo.gdal.ReprojectImage(image_mem,
                                  image,
                                  options.projection.ExportToWkt(),
                                  target_proj_wkt,
                                  osgeo.gdal.GRA_NearestNeighbour,
                                  options=['NUM_THREADS=ALL_CPUS'])

        raster_image_data = image.GetRasterBand(1)
        raster_image_data.FlushCache()

        return image

    def _get_transform(self, options, global_variable_name="spatial_resolution"):
        netcdf_file = NetCDFReader(netcdf_file=options.input_file, debug=self.debug, verbose=self.verbose)
        resolution = netcdf_file.global_attribute(global_variable_name)
        if resolution is None:
            return GoesResolution.two_km()

        resolution_in_meters = int(float(resolution.upper().split("km".upper())[0]) * 1000)
        return GoesResolution.extents_for_meters(resolution_in_meters)

    def extract(self, options, variable_name="CMI"):
        tiff_options = GeoTIFF_Options(output_file=options.output_file,
                                       projection=self._extract_projection_def(options, variable_name),
                                       data=self._extract_netcdf_image(options, variable_name))
        tiff_data = self._to_geotiff(tiff_options)
        return tiff_data

    def merge_rgb_bands(self, red_band_data, green_band_data, blue_band_data, store):
        (y_res, x_res) = green_band_data.shape
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(np.uint8)

        # Create a new GeoTIFF image
        gtiff_driver = osgeo.gdal.GetDriverByName('GTiff')
        image = gtiff_driver.Create(store, x_res, y_res, 3, eType=export_type)
        image.SetProjection(self.latlng_projection().ExportToWkt())
        image.SetGeoTransform(self.geo_transform(self.extents_WGS84, y_res, x_res))

        # Write the RGB bands into the GeoTIFF
        for band_idx, band_data in enumerate([red_band_data, green_band_data, blue_band_data]):
            band = image.GetRasterBand(band_idx + 1)
            band.WriteArray(band_data)

        return image

    def merge_rgb_bands_new(self, red_band_data, green_band_data, blue_band_data, store):
        (y_res, x_res) = green_band_data.shape
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(np.uint8)

        # Create a new GeoTIFF image
        gtiff_driver = osgeo.gdal.GetDriverByName('GTiff')
        image = gtiff_driver.Create(store, x_res, y_res, 3, eType=export_type)
        image.SetProjection(self.latlng_projection().ExportToWkt())
        image.SetGeoTransform(self.geo_transform(self.extents_WGS84, y_res, x_res))

        R = np.clip(red_band_data / 255, 0, 1)
        G = np.clip(green_band_data / 255, 0, 1)
        B = np.clip(blue_band_data / 255, 0, 1)

        G = 0.45 * R + 0.1 * G + 0.45 * B
        G = np.clip(G, 0, 1)

        R = np.sqrt(R * 100) * 25.5
        G = np.sqrt(G * 100) * 25.5
        B = np.sqrt(B * 100) * 25.5

        R = breakpoint_stretch(R, 33)
        G = breakpoint_stretch(G, 40)
        B = breakpoint_stretch(B, 50)

        R = gamma_correction(R, 0.8) * 255
        G = gamma_correction(G, 0.8) * 255
        B = gamma_correction(B, 0.8) * 255

        # Write the RGB bands into the GeoTIFF
        for band_idx, band_data in enumerate([R, G, B]):
            band = image.GetRasterBand(band_idx + 1)
            band.WriteArray(band_data)

        return image

    def create_band_new(self, band_data, store):
        (y_res, x_res) = band_data.shape
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(np.uint8)

        # Create a new GeoTIFF image
        gtiff_driver = osgeo.gdal.GetDriverByName('GTiff')
        image = gtiff_driver.Create(store, x_res, y_res, eType=export_type)
        image.SetProjection(self.latlng_projection().ExportToWkt())
        image.SetGeoTransform(self.geo_transform(self.extents_WGS84, y_res, x_res))
        band = image.GetRasterBand(0)
        band.WriteArray(band_data)
        return image

    def extract_and_merge_rgb_bands(self, red_options, green_options, blue_options, store):
        red_band_data = self._extract_netcdf_image(red_options, "Rad")
        green_band_data = self._extract_netcdf_image(green_options, "Rad")
        blue_band_data = self._extract_netcdf_image(blue_options, "Rad")
        red_band_data = rebin(np.array(red_band_data), [3000, 5000])

        # tiff_data = self.merge_rgb_bands(red_band_data, green_band_data, blue_band_data, store)
        tiff_data = self.merge_rgb_bands_new(red_band_data, green_band_data, blue_band_data, store)
        return tiff_data

    def extract_bands(self, band_option, store):
        area_data = self._extract_netcdf_image(band_option, "Area")
        temp_data = self._extract_netcdf_image(band_option, "Temp")
        mask_data = self._extract_netcdf_image(band_option, "Mask")
        power_data = self._extract_netcdf_image(band_option, "Power")
        power_data = self._extract_netcdf_image(band_option, "DQF")
        # tiff_data = self.create_band_new(band_data, store)
        return tiff_data


    def merge_temp_bands(self, red_band_data, green_band_data, blue_band_data, store):
        (y_res, x_res) = green_band_data.shape
        export_type = osgeo.gdal_array.NumericTypeCodeToGDALTypeCode(np.uint8)

        # Create a new GeoTIFF image
        gtiff_driver = osgeo.gdal.GetDriverByName('GTiff')
        image = gtiff_driver.Create(store, x_res, y_res, 3, eType=export_type)
        image.SetProjection(self.latlng_projection().ExportToWkt())
        image.SetGeoTransform(self.geo_transform(self.extents_WGS84, y_res, x_res))

        R = normalize(red_band_data, 273, 333)
        G = normalize(green_band_data, 0, 1)
        B = normalize(blue_band_data, 0, 0.75)

        gamma = 0.4
        R = gamma_correction(R, gamma)
        for band_idx, band_data in enumerate([R, G, B]):
            band = image.GetRasterBand(band_idx + 1)
            band.WriteArray(band_data)

        return image
        

    def extract_and_merge_temp_bands(self, red_options, green_options, blue_options, store):
        red_band_data = self._extract_netcdf_image(red_options, "Rad")
        green_band_data = self._extract_netcdf_image(green_options, "Rad")

        blue_band_data = self._extract_netcdf_image(blue_options, "Rad")
        blue_band_data = rebin(np.array(blue_band_data), [1500, 2500])

        tiff_data = self.merge_temp_bands(red_band_data, green_band_data, blue_band_data, store)
        return tiff_data

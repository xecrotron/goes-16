from datetime import datetime
from osgeo import gdal
import shutil
import numpy as np
import s3fs
import os
import json
from bbox import Bbox, Bboxs, Point
from osgeo import osr
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)

class GoesDownloaderLatest:
    def __init__(self) -> None:
        self.fs = s3fs.S3FileSystem(anon=True)
        self.root_dir = "DATA"
        self.day, self.month, self.year = 20, 9, 2023
        self.boxes = Bboxs.read_file().boxes
        self.__convert_to_WGS__()
        self.json_file = "cloud.json"

        if not os.path.exists(self.root_dir):
            os.mkdir(f"{self.root_dir}")

        for box in self.boxes:
            if not os.path.exists(f"{self.root_dir}/{box.id}"):
                os.mkdir(f"{self.root_dir}/{box.id}")

        logging.info("Calculating cloud cover")
        self.__bbox_cloud_covers__()

    def __bbox_cloud_covers__(self):
        temp_file = "tmp"
        os.mkdir(temp_file)
        file_achac_year = self.fs.ls(f"s3://noaa-goes16/{'ABI-L2-ACHAC'}/{self.year}/")[-1]
        file_achac_day = self.fs.ls(f"s3://{file_achac_year}")[-1]
        files_achac_hour = self.fs.ls(f"s3://{file_achac_day}")
        self.fs.get(files_achac_hour, f"{temp_file}")
        bbox_lowest_cloud_path = {}
        bbox_lowest_cloud_value = {}

        for file in os.listdir(temp_file):
            layer = gdal.Open("NETCDF:{0}:{1}".format(f"./{temp_file}/{file}", "DQF"))
            options = gdal.TranslateOptions(format="GTiff")
            file_name = file.replace('.nc', '.tif')
            gdal.Translate(f"./{temp_file}/{file_name}", layer, options=options)
            os.remove(f"{temp_file}/{file}")

        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")
        for box in self.boxes:
            os.mkdir(f"{temp_file}/{box.id}")
            cloud_cover, cloud_file = -1, None
            for file in os.listdir(temp_file):
                if os.path.isdir(f"./{temp_file}/{file}") or file.split(".")[-1] == "json":
                    continue
                options = gdal.WarpOptions(format="GTiff",
                                           srcSRS=OutSR,
                                           dstSRS=OutSR,
                                           cutlineDSName=f"{box.path}",
                                           cropToCutline=True,
                                           copyMetadata=True)

                gdal.Warp(f"./{temp_file}/{box.id}/{file}",
                          f"./{temp_file}/{file}",
                          options=options)

            for bbox in os.listdir(f"./{temp_file}/{box.id}/"):
                im = Image.open(f"./{temp_file}/{box.id}/{bbox}")
                imarray = np.array(im)
                shape = imarray.shape
                unique, counts = np.unique(imarray, return_counts=True)
                nc_dict = dict(zip(unique, counts))
                density = nc_dict.get(0.0, 1) / (shape[0] * shape[1])
                if density > cloud_cover:
                    cloud_cover = max(cloud_cover, density)
                    cloud_file = bbox
            bbox_lowest_cloud_path[box] = cloud_file
            bbox_lowest_cloud_value[box.id] = cloud_cover
        self.bbox_cloud_cover = bbox_lowest_cloud_path
        self.bbox_cloud_value = bbox_lowest_cloud_value
        shutil.rmtree(f"./{temp_file}")

    def __convert_to_WGS__(self):
        boxes = []
        for box in self.boxes:
            box_arr = []
            for point in box.box:
                p = self.point_coversion(point)
                box_arr.append(p)
            boxes.append(Bbox(box_arr, box.id, box.path))
        self.boxes = Bboxs(boxes).boxes

    def parse_filename(self, filename: str) -> dict:
        if filename.startswith("OR_"):
            filename = filename[3:] 

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

    def point_coversion(self, coord: Point):
        InSR = osr.SpatialReference()
        InSR.SetFromUserInput("EPSG:4326")
        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")

        transform_epsg = osr.CoordinateTransformation(InSR, OutSR)
        transformed = transform_epsg.TransformPoint(coord.y, coord.x)
        return Point(transformed[0], transformed[1])

    def clean_root_dir(self):
        for f in os.listdir(self.root_dir):
            if os.path.isfile(f"{self.root_dir}/{f}") and f.split(".")[-1] != "json":
                os.remove(f"{self.root_dir}/{f}")

    def cloud_cover(self, param, save_location, band):
        logging.info(f"Downloading Bbox for {param}:{band}")
        file_achac_year = self.fs.ls(f"s3://noaa-goes16/{param}/{self.year}/")[-1]
        file_achac_day = self.fs.ls(f"s3://{file_achac_year}")[-1]
        files_achac_hour = self.fs.ls(f"s3://{file_achac_day}")
        try:
            self.fs.get(files_achac_hour, f"{self.root_dir}")
        except Exception as e:
            logging.error(f"Unable to Download {param} {e}")

        for box in self.boxes:
            if not os.path.exists(f"{self.root_dir}/{box.id}/{save_location}"):
                os.mkdir(f"{self.root_dir}/{box.id}/{save_location}/")

        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")

        for file in os.listdir(f"./{self.root_dir}"):
            if os.path.isdir(f"./{self.root_dir}/{file}") or file.split(".")[-1] == "json":
                continue
            layer = gdal.Open("NETCDF:{0}:{1}".format(f"{self.root_dir}/{file}", band))
            options = gdal.TranslateOptions(format="GTiff")
            file_name = file.replace('.nc', '.tif')
            gdal.Translate(f"./{self.root_dir}/{file_name}", layer, options=options)
            os.remove(f"./{self.root_dir}/{file}")

            
        for file in os.listdir(f"./{self.root_dir}"):
            if os.path.isdir(f"./{self.root_dir}/{file}") or file.split(".")[-1] == "json":
                continue
            file_path = self.filename(file)
            for (box, box_file) in self.bbox_cloud_cover.items():
                min_box_file = self.parse_filename(box_file.replace(".tif", ""))["start_time"]
                if self.parse_filename(file.replace(".tif", ""))["start_time"] != min_box_file:
                    continue
                    
                options = gdal.WarpOptions(format="GTiff",
                                           srcSRS=OutSR,
                                           dstSRS=OutSR,
                                           cutlineDSName=f"{box.path}",
                                           cropToCutline=True)

                gdal.Warp(f"./{self.root_dir}/{box.id}/{save_location}/{file_path}",
                          f"./{self.root_dir}/{file}",
                          options=options)

                # reprojecting raster to EPSG:3857 because it is supported by Geoserver
                output_file_path = file_path.replace('.tif', 'Z.tif')
                gdal.Warp(f"./{self.root_dir}/{box.id}/{save_location}/{output_file_path}",
                          gdal.Open(f"./{self.root_dir}/{box.id}/{save_location}/{file_path}"),
                          dstSRS='EPSG:3857')
                os.remove(f"./{self.root_dir}/{box.id}/{save_location}/{file_path}")
        self.clean_root_dir()

    def filename(self, file):
        par = self.parse_filename(file.replace(".tif", ""))
        file_path = f"{par['start_time'].year}{str(par['start_time'].month).zfill(2)}{str(par['start_time'].day).zfill(2)}T{str(par['start_time'].hour).zfill(2)}{str(par['start_time'].minute).zfill(2)}{str(par['start_time'].second).zfill(2)}{str(par['start_time'].microsecond).zfill(3)}.tif"
        return file_path

    def cloud_json(self):
        if not os.path.exists(f"./{self.root_dir}/{self.json_file}"):
            empty_json = {}
            with open(f"./{self.root_dir}/{self.json_file}", "w") as f:
                json.dump(empty_json, f)

        with open(f"./{self.root_dir}/{self.json_file}", "r") as f:
            data = json.load(f)

        with open(f"./{self.root_dir}/{self.json_file}", "w") as f:
            data[str(datetime.now())] = self.bbox_cloud_value
            logging.info("Saving JSON file")
            json.dump(data, f)
            

if __name__ == "__main__":
    down = GoesDownloaderLatest()
    down.cloud_cover("ABI-L2-ACHAC", "cloud", "HT")
    down.cloud_cover("ABI-L2-FDCC", "mask", "Mask")
    down.cloud_cover("ABI-L2-FDCC", "area", "Area")
    down.cloud_cover("ABI-L2-FDCC", "power", "Power")
    down.cloud_cover("ABI-L2-FDCC", "temp", "Temp")
    down.cloud_json()

from datetime import datetime
from numpy import save
from osgeo import gdal
from collections import defaultdict
import s3fs
import os
from bbox import Bbox, Bboxs, Point
from osgeo import osr

class GoesDownloaderLatest:
    def __init__(self) -> None:
        self.fs = s3fs.S3FileSystem(anon=True)
        self.root_dir = "DATA"
        self.day, self.month, self.year = 20, 9, 2023
        self.boxes = Bboxs.read_file().boxes
        self.__convert_to_WGS__()
        os.mkdir(f"{self.root_dir}")
        for box in self.boxes:
            os.mkdir(f"{self.root_dir}/{box.id}")

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
            if os.path.isfile(f"{self.root_dir}/{f}"):
                os.remove(f"{self.root_dir}/{f}")

    def cloud_cover(self, param, save_location, band):
        file_achac_year = self.fs.ls(f"s3://noaa-goes16/{param}/{self.year}/")[-1]
        file_achac_day = self.fs.ls(f"s3://{file_achac_year}")[-1]
        files_achac_hour = self.fs.ls(f"s3://{file_achac_day}")
        self.fs.get(files_achac_hour, f"{self.root_dir}")

        for box in self.boxes:
            os.mkdir(f"{self.root_dir}/{box.id}/{save_location}/")

        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")

        for file in os.listdir(f"./{self.root_dir}"):
            if os.path.isdir(f"./{self.root_dir}/{file}"):
                continue
            file_path = self.filename(file)
            layer = gdal.Open("NETCDF:{0}:{1}".format(f"./{self.root_dir}/{file}", band))
            options = gdal.TranslateOptions(format="GTiff")
            file_name = file.replace('.nc', '.tif')
            gdal.Translate(f"./{self.root_dir}/{file_name}", layer, options=options)
            os.remove(f"./{self.root_dir}/{file}")
            for box in self.boxes:
                options = gdal.WarpOptions(format="GTiff",
                                           srcSRS=OutSR,
                                           dstSRS=OutSR,
                                           cutlineDSName=f"{box.path}",
                                           cropToCutline=True,
                                           copyMetadata=True)

                gdal.Warp(f"./{self.root_dir}/{box.id}/{save_location}/{file_path}",
                          f"./{self.root_dir}/{file_name}",
                          options=options)
        self.clean_root_dir()

    def filename(self, file):
        par = self.parse_filename(file)
        file_path = f"{par['start_time'].year}{str(par['start_time'].month).zfill(2)}{str(par['start_time'].day).zfill(2)}T{str(par['start_time'].hour).zfill(2)}{str(par['start_time'].minute).zfill(2)}{str(par['start_time'].second).zfill(2)}{str(par['start_time'].microsecond).zfill(3)}.tif"
        return file_path


if __name__ == "__main__":
    down = GoesDownloaderLatest()
    down.cloud_cover("ABI-L2-ACHAC", "cloud", "HT")
    down.cloud_cover("ABI-L2-FDCC", "mask", "Mask")
    down.cloud_cover("ABI-L2-FDCC", "area", "Area")
    down.cloud_cover("ABI-L2-FDCC", "power", "Power")
    down.cloud_cover("ABI-L2-FDCC", "temp", "Temp")

import s3fs
from datetime import datetime
from bbox import Bboxs
import os
from osgeo import osr
from bbox import Point, Bbox, Bboxs
import shutil
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename="goes_downloader.log", 
    filemode="a"
)

class Downloader:
    def __init__(self, save_dir) -> None:
        self.fs = s3fs.S3FileSystem(anon=True)
        self.root_dir = f"{save_dir}"
        self.boxes = Bboxs.read_file().boxes
        self.hour_freq = 1
        self.tmp_dir = "tmp"
        self.json_file = "cloud.json"

        self.__convert_to_WGS__()

        if not os.path.exists(self.root_dir):
            os.mkdir(f"{self.root_dir}")

        for box in self.boxes:
            if not os.path.exists(f"{self.root_dir}/{box.id}"):
                os.mkdir(f"{self.root_dir}/{box.id}")

    def clean_root_dir(self):
        shutil.rmtree(f"{self.root_dir}/{self.tmp_dir}")

    def point_coversion(self, coord: Point):
        InSR = osr.SpatialReference()
        InSR.SetFromUserInput("EPSG:4326")
        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")

        transform_epsg = osr.CoordinateTransformation(InSR, OutSR)
        transformed = transform_epsg.TransformPoint(coord.y, coord.x)
        return Point(transformed[0], transformed[1])


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

    def filename(self, file):
        par = self.parse_filename(file.replace(".tif", ""))
        file_path = f"{par['start_time'].year}{str(par['start_time'].month).zfill(2)}{str(par['start_time'].day).zfill(2)}T{str(par['start_time'].hour).zfill(2)}{str(par['start_time'].minute).zfill(2)}{str(par['start_time'].second).zfill(2)}{str(par['start_time'].microsecond).zfill(3)}Z.tif"
        return file_path

    def download(self, start:datetime, end:datetime, param:str, latest:bool=False):
        # Check Year
        try:
            database_year = self.fs.ls(f"s3://noaa-goes16/{param}/")
            file_param_year = [int(x.split("/")[-1]) for x in database_year] 
        except Exception as e:
            raise ValueError(f"Unable to load aws due to {e}")
        if start.year != end.year:
            raise ValueError(f"{start.year} and {end.year} should be same")
        if not start.year in file_param_year:
            raise ValueError(f"{start.year} not in database")
        if not end.year in file_param_year:
            raise ValueError(f"{end.year} not in database")


        # Check day
        start_date_in_year = (datetime(start.year, start.month, start.day) - datetime(start.year, 1, 1)).days + 1
        end_date_in_year = (datetime(end.year, end.month, end.day) - datetime(start.year, 1, 1)).days + 1
        try:
            database_day = self.fs.ls(f"s3://noaa-goes16/{param}/{start.year}")
            file_param_day = [int(x.split("/")[-1]) for x in database_day]
        except Exception as e:
            raise ValueError(f"Unable to load aws due to {e}")
        if not end_date_in_year in file_param_day:
            file_param_day.pop(-1)
            start_date_in_year -= 1
            end_date_in_year -= 1

        if not os.path.exists(f"{self.root_dir}/{self.tmp_dir}"):
            os.mkdir(f"{self.root_dir}/{self.tmp_dir}")

        for day in range(start_date_in_year, end_date_in_year + 1):
            try:
                database_hour = self.fs.ls(f"s3://noaa-goes16/{param}/{start.year}/{day}")
                file_param_hour = [int(x.split("/")[-1]) for x in database_hour]
            except Exception as e:
                raise ValueError(f"Unable to load aws due to {e}")

            if latest:
                hour = [file_param_hour[-1]]
            else:
                hour = file_param_hour[::self.hour_freq]

            os.mkdir(f"{self.root_dir}/{self.tmp_dir}/{day}")
            for hr in hour:
                os.mkdir(f"{self.root_dir}/{self.tmp_dir}/{day}/{hr}")
                files = self.fs.ls(f"s3://noaa-goes16/{param}/{start.year}/{day}/{str(hr).zfill(2)}/")
                logging.info(f"Downloading files for {day}:{hr}")
                try:
                    self.fs.get(files, f"{self.root_dir}/{self.tmp_dir}/{day}/{hr}/")
                except Exception as e:
                    self.clean_root_dir()
                    raise ValueError(f"Unable to Download Data for {param}")

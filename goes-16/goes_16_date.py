from datetime import datetime
from osgeo import gdal
import os
from osgeo import osr
import logging
from Downloader import Downloader

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename="goes_downloader.log", 
    filemode="a"
)


class GoesDownloaderDate(Downloader):
    def __init__(self, save_dir, start:datetime, end:datetime) -> None:
        super().__init__(save_dir)
        self.start = start
        self.end = end

        logging.info("Calculating cloud cover")
        self.__bbox_cloud_covers__()
        
    def __bbox_cloud_covers__(self):
        self.download(self.start, self.end, "ABI-L2-ACHAC", latest=False)
        for day in os.listdir(f"{self.root_dir}/{self.tmp_dir}"):
            for hour in os.listdir(f"{self.root_dir}/{self.tmp_dir}/{day}"):
                for file in os.listdir(f"{self.root_dir}/{self.tmp_dir}/{day}/{hour}"):
                    directory = f"{self.root_dir}/{self.tmp_dir}/{day}/{hour}"
                    layer = gdal.Open("NETCDF:{0}:{1}".format(f"{directory}/{file}", "DQF"))
                    options = gdal.TranslateOptions(format="GTiff")
                    file_name = file.replace('.nc', '.tif')
                    gdal.Translate(f"{directory}/{file_name}", layer, options=options)
                    os.remove(f"{directory}/{file}")

        os.mkdir(f"{self.root_dir}/{self.tmp_dir}_{self.tmp_dir}")
        for box in self.boxes:
            os.mkdir(f"{self.root_dir}/{self.tmp_dir}_{self.tmp_dir}/{box.id}")
            for day in os.listdir(f"{self.root_dir}/{self.tmp_dir}"):
                os.mkdir(f"{self.root_dir}/{self.tmp_dir}_{self.tmp_dir}/{box.id}/{day}")
                for hour in os.listdir(f"{self.root_dir}/{self.tmp_dir}/{day}"):
                    os.mkdir(f"{self.root_dir}/{self.tmp_dir}_{self.tmp_dir}/{box.id}/{day}/{hour}")

        OutSR = osr.SpatialReference()
        OutSR.SetFromUserInput("ESRI:102498")

        for box in self.boxes:
            for day in os.listdir(f"{self.root_dir}/{self.tmp_dir}"):
                for hour in os.listdir(f"{self.root_dir}/{self.tmp_dir}/{day}"):
                    directory = f"{self.root_dir}/{self.tmp_dir}/{day}/{hour}"
                    for file in os.listdir(directory):
                        options = gdal.WarpOptions(format="GTiff",
                                                   srcSRS=OutSR,
                                                   dstSRS=OutSR,
                                                   cutlineDSName=f"{box.path}",
                                                   cropToCutline=True,
                                                   copyMetadata=True)

                        gdal.Warp(f"{self.root_dir}/{self.tmp_dir}_{self.tmp_dir}/{box.id}/{day}/{hour}/{file}",
                                  f"{directory}/{file}",
                                  options=options)


if __name__ == "__main__":
    down = GoesDownloaderDate("/tmp/DATA", datetime(2023, 9, 29), datetime(2023, 10, 1))

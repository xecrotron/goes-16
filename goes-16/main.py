import argparse
from goes_16_latest import GoesDownloaderLatest
from goes_16_date import GoesDownloaderDate
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename="goes_downloader.log", 
    filemode="a"
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="Type of Download")
    parser.add_argument("-s", "--save", required=True)

    latest_parser = subparsers.add_parser("latest")

    datetime_parser = subparsers.add_parser("date")
    datetime_parser.add_argument("-d", "--date", nargs=2, type=str, required=True)
    args = parser.parse_args()
    if 'date' not in args:
        logging.info(f"Downloading data {datetime.now()}")
        down = GoesDownloaderLatest(args.save)
        down.wildfire_map()
        down.run("ABI-L2-ACHAC", "cloud", "HT")
        down.run("ABI-L2-FDCC", "mask", "Mask")
        down.run("ABI-L2-FDCC", "area", "Area")
        down.run("ABI-L2-FDCC", "power", "Power")
        down.run("ABI-L2-FDCC", "temp", "Temp")
        down.cloud_json()

    elif 'date' in args:
        logging.info(f"Buld Downloading")
        down = GoesDownloaderDate(args.save,
                                  datetime.strptime(args.date[0], '%d-%m-%Y'),
                                  datetime.strptime(args.date[1], '%d-%m-%Y'))
        down.wildfire_map()
        down.run("ABI-L2-ACHAC", "cloud", "HT")
        down.run("ABI-L2-FDCC", "mask", "Mask")
        down.run("ABI-L2-FDCC", "area", "Area")
        down.run("ABI-L2-FDCC", "power", "Power")
        down.run("ABI-L2-FDCC", "temp", "Temp")
        

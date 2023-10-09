set -e

source .env

log_file=$PWD/'latest_import.log'
> $log_file


echo "Running hourly update" >> $log_file 2>&1

docker run --name downloader --rm  -v "/home/ubuntu/goes-16:/app" goes_downloader:stable python3 goes-16/main.py -s DATA/ latest >> $log_file 2>&1

docker run --name updater --network goes-16_default --rm  -v "/home/ubuntu/goes-16:/app" goes_downloader:stable python3 goes-16/mosaic_update.py >> $log_file 2>&1
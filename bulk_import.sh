set -e

source .env

log_file='bulk_import.log'
> $log_file

start_date="2023-09-01"
end_date="2023-09-01"
for i in `seq 1 30`;
do
  start_date=$(date -d "$end_date 1 days" +%Y-%m-%d)
  end_date=$(date -d "$start_date 1 days" +%Y-%m-%d)
  echo "Running pipeline for $start_date - $end_date" >> $log_file 2>&1

  docker run --name downloader --rm  -v "/home/ubuntu/goes-16:/app" goes_downloader:stable python3 goes-16/main.py -s DATA/ date -d $start_date $end_date >> $log_file 2>&1

  docker run --name updater --network goes-16_default --rm  -v "/home/ubuntu/goes-16:/app" goes_downloader:stable python3 goes-16/mosaic_update.py >> $log_file 2>&1
done;
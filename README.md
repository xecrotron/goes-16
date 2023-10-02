# GOES-16

## Downloading Latest

```
python3 goes-16/main.py -s /tmp/DATA/ latest
```

Will Download the latest bounding boxes in the save directory



## Bulk Downloading By datetime

```
python3 goes-16/main.py -s /tmp/DATA/ [--date/-d] 29-9-2023 1-10-2023
```
Will Download the specified date range bounding boxes in the save directory
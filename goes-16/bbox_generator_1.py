import os
import argparse
import shapely
import fiona
import json
import numpy as np
from pyproj import Proj,transform
from geojson import Polygon, Feature, load
from shapely.geometry import shape

def generate_bounding_box_geojson(center_point, startDate, endDate, fireArea, box_size_acres=80062.1):
    '''
    box_size_acres: Desired area of bbox. Default as 324 sq km, in acres.
    '''
    box_size_km = box_size_acres*0.00404686
    center_latitude, center_longitude = center_point

    min_latitude = center_latitude - (box_size_km / 2) / 111.111
    max_latitude = center_latitude + (box_size_km / 2) / 111.111
    min_longitude = center_longitude - (box_size_km / 2) / (111.321 * abs(np.cos(np.radians(center_latitude))))
    max_longitude = center_longitude + (box_size_km / 2) / (111.321 * abs(np.cos(np.radians(center_latitude))))

    # Create GeoJSON Polygon
    polygon_coordinates = [
        (min_longitude, max_latitude),
        (min_longitude, min_latitude),
        (max_longitude, min_latitude),
        (max_longitude, max_latitude),
        (min_longitude, max_latitude)
    ]
    polygon=Polygon()
    polygon['coordinates']=[polygon_coordinates]
    feature = Feature(geometry=polygon)
    feature.properties['start_date'] = startDate
    feature.properties['end_date'] = endDate
    feature.properties['area'] = fireArea

    finalJson ={
        "type":"FeatureCollection",
        "features":[feature]
    }
    return finalJson


def dumpjson(root:os, bounding_box_geojson, filename:str):
    json_dump_dir = os.path.join(os.path.dirname(root), 'geojson')
    filename+=".json"
    with open(os.path.join(json_dump_dir,filename),'w') as json_file:
        json.dump(bounding_box_geojson, json_file,indent=2)


#reading 
def geojsonFile(file:str):
    try:
        if file.endswith(".json") == False:
            return
        with open(file) as geojson_file:
            
            geojson_dict = load(geojson_file)
            features = geojson_dict['features']

            for feature in features:

                geometry = feature['geometry']
                properties = feature['properties']
                shapely_geometry = shape(geometry)

                sourceOID = properties["poly_SourceOID"]
                area_acres = properties['poly_GISAcres']
                fireDisoveryDateTime = properties['poly_PolygonDateTime'] if properties['poly_PolygonDateTime'] is not None else properties['poly_CreateDate']
                fireControlDateTime = properties['attr_ContainmentDateTime'] if properties['attr_ContainmentDateTime'] is not None else properties['attr_ModifiedOnDateTime_dt']

                if area_acres < 10.0 or (fireDisoveryDateTime is None or fireControlDateTime is None):
                    print(sourceOID, area_acres, fireDisoveryDateTime, fireControlDateTime)
                    continue

                bounding_box = shapely_geometry.bounds
                bounding_box_geojson = generate_bounding_box_geojson(( (bounding_box[1]+bounding_box[3])/2, (bounding_box[0]+bounding_box[2])/2 ), fireDisoveryDateTime, fireControlDateTime, area_acres)
                root = os.path.dirname(os.path.abspath(__file__))
                dumpjson(root, bounding_box_geojson,str(sourceOID))
    except Exception as e:
        print("Exception Occurred")
        raise

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)

    args = parser.parse_args()
    file_path = args.file

    geojsonFile(file_path)

if __name__ == '__main__':
    main()
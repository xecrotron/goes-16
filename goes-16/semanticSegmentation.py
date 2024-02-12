from os.path import join
import os
import matplotlib.pyplot as plt
from osgeo import gdal
from rastervision.pytorch_learner.dataset import (
    SemanticSegmentationSlidingWindowGeoDataset,
    ObjectDetectionSlidingWindowGeoDataset,
    ClassificationSlidingWindowGeoDataset)
from rastervision.pytorch_learner.dataset.visualizer import (
    SemanticSegmentationVisualizer,
    ObjectDetectionVisualizer,
    ClassificationVisualizer)
from rastervision.core.data import ClassConfig



def work_with_file(image_file:str, label_file:str):
    convert_nc_to_tiff(image_file)
    image_file = join(os.getcwd(),image_file.replace(".nc",".tif"))
    label_file = join(os.getcwd(),label_file)
    lfile = label_file

    class_config = ClassConfig(
        names=['background', 'fire'],
        colors=['lightgray', 'darkred'],
        null_class='background')
    

    chip_sz = 3
    chip_stride = (chip_sz+1)/2
    channel_display_groups = {'RGB': (0, 1, 2), 'IR': (3, )}
    ds = SemanticSegmentationSlidingWindowGeoDataset.from_uris(
    class_config=class_config,
    image_uri=image_file,
    label_vector_uri=lfile,
    label_vector_default_class_id=class_config.get_class_id('fire'),
    image_raster_source_kw=dict(allow_streaming=True),
    size=chip_sz,
    stride=chip_stride)

    vis = SemanticSegmentationVisualizer(
        class_names=class_config.names, class_colors=class_config.colors,
        channel_display_groups=channel_display_groups)
    x, y = vis.get_batch(ds, 4)
    vis.plot_batch(x, y, show=True)



def main():
    file_rel_path = 'DATA/tmp/244/0/OR_ABI-L2-ACHAC-M6_G16_s20232440001172_e20232440003545_c20232440006324.nc'
    geojson_rel_path = 'geojson/13.geojson'
    work_with_file(file_rel_path,geojson_rel_path)

main()
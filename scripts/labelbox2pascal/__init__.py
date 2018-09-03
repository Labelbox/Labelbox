import os
import json
import logging
from shapely import wkt
import requests
from PIL import Image

from .pascal_voc_writer import Writer as PascalWriter


class UnknownFormatError(Exception):
    """Exception raised for unknown label_format"""

    def __init__(self, label_format):
        self.message = ("Provided label_format '{}' is unsupported"
                        .format(label_format))


def from_json(labeled_data, ann_output_dir, images_output_dir,
              label_format='WKT'):
    """Convert Labelbox JSON export to Pascal VOC format.

    Args:
        labeled_data (str): File path to Labelbox JSON export of label data.
        ann_output_dir (str): File path of directory to write Pascal VOC
            annotation files.
        images_output_dir (str): File path of directory to write images.
        label_format (str): Format of the labeled data.
            Valid options are: "WKT" and "XY", default is "WKT".

    Todo:
        * Add functionality to allow use of local copy of an image instead of
            downloading it each time.
    """

    # make sure annotation output directory is valid
    try:
        ann_output_dir = os.path.abspath(ann_output_dir)
        assert os.path.isdir(ann_output_dir)
    except AssertionError as e:
        logging.exception('Annotation output directory does not exist')
        return None

    # read labelbox JSON output
    with open(labeled_data, 'r') as f:
        lines = f.readlines()
        label_data = json.loads(lines[0])

    for data in label_data:
        # Download image and save it
        try:
            response = requests.get(data['Labeled Data'], stream=True)
        except requests.exceptions.MissingSchema as e:
            logging.exception(('"Labeled Data" field must be a URL. '
                              'Support for local files coming soon'))
            continue
        except requests.exceptions.ConnectionError as e:
            logging.exception('Failed to fetch image from {}'
                              .format(data['Labeled Data']))
            continue
        response.raw.decode_content = True
        im = Image.open(response.raw)
        image_name = ('{img_id}.{ext}'
                      .format(img_id=data['ID'], ext=im.format.lower()))
        image_fqn = os.path.join(images_output_dir, image_name)
        im.save(image_fqn, format=im.format)

        # generate image annotation in Pascal VOC
        width, height = im.size
        xml_writer = PascalWriter(image_fqn, width, height)

        # remove classification labels (Skip, etc...)
        labels = data['Label']
        if not callable(getattr(labels, 'keys', None)):
            continue

        # convert multipolygon to Pascal VOC format
        for cat in labels.keys():
            if label_format == 'WKT':
                xml_writer = _add_pascal_object_from_wkt(
                    xml_writer, img_height=height, wkt_data=data['Label'][cat],
                    label=cat)
            elif label_format == 'XY':
                xml_writer = _add_pascal_object_from_xy(
                    xml_writer, img_height=height, polygons=data['Label'][cat],
                    label=cat)
            else:
                e = UnknownFormatError(label_format=label_format)
                print(e.message)
                raise e

        # write Pascal VOC xml annotation for image
        xml_writer.save(os.path.join(ann_output_dir,
                                     '{}.xml'.format(data['ID'])))


def _add_pascal_object_from_wkt(xml_writer, img_height, wkt_data, label):
    polygons = []
    if type(wkt_data) is list: # V3+
        polygons = map(lambda x: wkt.loads(x['geometry']), wkt_data)
    else: # V2
        polygons = wkt.loads(wkt_data)

    for m in polygons:
        xy_coords = []
        for x, y in m.exterior.coords:
            xy_coords.extend([x, img_height-y])
        # remove last polygon if it is identical to first point
        if xy_coords[-2:] == xy_coords[:2]:
            xy_coords = xy_coords[:-2]
        xml_writer.addObject(name=label, xy_coords=xy_coords)
    return xml_writer


def _add_pascal_object_from_xy(xml_writer, img_height, polygons, label):
    for polygon in polygons:
        if 'geometry' in polygon: # V3
            polygon = polygon['geometry']

        assert type(polygon) is list # V2

        xy_coords = []
        for x, y in [(p['x'], p['y']) for p in polygon]:
            xy_coords.extend([x, img_height-y])
        xml_writer.addObject(name=label, xy_coords=xy_coords)
    return xml_writer

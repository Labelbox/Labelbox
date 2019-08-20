"""
Module for converting labelbox.com JSON exports to MS COCO format.
"""

import datetime as dt
import json
import logging
from typing import Any, Dict

from PIL import Image
import requests
from shapely import wkt
from shapely.geometry import box

from exceptions import UnknownFormatError


LOGGER = logging.getLogger(__name__)


def from_json(labeled_data, coco_output, label_format='XY'):
    "Writes labelbox JSON export into MS COCO format."
    # read labelbox JSON output
    with open(labeled_data, 'r') as file_handle:
        label_data = json.loads(file_handle.read())

    # setup COCO dataset container and info
    coco = make_coco_metadata(label_data[0]['Project Name'], label_data[0]['Created By'],)

    for data in label_data:
        # Download and get image name
        try:
            add_label(coco, data['ID'], data['Labeled Data'], data['Label'], label_format)
        except requests.exceptions.MissingSchema as exc:
            LOGGER.warning(exc)
            continue
        except requests.exceptions.ConnectionError:
            LOGGER.warning('Failed to fetch image from %s, skipping', data['Labeled Data'])
            continue

    with open(coco_output, 'w+') as file_handle:
        file_handle.write(json.dumps(coco))


def make_coco_metadata(project_name: str, created_by: str) -> Dict[str, Any]:
    """Initializes COCO export data structure.

    Args:
        project_name: name of the project
        created_by: email of the project creator

    Returns:
        The COCO export represented as a dictionary.
    """
    return {
        'info': {
            'year': dt.datetime.now(dt.timezone.utc).year,
            'version': None,
            'description': project_name,
            'contributor': created_by,
            'url': 'labelbox.com',
            'date_created': dt.datetime.now(dt.timezone.utc).isoformat()
        },
        'images': [],
        'annotations': [],
        'licenses': [],
        'categories': []
    }


def add_label(
        coco: Dict[str, Any], label_id: str, image_url: str,
        labels: Dict[str, Any], label_format: str):
    """Incrementally updates COCO export data structure with a new label.

    Args:
        coco: The current COCO export, will be incrementally updated by this method.
        label_id: ID for the instance to write
        image_url: URL to download image file from
        labels: Labelbox formatted labels to use for generating annotation
        label_format: Format of the labeled data. Valid options are: "WKT" and
                      "XY", default is "XY".

    Returns:
        The updated COCO export represented as a dictionary.
    """
    image = {
        "id": label_id,
        "file_name": image_url,
        "license": None,
        "flickr_url": image_url,
        "coco_url": image_url,
        "date_captured": None,
    }
    response = requests.get(image_url, stream=True, timeout=10.0)
    response.raw.decode_content = True
    image['width'], image['height'] = Image.open(response.raw).size

    coco['images'].append(image)

    # remove classification labels (Skip, etc...)
    if not callable(getattr(labels, 'keys', None)):
        return

    # convert label to COCO Polygon format
    for category_name, label_data in labels.items():
        try:
            # check if label category exists in 'categories' field
            category_id = [c['id']
                           for c in coco['categories']
                           if c['supercategory'] == category_name][0]
        except IndexError:
            category_id = len(coco['categories']) + 1
            category = {
                'supercategory': category_name,
                'id': category_id,
                'name': category_name
            }
            coco['categories'].append(category)

        polygons = _get_polygons(label_format, label_data)
        _append_polygons_as_annotations(coco, image, category_id, polygons)


def _append_polygons_as_annotations(coco, image, category_id, polygons):
    "Adds `polygons` as annotations in the `coco` export"
    for polygon in polygons:
        segmentation = []
        for x_val, y_val in polygon.exterior.coords:
            segmentation.extend([x_val, y_val])

        annotation = {
            "id": len(coco['annotations']) + 1,
            "image_id": image['id'],
            "category_id": category_id,
            "segmentation": [segmentation],
            "area": polygon.area,  # float
            "bbox": [polygon.bounds[0], polygon.bounds[1],
                     polygon.bounds[2] - polygon.bounds[0],
                     polygon.bounds[3] - polygon.bounds[1]],
            "iscrowd": 0
        }

        coco['annotations'].append(annotation)


def _get_polygons(label_format, label_data):
    "Converts segmentation `label: String!` into polygons"
    if label_format == 'WKT':
        if isinstance(label_data, list):  # V3
            polygons = map(lambda x: wkt.loads(x['geometry']), label_data)
        else:  # V2
            polygons = wkt.loads(label_data)
    elif label_format == 'XY':
        polygons = []
        for xy_list in label_data:
            if 'geometry' in xy_list:  # V3
                xy_list = xy_list['geometry']

                # V2 and V3
                if not isinstance(xy_list, list):
                    LOGGER.warning('Could not get an point list to construct polygon, skipping')
                    continue
            else:  # V2, or non-list
                if not isinstance(xy_list, list) or not xy_list or 'x' not in xy_list[0]:
                    # skip non xy lists
                    LOGGER.warning('Could not get an point list to construct polygon, skipping')
                    continue

            if len(xy_list) > 1:
                # find the bounding rectangle and add to the list of polys
                polygons.append(get_bbox(xy_list))

    else:
        exc = UnknownFormatError(label_format=label_format)
        LOGGER.exception(exc.message)
        raise exc

    return polygons

def get_bbox(xy_list):
    # find the rectangle that contains all points

    # initialize bounding box with first point
    point = xy_list[0]
    miny, minx, maxy, maxx = point['y'], point['x'], point['y'], point['x']

    # iterate over points in polygon
    for point in xy_list:
        # find min and max coordinates
        miny = min(miny, point['y'])
        minx = min(minx, point['x'])
        maxy = max(maxy, point['y'])
        maxx = max(maxx, point['x'])

    return box(minx, miny, maxx, maxy)
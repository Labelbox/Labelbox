import os
from jinja2 import Environment, PackageLoader


class Writer:
    def __init__(self, path, width, height, depth=3,
                 database='Unknown', segmented=0):
        environment = Environment(
            loader=PackageLoader('labelbox2pascal', package_path='pascal_voc_writer/templates'),
            keep_trailing_newline=True)
        self.annotation_template = environment.get_template('annotation.xml')

        abspath = os.path.abspath(path)

        self.template_parameters = {
            'path': abspath,
            'filename': os.path.basename(abspath),
            'folder': os.path.basename(os.path.dirname(abspath)),
            'width': width,
            'height': height,
            'depth': depth,
            'database': database,
            'segmented': segmented,
            'objects': []
        }

    # object can be bounding box or polygon
    def addObject(self, name, xy_coords, pose='Unspecified',
                  truncated=0, difficult=0):
        # figure out if label is bounding box or polygon
        if len(xy_coords) == 8:
            xs = sorted(xy_coords[::2])
            ys = sorted(xy_coords[1::2])
            if (xs[0] == xs[1] and xs[2] == xs[3]
                    and ys[0] == ys[1] and ys[2] == ys[3]):
                label_type = 'bndbox'
            else:
                label_type = 'polygon'
        else:
            label_type = 'polygon'

        self.template_parameters['objects'].append({
            'name': name,
            'type': label_type,
            'xy_coords': xy_coords,
            'pose': pose,
            'truncated': truncated,
            'difficult': difficult,
        })

    def save(self, annotation_path):
        with open(annotation_path, 'w') as file:
            content = self.annotation_template.render(**self.template_parameters)
            file.write(content)

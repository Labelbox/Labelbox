# Labelbox Scripts

## Usage 

### Setup


### Labelbox JSON to COCO

Convert a Labelbox JSON export file to COCO format.

```python
# import labelbox2coco library
import labelbox2coco as lb2co

# set labeled_data to the file path of the Labelbox JSON export
labeled_data = 'test-fixtures/labelbox_1.json'

# set coco_output to the file name you want the COCO data to be written to
coco_output = 'lb2co_1.json'

# call the Labelbox to COCO conversion
lb2co.from_json(labeled_data=labeled_data, coco_output=coco_output)
```

### Labelbox JSON to Pascal VOC

Convert a Labelbox JSON export file to Pascal VOC format.

```python
# import labelbox2pascal library
import labelbox2pascal as lb2pa

# set labeled_data to the file path of the Labelbox JSON export
labeled_data = 'test-fixtures/labelbox_1.json'

# set ann_output_dir to the file path of the directory to write Pascal VOC
# annotation files. The directory must exist.
ann_output_dir = './Annotations'

# set images_output_dir to the file path of the directory to write images.
# The directory must exist.
images_output_dir = './Images'

# call the Labelbox to Pascal conversion
# NOTE: make sure to specify the correct label_format based on the export
#  format chosen on Labelbox; 'WKT' or 'XY'.
lb2pa.from_json(labeled_data=labeled_data, ann_output_dir=ann_output_dir,
                images_output_dir=images_output_dir, label_format='WKT')
```

## Development

`pipenv` is used to manage virtualenvs and dependencies.

To get set up:

```sh
pipenv install
```

To run tests:

```sh
pipenv run pytest
```

To lock dependencies defined in `setup.py` (required after introducing new dependencies):

```sh
pipenv install -e .
```

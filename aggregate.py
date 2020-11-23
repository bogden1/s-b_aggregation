#!/usr/bin/env python3

import argparse
import json

import os
import sys
import re

import pandas as pd

WORKFLOWS = {
 'Index': {
    'id': 16866, #Alpha-Index
    'version': 11.28, #Alpha-Index
  },
}

def validated_stride(annotations, task, start, stride):
  result = annotations[start::stride]
  if isinstance(task, str):
    task = [task]
  for x in result:
    if not x['task'] in task:
      exit(f'Invalid task type {task} in stride {stride} through annotations')
  return result

def dropdown_value(dropdown_annotation, textbox_annotation):
  value = dropdown_annotation['value']
  if len(value) != 1: exit(f'Bad dropdown: too many values: {value}')
  value = value[0]
  if (not 'option' in value) or (value['option'] == False): return textbox_annotation['value']
  else: return value['label']

def index_other(annotations):
  HEADING = 'T12'
  SUBJECT_PAGES = 'T11'
  SUBJECT = ['T13', 'T16', 'T18']
  PAGES   = ['T14', 'T17', 'T19']
  SKIP    = 'T15'
  COMMENTS = 'T27'

  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == HEADING: print(value)
    elif task == SUBJECT_PAGES:
      #Subject and Pages group pairwise
      for subject_annotation, pages_annotation in \
        zip(validated_stride(value, SUBJECT, 0, 2),
            validated_stride(value, PAGES,   1, 2)):
        value = re.sub(r'^', '  ', subject_annotation['value'], flags = re.MULTILINE)
        print(value, end=' >>> ')
        print(pages_annotation['value'])
        print()
    elif task == COMMENTS: print(f'Comments: {value}')
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

def index_names(annotations):
  NAME_COMBO = 'T0'
  SURNAME = 'T1'
  TITLE_STANDARD = 'T8'
  TITLE_OTHER = 'T24'
  FORENAME = 'T2'
  POSITION_STANDARD = 'T9'
  POSITION_OTHER = 'T25'
  SUBJECT = 'T26'
  PAGES = 'T6'
  SKIP = 'T7'
  HEADING = 'T12'
  COMMENTS = 'T27'

  while(len(annotations)):
    annotation = annotations.pop(0)
    task = annotation['task']
    value = annotation['value']
    if task == NAME_COMBO:
      for surname, forename, title_dd, title_tb, position_dd, position_tb, subject, pages in \
        zip(validated_stride(value, SURNAME,           0, 8),
            validated_stride(value, FORENAME,          1, 8),
            validated_stride(value, TITLE_STANDARD,    2, 8),
            validated_stride(value, TITLE_OTHER,       3, 8),
            validated_stride(value, POSITION_STANDARD, 4, 8),
            validated_stride(value, POSITION_OTHER,    5, 8),
            validated_stride(value, SUBJECT,           6, 8),
            validated_stride(value, PAGES,             7, 8)):
        print(f'{dropdown_value(title_dd, title_tb)} {forename["value"]} {surname["value"]}, {dropdown_value(position_dd, position_tb)}    {subject["value"]} >>> {pages["value"]}')
    elif task == COMMENTS: print(f'Comments: {value}')
    elif task == HEADING:
      print()
      annotations.insert(0, annotation)
      index_other(annotations)
      break
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

parser = argparse.ArgumentParser(
  description='''Aggregate data from S&B workflows''',
  epilog="Example: ./aggregate.py",
  formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument('classifications', nargs='?', default='scarlets-and-blues-classifications.csv', help='Classifications file (default: scarlets-and-blues-classifications.csv)')
parser.add_argument('-d', '--dump', action='store_true', help='Dump raw JSON')
parser.add_argument('-w', '--workflow', nargs='*', default=[])
args = parser.parse_args()

for x in args.workflow:
  parts = x.split(':')
  if len(parts) != 3:
    exit('Bad args')
  if not parts[0] in ['Index']:
    exit('Bad args')
  WORKFLOWS[parts[0]] = {
    'id': int(parts[1]),
    'version': float(parts[2]),
  }

classifications = pd.read_csv(args.classifications)

for workflow, workflow_data in WORKFLOWS.items():
  #Heading
  print(f'### {workflow} {workflow_data["version"]} ({os.path.basename(args.classifications)})')

  workflow_classifications = classifications.loc[(classifications['workflow_id'] == workflow_data['id']) &
                                                 (classifications['workflow_version'] == workflow_data['version'])]

  #Read the annotations into an array of (subject_data, annotation) tuples
  pages = [ (
              next(iter(json.loads(row['subject_data']).values())), #Load a dict from the subject_data JSON, then drop the key,
                                                                    #leaving only the dict that the key pointed to (there is only
                                                                    #ever one value in these dicts)
              json.loads(row['annotations'])
            )
            for index, row in workflow_classifications.iterrows() ]

  if args.dump: print(json.dumps(pages, indent=2))

  #Read the transcriptions (using our knowledge about the workflows)
  for (page, annotations) in pages:
    print(f'* Page: {page["page"]}')
    control = annotations.pop(0)['value'] #Our workflows all start with a control flow question
    if workflow == 'Index':
      if control == 'Other page':
        index_other(annotations)
      elif control == 'Name list':
        index_names(annotations)
      elif control == 'Blank page':
        print('BLANK')
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    else:
      exit(f'Bad workflow: "{workflow}"')


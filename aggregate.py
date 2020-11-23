#!/usr/bin/env python3

import argparse
import json

import os
import sys
import re

import pandas as pd

WORKFLOWS = {
 'Index': {
    'id': 16866,
    'version': 11.28,
    'control': 'T20',
    'other': {
      'Heading': 'T12',
      'skip': [ 'T15' ], #Tasks in this workflow that we do not process any data for (e.g. control flow)
      'combo':
        { 'T11':
          {
            'Subject': ['T13', 'T16', 'T18'],
            'Pages':   ['T14', 'T17', 'T19'],
          }
        }
    },
    'names': {
      'Title': { 'standard': 'T8', 'other': 'T24' },
      'Forename': 'T2',
      'Position': { 'standard': 'T9', 'other': 'T25'},
      'Subject': 'T26',
      'Pages': 'T6'
    },
    'comments': 'T27',
  },
}

parser = argparse.ArgumentParser(
  description='''Aggregate data from S&B workflows''',
  epilog="Example: ./aggregate.py",
  formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument('classifications', nargs='?', default='scarlets-and-blues-classifications.csv', help='Classifications file (default: scarlets-and-blues-classifications.csv)')
parser.add_argument('-d', '--dump', action='store_true', help='Dump raw JSON')
args = parser.parse_args()

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
    if workflow == 'Index':
      print(f'* Page: {page["page"]}')
      control = annotations.pop(0)['value'] #Our workflows all start with a control flow question
      if control == 'Other page':
        tasks = workflow_data['other']
        for annotation in annotations:
          task = annotation['task']
          value = annotation['value']
          if task == tasks['Heading']: print(f'{value}')
          elif task in tasks['combo'].keys():
            if task == 'T11':
              for subject_annotation, pages_annotation in zip(value[::2], value[1::2]): #Subject and Pages group pairwise
                if(not((subject_annotation['task'] in tasks['combo']['T11']['Subject']) and
                       (pages_annotation['task']   in tasks['combo']['T11']['Pages'])
                      )
                  ):
                  exit(f'T11 subtask not in Subject or Pages:\n{subject_annotation}\n{pages_annotation}')
                value = re.sub(r'^', '  ', subject_annotation['value'], flags = re.MULTILINE)
                print(value, end=' >>> ')
                print(pages_annotation['value'])
                print()
            else: error(f'Unknown combo task: {task}\n{value}')
          elif task == workflow_data['comments']: print(f'Comments: {value}')
          elif task in tasks['skip']: continue
          else: exit(f'Unknown task: {task}\nValue: {value}')
      elif control == 'Name list':
        tasks = workflow_data['names']
        ##TODO
      elif control == 'Blank page':
        print('BLANK')
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    else:
      exit(f'Bad workflow: "{workflow}"')


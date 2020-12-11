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
  'Minutes': {
    'id': 16890, #Alpha-Minutes
    'version': 4.9, #Alpha-Minutes
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

#Return page number and any associated annoatation as a list for each page number
#Unfortunate naming, given that an 'annotation' is something returned from a Zooniverse volunteer,
#but here refers to an annotation written in the minute book by a person
def pageref_annotations(pagerefs):
  match = re.search(r'\([^\),]*,[^\)]*\)', pagerefs)
  if match: exit(f'Comma within brackets: assumption that we can split on comma is broken.\nMatch is "{match.group(0)}" in "{pagerefs}".')
  pagerefs = pagerefs.split(',')
  output = []
  for pageref in [x.strip() for x in pagerefs]:
    #This regexp defines what volunteers are asked to do
    match = re.fullmatch(r'(\d+)\s*(?:\(\s*(.+?)\s*\))?', pageref)
    if match:
      output.append([match.group(1), match.group(2)])
      continue

    #This regexp handles the case where volunteer instead puts the annotation at the beginning
    match = re.fullmatch(r'(.+?)\s+(\d+)', pageref)
    if match:
      output.append([match.group(2), match.group(1)])
      continue

    #Exit if string is not of any form where we can work out what the volunteer meant
    exit(f'Bad pagerefs string: "{pageref}"')
  return output

def index_other(page_data, annotations, other_index):
  HEADING = 'T12'
  SUBJECT_PAGES = 'T11'
  SUBJECT = ['T13', 'T16', 'T18']
  PAGES   = ['T14', 'T17', 'T19']
  SKIP    = 'T15'
  COMMENTS = 'T27'

  page_number = page_data['page']
  heading = None
  heading_stored = True #TODO: This is getting messy -- would it help to have an inner function to update the array?
  entry = 0
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == HEADING:
      print(value)
      if not heading_stored:
        other_index.append([page_number, entry, heading, None, None, None, None])
        entry += 1
      heading = value
      heading_stored = False
    elif task == SUBJECT_PAGES:
      #Subject and Pages group pairwise
      for subject_annotation, pagerefs_annotation in \
        zip(validated_stride(value, SUBJECT, 0, 2),
            validated_stride(value, PAGES,   1, 2)):
        subject = subject_annotation['value']
        pagerefs = pagerefs_annotation['value']
        if subject != '' or pagerefs != '':
          subject = re.sub(r'^', '  ', subject, flags = re.MULTILINE)
          print(subject, end=' >>> ')
          print(pagerefs)
          print()
          if pagerefs == '':
            other_index.append([page_number, entry, heading, subject, '', '', ''])
            entry += 1
          else:
            for pageref, annotation in pageref_annotations(pagerefs):
              other_index.append([page_number, entry, heading, subject, pageref, annotation, None])
              entry += 1
          heading_stored = True
    elif task == COMMENTS:
      if not heading_stored:
        other_index.append([page_number, entry, heading, None, None, None, None])
        entry += 1
        heading_stored = True
      print(f'Comments: {value}')
      other_index.append([page_number, entry, None, None, None, None, value])
      entry += 1
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')


def index_names(page_data, annotations, name_index, other_index):
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

  page_number = page_data['page']
  entry = 0
  while(len(annotations)):
    annotation = annotations.pop(0)
    task = annotation['task']
    value = annotation['value']
    if task == NAME_COMBO:
      for surname, forename, title_dd, title_tb, position_dd, position_tb, subject, pagerefs in \
        zip(validated_stride(value, SURNAME,           0, 8),
            validated_stride(value, FORENAME,          1, 8),
            validated_stride(value, TITLE_STANDARD,    2, 8),
            validated_stride(value, TITLE_OTHER,       3, 8),
            validated_stride(value, POSITION_STANDARD, 4, 8),
            validated_stride(value, POSITION_OTHER,    5, 8),
            validated_stride(value, SUBJECT,           6, 8),
            validated_stride(value, PAGES,             7, 8)):
        title = dropdown_value(title_dd, title_tb)
        position = dropdown_value(position_dd, position_tb)
        forename = forename['value']; surname = surname['value']; subject = subject['value']; pagerefs = pagerefs['value']
        print(f'{title} {forename} {surname}, {position}    {subject} >>> {pagerefs}')
        if pagerefs == '':
          name_index.append([page_number, entry, title, forename, surname, position, subject, None, None, None])
          entry += 1
        else:
          for pageref, annotation in pageref_annotations(pagerefs):
            name_index.append([page_number, entry, title, forename, surname, position, subject, pageref, annotation, None])
            entry += 1
    elif task == COMMENTS:
      print(f'Comments: {value}')
      name_index.append([page_number, entry, None, None, None, None, None, None, None, value])
      entry += 1
    elif task == HEADING:
      #Make sure that we add any comment to this CSV, as well as the other one
      #Note that COMMENT is the same in both functions, as they are processing data from the same page,
      #so we will end up with the comment in both CSV files, which is what we want.
      #TODO: it would be neater to do this in the loop that calls this function, at page level
      #TODO: it should also always be the final task, so I likely do not need this loop -- but a moot point if I deal with the TODO above
      for x in annotations:
        if x['task'] == COMMENTS:
          print(f'Comments: {x["value"]}')
          name_index.append([page_number, entry, None, None, None, None, None, None, None, x['value']])

      print()
      annotations.insert(0, annotation)
      index_other(page_data, annotations, other_index)
      break
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

def minutes_front(page_data, annotations, front_minutes):
  STANDARD_ATTENDEES = 'T9'
  OTHER_ATTENDEES = 'T3'
  STANDARD_ITEMS = 'T14'
  OTHER_ITEMS_COMBO = 'T7'
  OTHER_ITEMS_STANDARD_NUMBER = 'T12'
  OTHER_ITEMS_OTHER_NUMBER = 'T54'
  OTHER_ITEMS_TITLE = 'T13'
  OTHER_ITEMS_TEXT = 'T5'
  OTHER_ITEMS_RESOLUTION = 'T6'
  OTHER_ITEMS_CLASSIFICATION = 'T10'
  COMMENTS = 'T28'
  SKIP = ['T15', 'T55'] #T15: 'Are there any non-standard minutes to transcribe?'
                        #T55: 'Is there another agenda item to transcribe?'

  page_number = page_data['page']
  entry = 0
  print('\033[4mAttendees\033[0m')
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == STANDARD_ATTENDEES:
      print('\n'.join(value))
    elif task == OTHER_ATTENDEES:
      if len(value): print(value)
    elif task == STANDARD_ITEMS:
      print('\n\033[4mAgenda Items\033[0m')
      print('\n'.join(value))
    elif task == OTHER_ITEMS_COMBO:
      for number_dd, number_tb, title, text, resolution, classification, in \
        zip(validated_stride(value, OTHER_ITEMS_STANDARD_NUMBER, 0, 6),
            validated_stride(value, OTHER_ITEMS_OTHER_NUMBER,    1, 6),
            validated_stride(value, OTHER_ITEMS_TITLE,           2, 6),
            validated_stride(value, OTHER_ITEMS_TEXT,            3, 6),
            validated_stride(value, OTHER_ITEMS_RESOLUTION,      4, 6),
            validated_stride(value, OTHER_ITEMS_CLASSIFICATION,  5, 6)):
        number = dropdown_value(number_dd, number_tb)
        title = title['value']; text = text['value']; resolution = resolution['value']; classification = ['classification_value']
        print(f'{number}. ', end = '')
        if len(title): print(f'\033[4m{title}\033[0m ', end = '') #TODO: This should be empty, requires a fixup if it exists.
        if len(text):  print(text, end = ': ')
        print(resolution)
    elif task == COMMENTS:
      print(f'Comments: {value}')
    elif task in SKIP: continue
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

workflow_list = []
for x in args.workflow:
  parts = x.split(':')
  if len(parts) == 3:
    if not parts[0] in WORKFLOWS:
      exit(f'Bad args: {parts[0]} is not a key in WORKFLOWS')
    workflow_list.append(parts[0])
    WORKFLOWS[parts[0]] = {
      'id': int(parts[1]),
      'version': float(parts[2]),
    }
  elif len(parts) == 1:
    workflow_list.append(parts[0])
  else:
    exit(f'Bad args: workflow argument {parts} must have 1 or 3 parts')
if len(workflow_list) == 0: workflow_list = WORKFLOWS.keys()

classifications = pd.read_csv(args.classifications)

for workflow in workflow_list:
  workflow_data = WORKFLOWS[workflow]
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
  other_index = []
  name_index = []
  front_minutes = []
  for (page, annotations) in pages:
    print(f'* Page: {page["page"]}')
    control = annotations.pop(0)['value'] #Our workflows all start with a control flow question
    if workflow == 'Index':
      if control == 'Other page':
        index_other(page, annotations, other_index)
      elif control == 'Name list':
        index_names(page, annotations, name_index, other_index)
      elif control == 'Blank page':
        print('*** BLANK ***')
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    elif workflow == 'Minutes':
      if control == 'Front page, with attendance list':
        minutes_front(page, annotations, front_minutes)
      elif control == 'Other page':
        print(control)
      elif control == 'Blank page':
        print('*** BLANK ***')
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    else:
      exit(f'Bad workflow: "{workflow}"')

  if workflow == 'Index':
    pd.DataFrame(other_index, columns = ['Page', 'Entry', 'Heading', 'Subject', 'PageRef', 'Annotation', 'Comments']). \
      sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Index.csv', index = False)
    pd.DataFrame(name_index, columns = ['Page', 'Entry', 'Title', 'Forename', 'Surname', 'Position', 'Subject', 'PageRef', 'Annotation', 'Comments']). \
      sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Names.csv', index = False)
  elif workflow == 'Minutes':
    pd.DataFrame(front_minutes).to_csv(path_or_buf = 'Minutes.csv', index = False) #COLUMNS TODO


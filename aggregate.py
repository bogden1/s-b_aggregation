#!/usr/bin/env python3

import argparse
import json

import os
import sys
import re
from enum import Enum, unique

import pandas as pd

@unique
class WorkflowType(Enum):
  INDEX = 1
  MINUTES = 2

WORKFLOWS = {
 'Alpha-Index': {
    'type': WorkflowType.INDEX,
    'id': 16866,
    'version': 11.28,
  },
  'Alpha-Names': {
    'type': WorkflowType.INDEX,
    'id': 16899,
    'version': 1.1,
  },
  'Alpha-Minutes': {
    'type': WorkflowType.MINUTES,
    'id': 16890,
    'version': 4.9,
  },
  'Alpha-Tables': {
    'type': WorkflowType.MINUTES,
    'id': 16863,
    'version': 19.48,
  },
}

pd.set_option('display.max_colwidth', None)

#expected_tasks can be scalar or sequence
#if a scalar, there is only one legal task for the annotation
#if a sequence, any of the given tasks is legal for the annotation
def validate(expected_tasks, annotation):
  if isinstance(expected_tasks, str): expected_tasks = [expected_tasks]
  task = annotation['task']
  if not task in expected_tasks:
    raise Exception(f'Invalid task type {task}: expected {expected_tasks}')

#There has never yet been a case where I need multiple expected tasks for dropdowns
def get_dropdown_textbox_value(expected_dropdown_task, dropdown_annotation, expected_textbox_task, textbox_annotation):
  validate(expected_dropdown_task, dropdown_annotation)
  validate(expected_textbox_task, textbox_annotation)
  value = dropdown_annotation['value']
  if len(value) != 1: exit(f'Bad dropdown: too many values: {value}')
  value = value[0]
  if (not 'option' in value) or (value['option'] == False): return textbox_annotation['value'].strip()
  else: return value['label']

def get_dropdown_textbox_values(expected_dropdown_task, dropdown_annotations, expected_textbox_task, textbox_annotations):
  return [get_dropdown_textbox_value(expected_dropdown_task, dd, expected_textbox_task, tb) for dd, tb in \
    zip(dropdown_annotations, textbox_annotations)]

def get_value(expected_tasks, annotation):
  validate(expected_tasks, annotation)
  value = annotation['value']
  if isinstance(value, str): return value.strip()
  else:
    if len(value) != 1: exit(f'Bad value: too many values: {value}')
    return value[0]['label']

def get_values(expected_tasks, annotations):
  return [get_value(expected_tasks, x) for x in annotations]

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
      #TODO: Do I need to make sure that subject task matches page task, or is that already covered somehow?
      #      If I do need to make sure, then I likely don't need validate() to be able to cope with multiple
      #      valid task types any more.
      for subject, pagerefs in \
        zip(get_values(SUBJECT, value[0::2]),
            get_values(PAGES,   value[1::2])):
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
      for surname, forename, title, position, subject, pagerefs in \
        zip(get_values(SURNAME,           value[0::8]),
            get_values(FORENAME,          value[1::8]),
            get_dropdown_textbox_values(TITLE_STANDARD, value[2::8], TITLE_OTHER, value[3::8]),
            get_dropdown_textbox_values(POSITION_STANDARD, value[4::8], POSITION_OTHER, value[5::8]),
            get_values(SUBJECT,           value[6::8]),
            get_values(PAGES,             value[7::8])):
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

def minutes_front_alpha(page_data, annotations, front_minutes):
  STANDARD_ATTENDEES = 'T9'
  OTHER_ATTENDEES = 'T3'
  STANDARD_AGENDA = 'T14'
  AGENDA_COMBO = 'T7'
  AGENDA_STANDARD_NUMBER = 'T12'
  OTHER_NUMBER = 'T54' #Same task serves for both alternative agenda item number in both table and item contexts
  AGENDA_TITLE = 'T13'
  AGENDA_TEXT = 'T5'
  AGENDA_RESOLUTION = 'T6'
  AGENDA_CLASSIFICATION = 'T10'

  TABLE_FIRST_COMBO = 'T25'
  TABLE_STANDARD_NUMBER = 'T23'
  TABLE_TITLE = 'T24'
  TABLE_FIRST_HEADING = 'T47'
  TABLE_FIRST_ROWS = ['T48', 'T49', 'T50', 'T51', 'T52', 'T53']
  TABLE_ROWS_COMBO = 'T36'
  TABLE_ROWS_HEADING = 'T26'
  TABLE_ROWS = ['T30', 'T31', 'T32', 'T33', 'T34', 'T35']
  TABLE_MORE_ROWS_COMBO = 'T46'
  TABLE_MORE_ROWS = ['T39', 'T40', 'T41', 'T42', 'T43', 'T44', 'T45']
  TABLE_NEXT = 'T37'

  COMMENTS = 'T28'
  SKIP = ['T8', 'T15', 'T55'] #T8: 'Is there a table on the page?'
                              #T15: 'Are there any non-standard minutes to transcribe?'
                              #T55: 'Is there another agenda item to transcribe?'

  page_number = page_data['page']
  entry = 0
  table_counter = 0
  table = []
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == STANDARD_ATTENDEES:
      print('\033[4mAttendees\033[0m')
      print('\n'.join(value))
    elif task == OTHER_ATTENDEES:
      if len(value): print(value)
    elif task == STANDARD_AGENDA:
      print('\n\033[4mAgenda Items\033[0m')
      print('\n'.join(value))
    elif task == AGENDA_COMBO:
      number = get_dropdown_textbox_value(AGENDA_STANDARD_NUMBER, value[0], OTHER_NUMBER, value[1])
      title, text, resolution, classification = [get_value(x, y) for x, y in \
        zip([AGENDA_TITLE, AGENDA_TEXT, AGENDA_RESOLUTION, AGENDA_CLASSIFICATION], value[2:])]
      print(f'{number}. ', end = '')
      if len(title): print(f'\033[4m{title}\033[0m ', end = '') #TODO: This should be empty, requires a fixup if it exists.
      if len(text):  print(text, end = ': ')
      print(resolution, end =' ')
      if len(classification): print(f'({classification})', end = '')
      print()
    elif task == TABLE_FIRST_COMBO:
      table_counter += 1

      number = get_value(TABLE_STANDARD_NUMBER, value[0])
      title = get_value(TABLE_TITLE, value[1])
      print(f"Table {table_counter} in item {number}")
      print(f'\033[4m{title}\033[0m')
      heading = get_value(TABLE_FIRST_HEADING, value[2])
      column = [get_value(x, y) for x, y in zip(TABLE_FIRST_ROWS, value[3:])] #This will match each task to the particular value
      table = [[f'*{heading}*']]
      table[-1].extend(column)
      #print(f'Init: {pd.DataFrame(table)}')
    elif task == TABLE_ROWS_COMBO:
      heading = get_value(TABLE_ROWS_HEADING, value[0])
      column = [get_value(x, y) for x, y in zip(TABLE_ROWS, value[1:])]
      table.append([f'*{heading}*'])
      table[-1].extend(column)
      #print(f'Append: {pd.DataFrame(table)}')
    elif task == TABLE_MORE_ROWS_COMBO:
      column = [get_value(x, y) for x, y in zip(TABLE_MORE_ROWS, value)]
      #print(f'Extend1: {pd.DataFrame(table)}')
      table[-1].extend(column)
      #print(f'Extend2: {pd.DataFrame(table)}')
    elif task == TABLE_NEXT:
      if value == 'More rows in this column': None
      elif value == 'Another column': None
      elif value == 'Another table':
        print(pd.DataFrame(table).transpose())
        print()
      elif value[0:8] == 'Nothing ':
        table_counter = 0
        print(pd.DataFrame(table).transpose())
        print()
      else: raise Exception(f'Bad value: {value}')
    elif task == COMMENTS:
      if len(value.strip()) != 0:
        print(f'Comments: {value}')
    elif task in SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

def minutes_front(page_data, annotations, front_minutes):
  STANDARD_ATTENDEES = 'T9'
  OTHER_ATTENDEES = 'T3'
  STANDARD_AGENDA = 'T14'
  AGENDA_COMBO = 'T7'
  AGENDA_STANDARD_NUMBER = 'T12'
  OTHER_NUMBER = 'T54' #Same task serves for both alternative agenda item number in both table and item contexts
  AGENDA_TITLE = 'T13'
  AGENDA_TEXT = 'T5'
  AGENDA_RESOLUTION = 'T6'
  AGENDA_CLASSIFICATION = 'T10'

  TABLE_HEADERS_COMBO = 'T25'
  TABLE_STANDARD_NUMBER = 'T23'
  TABLE_TITLE = 'T24'
  TABLE_COL_HEAD = ['T47', 'T48', 'T49', 'T50', 'T51', 'T52']
  TABLE_ENTRIES_COMBO = 'T36'
  TABLE_ROWS = ['T30', 'T31', 'T32', 'T33', 'T34', 'T35']
  TABLE_NEXT = 'T37'

  COMMENTS = 'T28'
  SKIP = ['T8', 'T15', 'T55'] #T8: 'Is there a table on the page?'
                              #T15: 'Are there any non-standard minutes to transcribe?'
                              #T55: 'Is there another agenda item to transcribe?'

  page_number = page_data['page']
  entry = 0
  table_counter = 0
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == STANDARD_ATTENDEES:
      print('\033[4mAttendees\033[0m')
      print('\n'.join(value))
    elif task == OTHER_ATTENDEES:
      if len(value): print(value)
    elif task == STANDARD_AGENDA:
      print('\n\033[4mAgenda Items\033[0m')
      print('\n'.join(value))
    elif task == AGENDA_COMBO:
      number = get_dropdown_textbox_value(AGENDA_STANDARD_NUMBER, value[0], OTHER_NUMBER, value[1])
      title, text, resolution, classification = [get_value(x, y) for x, y in \
        zip([AGENDA_TITLE, AGENDA_TEXT, AGENDA_RESOLUTION, AGENDA_CLASSIFICATION], value[2:])]
      print(f'{number}. ', end = '')
      if len(title): print(f'\033[4m{title}\033[0m ', end = '') #TODO: This should be empty, requires a fixup if it exists.
      if len(text):  print(text, end = ': ')
      print(resolution, end =' ')
      if len(classification): print(f'({classification})', end = '')
      print()
    elif task == TABLE_HEADERS_COMBO:
      table_counter += 1

      number = get_dropdown_textbox_value(TABLE_STANDARD_NUMBER, value[0], OTHER_NUMBER, value[1])
      title = get_value(TABLE_TITLE, value[2])
      headings = [get_value(x, y) for x, y in zip(TABLE_COL_HEAD, value[3:])] #This will match each task to the particular value

      print(f"Table {table_counter} in item {number}")
      for x in headings:
        if len(x) == 0: break
        print(f'\033[4m{x}\033[0m', end = ',')
      print()
    elif task == TABLE_ENTRIES_COMBO:
      cells = [get_value(x, y) for x, y in zip(TABLE_ROWS, value)]
      for x in cells:
        if len(x) == 0: break
        print(x, end = ',')
      print()
    elif task == TABLE_NEXT:
      if value == 'Another row': None
      elif value == 'Another table': print()
      elif value[0:8] == 'Nothing:':
        table_counter = 0
        print()
      else: raise Exception('Bad value')
    elif task == COMMENTS:
      if len(value.strip()) != 0:
        print(f'Comments: {value}')
    elif task in SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

  #Return multiple dataframes
  #1) Date, page, attendee (one row for each attendee)
  #2) Date, page, agenda item number, agenda item title, agenda item text, agenda item resolution
  #3) Date, page, comments - refactor the way I do comments for the index before implementing this one


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
  if len(parts) == 4:
    if parts[0] in WORKFLOWS:
      print(f'Warning: replacing {parts[0]} in WORKFLOWS')
    workflow_list.append(parts[0])
    WORKFLOWS[parts[0]] = {
      'type': WorkflowType[parts[1].upper()],
      'id': int(parts[2]),
      'version': float(parts[3]),
    }
  elif len(parts) == 1:
    workflow_list.append(parts[0])
  else:
    exit(f'Bad args: workflow argument {parts} must have 1 or 3 parts')
if len(workflow_list) == 0: workflow_list = WORKFLOWS.keys()

classifications = pd.read_csv(args.classifications)

for workflow in workflow_list:
  workflow_data = WORKFLOWS[workflow]
  workflow_type = workflow_data['type']
  #Heading
  print(f'### {workflow} ({workflow_type.name}) {workflow_data["version"]} ({os.path.basename(args.classifications)})')

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
    if workflow_type == WorkflowType.INDEX:
      if control == 'Other page':
        index_other(page, annotations, other_index)
      elif control == 'Name list':
        index_names(page, annotations, name_index, other_index)
      elif control == 'Blank page':
        print('*** BLANK ***')
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    elif workflow_type == WorkflowType.MINUTES:
      if control == 'Blank page':
        print('*** BLANK ***')
        continue
      if (workflow_data['id'] == 16890 and workflow_data['version'] == 4.9) or \
         (workflow_data['id'] == 16863 and workflow_data['version'] == 19.48):
        if control == 'Front page, with attendance list' or \
           control == 'Other page':
          minutes_front_alpha(page, annotations, front_minutes)
        else: exit(f"Bad control switch for alpha workflows: \"{control}\"")
      else:
        if control == 'Front page, with attendance list' or \
           control == 'Another page of meeting minutes':
          minutes_front(page, annotations, front_minutes)
        else: exit(f"Bad control switch: \"{control}\"")
      print()
    else:
      exit(f'Bad workflow type: "{workflow_type}"')

  if workflow_type == WorkflowType.INDEX:
    pd.DataFrame(other_index, columns = ['Page', 'Entry', 'Heading', 'Subject', 'PageRef', 'Annotation', 'Comments']). \
      sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Index.csv', index = False)
    pd.DataFrame(name_index, columns = ['Page', 'Entry', 'Title', 'Forename', 'Surname', 'Position', 'Subject', 'PageRef', 'Annotation', 'Comments']). \
      sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Names.csv', index = False)
  elif workflow_type == WorkflowType.MINUTES:
    pd.DataFrame(front_minutes).to_csv(path_or_buf = 'Minutes.csv', index = False) #COLUMNS TODO


#!/usr/bin/env python3

import argparse
import json

import os
import sys
import re
from enum import Enum, unique

import pandas as pd

@unique
class UnderlineType(Enum):
  TITLE = 0
  TEXT = 1
  RESOLUTION = 2

@unique
class WorkflowType(Enum):
  INDEX = 1
  MINUTES = 2
  UNDERLINING = 3

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
  'Alpha-Underlining': {
    'type': WorkflowType.UNDERLINING,
    'id': 16848,
    'version': 18.65,
  }
}

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

#TODO: Probably makes more sense to have a single index-processing function
def proc_index_other(page_data, annotations, index_other, comments):
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
        index_other.append([page_number, entry, heading, None, None, None])
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
            index_other.append([page_number, entry, heading, subject, '', ''])
            entry += 1
          else:
            for pageref, annotation in pageref_annotations(pagerefs):
              index_other.append([page_number, entry, heading, subject, pageref, annotation])
              entry += 1
          heading_stored = True
    elif task == COMMENTS:
      if not heading_stored:
        index_other.append([page_number, entry, heading, None, None, None])
        entry += 1
        heading_stored = True
      print(f'Comments: {value}')
      comments.append([page_number, value])
      entry += 1
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

#TODO: Probably makes more sense to have a single index-processing function
def proc_index_names(page_data, annotations, index_name, index_other, comments):
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
          index_name.append([page_number, entry, title, forename, surname, position, subject, None, None])
          entry += 1
        else:
          for pageref, annotation in pageref_annotations(pagerefs):
            index_name.append([page_number, entry, title, forename, surname, position, subject, pageref, annotation])
            entry += 1
    elif task == COMMENTS:
      print(f'Comments: {value}')
      entry += 1
    elif task == HEADING:
      print()
      annotations.insert(0, annotation)
      proc_index_other(page_data, annotations, index_other, comments)
      break
    elif task == SKIP: continue
    else: exit(f'Unknown task: {task}\n{value}')

def proc_tables_alpha(page_data, task, value, tables):
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

  page_number = page_data['page']

  if task == TABLE_FIRST_COMBO:
    proc_tables_alpha.counter += 1
    proc_tables_alpha.item_number = get_value(TABLE_STANDARD_NUMBER, value[0])

    proc_tables_alpha.title = get_value(TABLE_TITLE, value[1])
    print(f"Table {proc_tables_alpha.counter} in item {proc_tables_alpha.item_number}")
    print(f'\033[4m{proc_tables_alpha.title}\033[0m')
    heading = get_value(TABLE_FIRST_HEADING, value[2])
    column = [get_value(x, y) for x, y in zip(TABLE_FIRST_ROWS, value[3:])] #This will match each task to the particular value
    proc_tables_alpha.table = [[heading]]
    proc_tables_alpha.table[-1].extend(column)
  elif task == TABLE_ROWS_COMBO:
    heading = get_value(TABLE_ROWS_HEADING, value[0])
    column = [get_value(x, y) for x, y in zip(TABLE_ROWS, value[1:])]
    proc_tables_alpha.table.append([heading])
    proc_tables_alpha.table[-1].extend(column)
  elif task == TABLE_MORE_ROWS_COMBO:
    column = [get_value(x, y) for x, y in zip(TABLE_MORE_ROWS, value)]
    proc_tables_alpha.table[-1].extend(column)
  elif task == TABLE_NEXT:
    if value == 'More rows in this column': None
    elif value == 'Another column': None
    elif value == 'Another table' or value[0:8] == 'Nothing ':
      if value[0:8] == 'Nothing ': proc_tables_alpha.counter = 0

      #Normalise all columns to same length
      max_length = len(proc_tables_alpha.table[0])
      for x in proc_tables_alpha.table[1:]:
        if len(x) > max_length: max_length = len(x)
      for x in proc_tables_alpha.table:
        if len(x) < max_length: x.extend([None] * (max_length - len(x)))

      #Transpose, print and store
      for i, row in enumerate(zip(*proc_tables_alpha.table)):
        if i == 0: print(' '.join([f'*{x}*' for x in row]))
        else: print(*row)

        expanded_row = [*row]
        expanded_row.extend([None] * (6 - len(row)))
        tables.append([page_number, proc_tables_alpha.item_number, proc_tables_alpha.counter, proc_tables_alpha.title, i, *expanded_row]) #row 0 is the headings
      print()
    else: raise Exception(f'Bad value: {value}')
  else: exit(f'Unknown task: {task}\n{value}')

def proc_tables(page_data, task, value, tables):
  TABLE_HEADERS_COMBO = 'T25'
  TABLE_STANDARD_NUMBER = 'T23'
  TABLE_TITLE = 'T24'
  TABLE_COL_HEAD = ['T47', 'T48', 'T49', 'T50', 'T51', 'T52']
  TABLE_ENTRIES_COMBO = 'T36'
  TABLE_ROWS = ['T30', 'T31', 'T32', 'T33', 'T34', 'T35']
  TABLE_NEXT = 'T37'
  OTHER_NUMBER = 'T54' #Same task serves for both alternative agenda item number in both table and item contexts

  page_number = page_data['page']

  if task == TABLE_HEADERS_COMBO:
    proc_tables.counter += 1
    proc_tables.row_number = 0
    proc_tables.item_number = get_dropdown_textbox_value(TABLE_STANDARD_NUMBER, value[0], OTHER_NUMBER, value[1])
    proc_tables.title = get_value(TABLE_TITLE, value[2])

    headings = [get_value(x, y) for x, y in zip(TABLE_COL_HEAD, value[3:])] #This will match each task to the particular value

    print(f"Table {proc_tables.counter} in item {proc_tables.item_number}")
    print(f'\033[4m{proc_tables.title}\033[0m')
    for x in headings:
      if len(x) == 0: break
      print(f'\033[4m{x}\033[0m', end = ',')
    print()
    tables.append([page_number, proc_tables.item_number, proc_tables.counter, proc_tables.title, proc_tables.row_number, *headings]) #row 0 signifies the headings -- there may not be any, in which case those 6 cells will be empty
  elif task == TABLE_ENTRIES_COMBO:
    proc_tables.row_number += 1
    cells = [get_value(x, y) for x, y in zip(TABLE_ROWS, value)]
    for x in cells:
      if len(x) == 0: break
      print(x, end = ',')
      tables.append([page_number, proc_tables.item_number, proc_tables.counter, proc_tables.title, proc_tables.row_number, *cells])
    print()
  elif task == TABLE_NEXT:
    if value == 'Another row': None
    elif value == 'Another table':
      print()
      proc_tables.row_number = 0
    elif value[0:8] == 'Nothing:':
      proc_tables.counter = 0
      print()
    else: raise Exception('Bad value')
  else: exit(f'Unknown task: {task}\n{value}')

def proc_minutes(table_function, page_data, annotations, attendees, tables, items, comments):
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

  COMMENTS = 'T28'
  SKIP = ['T8', 'T15', 'T55'] #T8: 'Is there a table on the page?'
                              #T15: 'Are there any non-standard minutes to transcribe?'
                              #T55: 'Is there another agenda item to transcribe?'

  page_number = int(page_data['page'])
  entry = 0
  table_function.counter = 0
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == STANDARD_ATTENDEES:
      print('\033[4mAttendees\033[0m')
      print('\n'.join(value))
      for x in value: attendees.append([page_number, x.strip()])
    elif task == OTHER_ATTENDEES:
      if len(value):
        print(value)
        for x in value.split('\n'):
          attendees.append([page_number, x.strip()])
    elif task == STANDARD_AGENDA:
      print('\n\033[4mAgenda Items\033[0m')
      print('\n'.join(value))
      for x in value:
        items.append([page_number, int(x[0]), None, x[3:x.index(':')], x[x.index(':') + 1:], 'Front Page Item'])
    elif task == AGENDA_COMBO:
      number = get_dropdown_textbox_value(AGENDA_STANDARD_NUMBER, value[0], OTHER_NUMBER, value[1])
      try:
        number = int(number)
      except ValueError:
        sys.stderr.write(f'Item "{number}" on p. {page_number} is not an integer\n')
      title, text, resolution, classification = [get_value(x, y) for x, y in \
        zip([AGENDA_TITLE, AGENDA_TEXT, AGENDA_RESOLUTION, AGENDA_CLASSIFICATION], value[2:])]
      print(f'{number}. ', end = '')
      if len(title): print(f'\033[4m{title}\033[0m ', end = '') #TODO: This should be empty, requires a fixup if it exists.
      if len(classification): print(f'\033[3m{classification}\033[0m', end = '')
      if len(title) or len(classification): print()
      print('\033[3mText\033[0m')
      if len(text):
        print(text)
        print()
      print('\033[3mResolution\033[0m')
      print(resolution)
      print()
      items.append([page_number, number, title, text, resolution, classification])
    elif task == COMMENTS:
      if len(value.strip()) != 0:
        print(f'Comments: {value}')
        comments.append([page_number, value])
    elif task in SKIP: continue
    else: table_function(page_data, task, value, tables)

def proc_underlining(page, annotations, lines):
  UNDERLININGS = 'T0'

  page_number = page['page']
  for annotation in annotations:
    task = annotation['task']
    value = annotation['value']
    if task == UNDERLININGS:
      underlinings = [[],[],[]]
      for v in value:
        underlinings[int(v['tool'])].append(((v['x1'], v['y1']), (v['x2'], v['y2'])))
      print('Titles')
      for line in underlinings[UnderlineType.TITLE.value]: print(line)
      print('Texts')
      for line in underlinings[UnderlineType.TEXT.value]: print(line)
      print('Resolutions')
      for line in underlinings[UnderlineType.RESOLUTION.value]: print(line)
      for line_type in UnderlineType:
        for line in underlinings[line_type.value]:
          lines.append([page_number, line_type.name, *line[0], *line[1]])
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

index_other = []
index_name = []
minutes_attendees = []
minutes_items = []
minutes_tables = []
comments = []
lines = []
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
  for (page, annotations) in pages:
    print(f'* Page: {page["page"]}')
    control = annotations.pop(0)['value'] #Our workflows all start with a control flow question
    if workflow_type == WorkflowType.INDEX:
      if control == 'Other page':
        proc_index_other(page, annotations, index_other, comments)
      elif control == 'Name list':
        proc_index_names(page, annotations, index_name, index_other, comments)
      elif control == 'Blank page':
        print('*** BLANK ***') #TODO: Probably should make sure that Blank classifications are consistent
        continue
      else: exit(f"Bad control switch: \"{control}\"")
      print()
    elif workflow_type == WorkflowType.MINUTES:
      if control == 'Blank page':
        print('*** BLANK ***') #TODO: Probably should make sure that Blank classifications are consistent
        continue
      if (workflow_data['id'] == 16890 and workflow_data['version'] == 4.9) or \
         (workflow_data['id'] == 16863 and workflow_data['version'] == 19.48):
        if control == 'Front page, with attendance list' or \
           control == 'Other page':
          proc_minutes(proc_tables_alpha, page, annotations, minutes_attendees, minutes_tables, minutes_items, comments)
        else: exit(f"Bad control switch for alpha workflows: \"{control}\"")
      else:
        if control == 'Front page, with attendance list' or \
           control == 'Another page of meeting minutes':
          proc_minutes(proc_tables, page, annotations, minutes_attendees, minutes_tables, minutes_items, comments)
        else: exit(f"Bad control switch: \"{control}\"")
      print()
    elif workflow_type == WorkflowType.UNDERLINING:
      if control == 'Yes, this page is suitable for underlining.':
        proc_underlining(page, annotations, lines)
      elif control == 'No, this page is not suitable for underlining.':
        print('*** UNSUITABLE ***') #TODO: Probably should make sure that Unsuitable classifications are consistent
      elif (workflow_data['id'] == 16848 and workflow_data['version'] < 19.81) and control == None:
        print('*** UNSUITABLE ***') #In the Alpha workflow, the first question was not flagged required and so this could be None
      else: exit(f'Bad control switch: "{control}"')
    else:
      exit(f'Bad workflow type: "{workflow_type}"')

#Index
pd.DataFrame(index_other, columns = ['Page', 'Entry', 'Heading', 'Subject', 'PageRef', 'Annotation']). \
  sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Index.csv', index = False)
pd.DataFrame(index_name, columns = ['Page', 'Entry', 'Title', 'Forename', 'Surname', 'Position', 'Subject', 'PageRef', 'Annotation']). \
  sort_values(['Page', 'Entry']).to_csv(path_or_buf = f'Names.csv', index = False)

#Minutes
pd.DataFrame(minutes_attendees, columns = ['Page', 'Name']). \
  sort_values(['Page', 'Name']).to_csv(path_or_buf = 'Attendees.csv', index = False)
pd.DataFrame(minutes_tables, columns = ['Page', 'Item', 'Table', 'Title', 'Row', 'Col1', 'Col2', 'Col3', 'Col4', 'Col5', 'Col6']). \
  sort_values(['Page', 'Item', 'Table', 'Row']).to_csv(path_or_buf = 'Tables.csv', index = False)
pd.DataFrame(minutes_items, columns = ['Page', 'Item', 'Title', 'Text', 'Resolution', 'Classification']). \
  sort_values(['Page', 'Item']).to_csv(path_or_buf = 'Items.csv', index = False)

#Comments
pd.DataFrame(comments, columns = ['Page', 'Comments']). \
  sort_values('Page').to_csv(path_or_buf = 'Comments.csv', index = False)

#Lines
pd.DataFrame(lines, columns = ['Page', 'Type', 'x1', 'y1', 'x2', 'y2']). \
  sort_values(['Page', 'Type'], key = lambda x: x if x.name == 'Page' else [UnderlineType[y].value for y in x]). \
  to_csv(path_or_buf = 'Lines.csv', index = False)

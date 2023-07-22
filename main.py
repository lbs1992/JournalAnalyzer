from api import *
from collections import defaultdict
import shutil
import os

segment_paths = split_audio_file("/Users/lukesimon/Downloads/test.m4a")

all_entries = ""

#TODO: What happens if there's only one entry?
for path in segment_paths: 
	transcription = transcribe(path)
	_, month, day, year, content = has_date(transcription.lower())
	new_name = f"{str(month).zfill(2)}_{str(day).zfill(2)}_{year}.mp3"
	shutil.copy(path, os.path.join("/Users/lukesimon/Dev/JournalAnalyzer/audio_files", new_name))

	month_name = calendar.month_name[1:][month-1]
	all_entries += f"{month_name} {day}, {year}\n{fix_spelling_and_punctuation(content)}\n\n"

print (all_entries)

parse_and_add_journal_to_database(all_entries)

# print(transcribe("input1.mp3"))
# journal = ""
# with open('SampleJournal.txt', 'r') as file:
#     # Perform operations on the file
#     journal = file.read()

journal_prompt = input("Prompt: ")

date_range = get_date_range(journal_prompt)

if date_range:
  entries = get_journal_entries_by_date_range(*date_range)

  if entries: 
    print (analyze_journal_entries(entries, journal_prompt))
  else: 
    print ("You have no journal entries associated with that prompt.")




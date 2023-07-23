from api import *
from collections import defaultdict
import shutil
import os
import datetime
from fuzzywuzzy import fuzz

# segment_paths = split_audio_file("/Users/lukesimon/Downloads/test.m4a")

# all_entries = ""

#TODO: What happens if there's only one entry?
# for path in segment_paths: 
# 	transcription = transcribe(path)
# 	_, month, day, year, content = has_date(transcription.lower())
# 	new_name = f"{str(month).zfill(2)}_{str(day).zfill(2)}_{year}.mp3"
# 	shutil.copy(path, os.path.join("/Users/lukesimon/Dev/JournalAnalyzer/audio_files", new_name))

# 	month_name = calendar.month_name[1:][month-1]
# 	all_entries += f"{month_name} {day}, {year}\n{fix_spelling_and_punctuation(content)}\n\n"

# print (all_entries)


# journal = ""
# with open('SampleJournal.txt', 'r') as file:
#     # Perform operations on the file
#     journal = file.read()

# parse_and_add_journal_to_database(journal)


journal_prompt = input("Prompt: ")

date_range = get_date_range(journal_prompt)

if date_range:
  entries = get_journal_entries_by_date_range(*date_range)

  if entries: 
    print (analyze_journal_entries(entries, journal_prompt))
  else: 
    print ("You have no journal entries associated with that prompt.")
else: 
	to_search = find_keyword_search(journal_prompt)
	segment_length = len(to_search.split())

	if to_search != "None":
		print (to_search)

	start, end = get_database_range()

	entries = get_journal_entries_by_date_range(
			start.month, start.day, start.year,
			end.month, end.day, end.year
	)

	potential_entries = []
	for entry in entries: 
		segments = entry.entry().split()
		for x in range(0, len(segments) - segment_length):
			curr_segment = remove_non_letters(" ".join(segments[x:x+segment_length]))
			ratio = fuzz.ratio(to_search.lower(), curr_segment.lower())
			if ratio > 90: 
				potential_entries.append(entry)
				break
	
	import pdb; pdb.set_trace()
	print(analyze_journal_entries(potential_entries, journal_prompt))		


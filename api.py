import re
import openai
import datetime
import os
import sqlite3
import tempfile 
from pydub import AudioSegment
from pydub.silence import split_on_silence
import calendar

class JournalEntry: 
    def __init__(self, month, day, year, entry):
        self._entry = entry #fix_spelling_and_grammar(entry)
        self._date = datetime.datetime(year, month, day)

    def entry(self): 
        return self._entry

    def pretty_date(self): 
        return self._date.strftime("%B %d, %Y")

    def date(self):
        return self._date

def init_database():    
    if os.path.exists("journal.db"):
        return

    # Connect to the database or create it if it doesn't exist
    conn = sqlite3.connect('journal.db')

    # Create a table to store journal entries if it doesn't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            month INTEGER,
            day INTEGER,
            year INTEGER,
            entry TEXT,
            mp3_file BLOB,
            PRIMARY KEY (month, day, year)
        )
    ''')

    conn.close()

API_KEY = open('key.txt','r').readline().strip()

def analyze_journal_entries(entries, question):
    prompt = """
        Task: Analyze the provided text entries and extract relevant insights, based on the given question. 

        Context: The provided text entries are daily journal entries covering various topics, experiences, emotions, etc. 
        You can assume I wrote them.

        The requirements for your response are:
            - Use no other context or knowledge except for what is found in the provided text
    """

    text_entries = ""
    for entry in entries:
        text_entries += entry.pretty_date() + "\n"
        text_entries += entry.entry() + "\n"*2
    prompt += f"Text entries: \nSTART\n\n{text_entries}\n\nEND"
    prompt += f"\nQuestion: {question}\n" 
    
    openai.api_key = API_KEY
    completion = openai.ChatCompletion.create(
      model = "gpt-3.5-turbo-16k",
      temperature = 0.8,
      max_tokens = 2000,
      messages = [
        {"role": "user", "content": prompt}
      ]
    )

    return completion.choices[0].message.content

def remove_non_letters(input_string):
    # Use regex pattern to match all non-letter characters (anything that's not a-z or A-Z)
    pattern = r'[^a-zA-Z 0-9]'
    
    # Replace all non-letter characters with an empty string
    result = re.sub(pattern, '', input_string)
    return result

def clean_up_text(entry, fix_spelling = True, fix_punctuation = True, format_nicely = True, fix_grammar = False):
    prompt = "Fix the following: "
    things_to_fix = []

    if fix_spelling: 
        things_to_fix.append("spelling")
    if fix_punctuation:
        things_to_fix.append("punctuation")
    if fix_grammar:
        things_to_fix.append("grammar")
    
    prompt += ",".join(things_to_fix)
    
    if format_nicely:
        prompt += ". Format the text nicely."

    return get_chatgpt_response(prompt + "\n\nText:\"\"\"\n" + entry + "\"\"\"")

def get_journal_entries_by_date_range(start_month, start_day, start_year, end_month, end_day, end_year):
    conn = sqlite3.connect('journal.db')
    cursor = conn.execute('''
        SELECT * FROM journal
        WHERE (year > ? OR (year = ? AND (month > ? OR (month = ? AND day >= ?))))
        AND (year < ? OR (year = ? AND (month < ? OR (month = ? AND day <= ?))))
    ''', (start_year, start_year, start_month, start_month, start_day, end_year, end_year, end_month, end_month, end_day))
    entries = cursor.fetchall()
    conn.close()

    if not entries:
        return []

    journal_entries = []

    for entry in entries:
        journal_entries.append(JournalEntry(*entry[0:4]))
    
    return journal_entries

def split_audio_file(original_file, silent_threshold = 1500, silence_def = 16):
    # Create a temporary folder
    print (f"Splitting the audio file {original_file} with a silent threshold of {silent_threshold}ms")    
    temp_folder = tempfile.mkdtemp()
    print (f"Created a temporary folder at {temp_folder}")

    # Load audio file
    _, file_extension = os.path.splitext(original_file)
    audio = AudioSegment.from_file(original_file, file_extension.strip("."))

    # Define parameters
    min_silence_len = silent_threshold  # silence threshold in milliseconds
    silence_thresh = audio.dBFS - silence_def  # silence less than 16dBFS is considered silence

    # Split on silence
    print ("Splitting the file", end="...")
    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    print ("DONE")
    print (f"Found {len(chunks)} chunks to write to files")
    segment_paths = []

    # Export each chunk
    for i, chunk in enumerate(chunks):
        out_file = os.path.join(temp_folder, f"segment_{i+1}.mp3")
        print (f"Exporting {out_file}", end="...")
        chunk.export(out_file, format="mp3")
        print ("DONE")
        segment_paths.append(out_file)
    
    return segment_paths

def get_database_range():  
    # Connect to the database
    conn = sqlite3.connect('journal.db')  # Replace 'your_database_name.db' with the actual database file name
    cursor = conn.cursor()

    # Get the minimum entry
    cursor.execute('SELECT * FROM journal ORDER BY year, month, day ASC LIMIT 1')
    min_entry = cursor.fetchone()

    # Get the maximum entry
    cursor.execute('SELECT * FROM journal ORDER BY year DESC, month DESC, day DESC LIMIT 1')
    max_entry = cursor.fetchone()

    # Close the connection
    conn.close()

    min_month, min_day, min_year, _, _ = min_entry
    max_month, max_day, max_year, _, _ = max_entry

    return (datetime.date(min_year, min_month, min_day), datetime.date(max_year, max_month, max_day))

def find_keyword_search(query):
    prompt = """
        Task: Return the word I need to use in a search. If there is no word to search, return "None"

        Context: I am going to give you a question or a statement that requires searching something. I want you to analyze the statement and return me the word or phrase I need to use in the search.

        Format: <the word or phrase>

        Requirements: 
         - Only return the word or phrase, no other context

        Prompt: 
    """

    prompt += query

    return get_chatgpt_response(prompt)

def get_date_range(query):
    prefix = """
        Task: Return the date range for the given question or statement.

        Context: I am going to give you a question or a statement that requires knowledge of a certain date. I want
        you to analyze the statement and return me a date range. 

        Format: (<from month>,<from day>,<from year>,<to month>,<to day>,<to year>). 

        Requirements: 
          - Numbers must not start with 0; do not 0-pad
          - Use month-day format
          - Always include the day 
          - No whitespace
          - Minimum character count is 19, maximum is 23
          - No explanation
          - Six numbers separated by a comma and in parenthesis
          - If no response, return "None"

        Prompt: \"\"\"
    """
    

    openai.api_key = API_KEY
    completion = openai.ChatCompletion.create(
      model = "gpt-3.5-turbo-16k",
      temperature = 0.8,
      max_tokens = 2000,
      messages = [
        {"role": "user", "content": prefix + query + "\"\"\""}
      ]
    )

    try:
        return eval(completion.choices[0].message.content)
    except: 
        import pdb; pdb.set_trace()
        return None

def add_journal_entry_to_database(journal_entry):
    date = journal_entry.date()

    potential_file = f"{str(date.month).zfill(2)}_{str(date.day).zfill(2)}_{date.year}.mp3"
    file = os.path.join("/Users/lukesimon/Dev/JournalAnalyzer/audio_files", potential_file) 
    
    mp3_content = None
    try:
        with open(file, "rb") as mp3_file:
            mp3_content = mp3_file.read()
    except:
        pass

    conn = sqlite3.connect('journal.db')
    conn.execute('''
        INSERT OR IGNORE INTO journal (month, day, year, entry, mp3_file)
        VALUES (?, ?, ?, ?, ?)
    ''', (date.month, date.day, date.year, journal_entry.entry(), mp3_content))
    conn.commit()
    conn.close()

def remove_suffixes(input_string):
    pattern = r"\b(\d+)(?:st|nd|rd|th)\b"
    return re.sub(pattern, r"\1", input_string)

def has_date(string):
    contains_date = False
    days = calendar.day_name
    months = calendar.month_name[1:]

    regex_days = r"|".join(days).lower()
    regex_months = r"|".join(months).lower()
    
    text = "^(" + regex_days + "){0,1}[,\\s]*" + "(?P<month>" + regex_months + ")\\s*(?P<day>\\d{1,2}(st|nd|rd|th){0,1})\\s*,?\\s*(?P<year>\\d{4})\\.*"
    
    match = re.search(text, string.strip())
    if match:
        print (f"Found date: {string}")
        month = match.groupdict()['month']
        month = month[0].upper() + month[1:]
        day = int(remove_suffixes(match.groupdict()['day']))
        year = int(match.groupdict()['year'])
        return (True, months.index(month) + 1, day, year, string.replace(match.group(), "").strip())
    return (False, -1, -1, -1, None)

def transcribe(file): 
    openai.api_key = API_KEY
    audio_file= open(file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

def get_chatgpt_response(chat_input):
    openai.api_key = API_KEY
    completion = openai.ChatCompletion.create(
      model = "gpt-3.5-turbo-16k",
      temperature = 0.8,
      max_tokens = 2000,
      messages = [
        {"role": "user", "content": chat_input}
      ]
    )

    return completion.choices[0].message.content

def parse_and_add_journal_to_database(journal_text):
    init_database()
    
    # new_period = "PERIOD_PERIOD_PERIOD_ALERT"
    # journal_text = journal_text.replace("\n", " ")
    # journal_text = re.sub(r"([^\.]*)\.([^\.])", r"\1" + new_period + r"\2", journal_text)
    lines = journal_text.split("\n")
    lines = list(filter(lambda line: line, lines))


    transcribing_entry = False
    date = (-1, -1, -1)
    entry_lines = ""

    for line in lines:
      contains_date, month, day, year, entry = has_date(line.lower())
      if contains_date and not transcribing_entry:
        transcribing_entry = True
        date = (month, day, year)
        entry_lines += entry + ". "
      elif contains_date and transcribing_entry: #Let's populate this new entry
        add_journal_entry_to_database(JournalEntry(*date, clean_up_text(entry_lines)))
        entry_lines = ""
        date = (month, day, year)
        entry_lines += entry + ". "
      elif not contains_date:
        entry_lines += line[0].upper() + line[1:] + ". "


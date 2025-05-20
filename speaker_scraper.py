import re
# Currently registers end of speech at new speaker or end of document. Need to improve end of speech detection. 
SPEAKER_REGEX = re.compile(
    r'^ {2,}'
    r'(?:'
      r'(?:M(?:r|rs|s)\.|Chairman|Chairwoman|Dr\.)\s'
      r'[A-Z](?:[a-z])?[A-Z]+(?:-[A-Z]+)*(?:\s[A-Z](?:[a-z])?[A-Z]+(?:-[A-Z]+)*)*'
      r'(?:\s(?:of\s[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*))?'
      r'(?:\s\[continuing\])?'
      r'(?:\s\([^)]*\))?\.'
    r'|'
      r'(?:'
        r'The\s(?:'
          r'CLERK'
          r'|CHAIRMAN(?:\spro\stempore)?'
          r'|PRESIDING\sOFFICER'
          r'|SPEAKER(?:\spro\stempore)?'
          r'|VICE\sPRESIDENT'
          r'|PRESIDENT\spro\stempore'
          r'|ACTING\sPRESIDENT\spro\stempore'
        r')'
        r'(?:\s\([^)]*\))?'
        r'\.'
      r')'
    r')',
    re.MULTILINE
)

def scrape(text):
    current_speaker = None
    speech_start = None
    speech_end = None

    for m in re.finditer(SPEAKER_REGEX, text):
        name_start = m.start(0)
        name_end = m.end(0)

        if current_speaker is not None:
            speech_end = name_start - 1
            yield current_speaker, text[speech_start:speech_end]

        speech_start = name_end + 1
        current_speaker = text[name_start:name_end].strip()[:-1]

    if current_speaker is not None:
        yield current_speaker, text[speech_start:]

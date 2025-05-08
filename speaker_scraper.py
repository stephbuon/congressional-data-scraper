import re

# Specific exceptions
SPEAKER_REGEX = re.compile(
    r'^  +'                            # Start of line with two spaces
    r'(?:'                             # BEGIN big alternation
    r'(?:M(?:r|rs|s)\.|Chairman|Chairwoman|Dr\.)\s'  # Title
    r'[A-Z]{2,}(?:\s[A-Z]{2,})*'       # Name in ALL CAPS blocks (e.g. MEUSER, YOUNG KIM)
    r'(?:\s(?:of\s[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*))?'  # OPTIONAL: "of California" etc.
    r'(?:\s\[continuing\])?\.'         # OPTIONAL: "[continuing]" before final period
    r'|'                               # OR...
    r'The CLERK\.'                     # "The CLERK."
    r')',                              # END big alternation
    re.MULTILINE
)

"""
SPEAKER_REGEX = re.compile(
    r'(?:^  +(M(?:rs|r|s)\. [a-zA-Z]+[A-Z -]+\.)|(?:Chairman [a-zA-Z]+[A-Z -]+\.)|(?:Dr\. [a-zA-Z]+[A-Z -]+\.))',
    re.MULTILINE
)
"""

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
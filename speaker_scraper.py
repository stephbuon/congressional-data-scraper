import re

SPEAKER_REGEX = re.compile(r'(?:^  +M[rs]. [a-zA-Z]+[A-Z ]+\.)|(?:^  +The [A-Z ]{2,}.)', re.MULTILINE)


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

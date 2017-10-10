import soco

speakers = {}
names = []

list_sonos = list(soco.discover())

for speaker in list_sonos:
    name = speaker.get_speaker_info()['zone_name']
    names.append(name)
    speakers[name] = speaker

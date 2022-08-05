
from amixer import SelemId, ChannelId, Mixer

mixer = Mixer('default')

print(mixer.get_all_selem_ids())

selem_id = SelemId('Master', 0)
selem = mixer.get_selem(selem_id)
print(selem.get_playback_volume(ChannelId.FRONT_LEFT))
print(selem.get_playback_volume(ChannelId.FRONT_RIGHT))

# set volume to 50%
min, max = selem.get_playback_volume_range()
print(min, max)
vol = int(min + 0.5 * (max - min))
selem.set_playback_volume(ChannelId.FRONT_LEFT, vol)
selem.set_playback_volume(ChannelId.FRONT_RIGHT, vol)

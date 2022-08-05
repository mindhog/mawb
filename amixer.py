"""ALSA mixer module."""

import alsa_mixer
import enum
from shorthand import Shorthand
from typing import cast, overload, Any, List, Optional, Tuple

sm = Shorthand(alsa_mixer, 'snd_mixer_')
sms = Shorthand(alsa_mixer, 'snd_mixer_selem_')
smsi = Shorthand(alsa_mixer, 'snd_mixer_selem_id_')
SMS = Shorthand(alsa_mixer, 'SND_MIXER_SCHN_')

class Error(Exception):
    pass

class ChannelId(enum.IntEnum):
    UNKNOWN = SMS.UNKNOWN
    FRONT_LEFT = SMS.FRONT_LEFT
    FRONT_RIGHT = SMS.FRONT_RIGHT
    REAR_LEFT = SMS.REAR_LEFT
    REAR_RIGHT = SMS.REAR_RIGHT
    FRONT_CENTER = SMS.FRONT_CENTER
    WOOFER = SMS.WOOFER
    SIDE_LEFT = SMS.SIDE_LEFT
    SIDE_RIGHT = SMS.SIDE_RIGHT
    REAR_CENTER = SMS.REAR_CENTER
    LAST = SMS.LAST
    MONO = SMS.MONO

# SWIG doesn't expose its types, set up a bunch of fake types.
class SelemId:
    """snd_mixer_selem_id_t"""

    @overload
    def __init__(self, name: str, index: int): ...

    @overload
    def __init__(self, *, raw: Any): ...

    def __init__(self, name: Optional[str] = None,
                 index: Optional[int] = None,
                 raw: Any = None
                 ):
        if raw:
            self.raw = raw
        else:
            assert name is not None
            assert index is not None
            rc, self.raw = smsi.malloc()
            smsi.set_name(self.raw, name)
            smsi.set_index(self.raw, index)

    @property
    def name(self) -> str:
        return smsi.get_name(self.raw)

    @property
    def index(self) -> int:
        return smsi.get_index(self.raw)

    def __str__(self) -> str:
        return f'"{self.name}",{self.index}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self})'

class Selem:
    """A mixer control.

    These are multi-channel controls named by a SelemId.  Use
    Mixer.get_selem() to obtain one.
    """

    def __init__(self, raw: Any):
        self.raw = raw

    def __check_result(self, result: Any) -> Any:
        rc, val = cast(Tuple[int, Any], result)
        if rc:
            raise Error(f'Got rc = {rc}')
        return val

    def __check(self, rc: Any):
        if rc:
            raise Error(f'Got rc = {rc}')

    def get_playback_volume(self, id: ChannelId) -> int:
        return cast(int, self.__check_result(
            sms.get_playback_volume(self.raw, id.value)
        ))

    def set_playback_volume(self, id: ChannelId, volume: int):
        self.__check(sms.set_playback_volume(self.raw, id.value, volume))

    def get_playback_volume_range(self) -> Tuple[int, int]:
        rc, min, max = cast(Tuple[int, int, int],
                            sms.get_playback_volume_range(self.raw)
                            )
        self.__check(rc)
        return min, max

class Mixer:

    def __init__(self, card: str):
        rc, self.__mixer = sm.open(0)
        sm.attach(self.__mixer, card)
        sms.register(self.__mixer, None,  None)
        sm.load(self.__mixer)

    def __del__(self):
        sm.close(self.__mixer)

    def get_all_selem_ids(self) -> List[SelemId]:
        results: List[SelemId] = []
        cur = sm.first_elem(self.__mixer)
        while cur:
            rc, id = smsi.malloc()
            sms.get_id(cur, id)
            results.append(SelemId(raw=id))
            cur = sm.elem_next(cur)
        return results

    def get_selem(self, selem_id: SelemId) -> Optional[Selem]:
        """Returns the Selem for the id, or None if there is none."""
        selem = sm.find_selem(self.__mixer, selem_id.raw)
        return selem and Selem(selem)

from ...protocol.segments import register_milky_converter
from ...utils import KeyQueue
from .. import Adapter
from .actions import MilkyActions
from .listener import MilkyListener
from .translator import milky_seg_from_dict


def build_adapter() -> Adapter:
    register_milky_converter(milky_seg_from_dict)
    return Adapter(name="Milky", actions_cls=MilkyActions, listener=MilkyListener(), reports=KeyQueue())


__all__ = ["MilkyActions", "MilkyListener", "build_adapter"]

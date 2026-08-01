from abc import ABC
from typing import cast

from ...utils.hypetyping import OneBotSegReg
from .translator import milky_seg_from_dict

message_types = {}


class SegmentBase(ABC):
    def __init__(self, *args, **kwargs):
        var = self.__var
        anns = self.__anns
        arg = {}
        if len(args) > 0:
            for i in args:
                arg[list(anns.keys())[list(args).index(i)]] = i

        if len(kwargs) > 0:
            for i, v in kwargs.items():
                try:
                    arg[i] = anns[i](v)
                except TypeError:
                    arg[i] = v
        new_arg = arg.copy()

        if len(anns) > len(arg):
            for i in anns:
                if i not in arg:
                    if i not in var:
                        new_arg[i] = None
                        continue
                    if not isinstance(var[i], anns[i]):
                        new_arg[i] = anns[i](var[i])
                    else:
                        new_arg[i] = var[i]

        for i in new_arg:
            setattr(self, i, new_arg[i])

    def __init_subclass__(cls, **kwargs):
        sg_type = kwargs.get("sg_type") or kwargs.get("st")
        summary_tmp = kwargs.get("summary_tmp") or kwargs.get("su")

        if sg_type is summary_tmp is None:
            return

        cls.__sg_type = sg_type
        cls.__var = dict(vars(cls))
        cls.__anns: dict = cls.__var.get("__annotations__", False) or {}

        def to_str(self) -> str:
            text = summary_tmp
            if text is None:
                text = "[]"
            if "<" not in text and ">" not in text:
                return text

            for i in cls.__anns:
                if f"<{i}>" in text:
                    try:
                        v = self.__getattribute__(i)
                    except AttributeError:
                        v = None
                    text = text.replace(f"<{i}>", str(v))

            return text

        cls.__str__ = to_str if cls().__str__() == "__not_set__" else cls.__str__

        message_types[sg_type] = cast(
            OneBotSegReg,
            {
                "type": cls,
                "args": list(cls.__anns.keys()),
            },
        )

        return cls

    def to_json(self) -> dict:
        base = {"type": self.__sg_type, "data": {}}
        for i in self.__anns:
            if i.startswith("__") or getattr(self, i) is None:
                continue
            if not isinstance(getattr(self, i), self.__anns[i]):
                base["data"][i] = self.__anns[i](getattr(self, i))
            else:
                base["data"][i] = getattr(self, i)
        return base

    def milky_outgoing_seg(self) -> dict:
        return milky_seg_from_dict(self.to_json())

    def __str__(self) -> str:
        return "__not_set__"

    def __eq__(self, other) -> bool:
        return type(self) is type(other) and self.to_json() == other.to_json()

    def __ne__(self, other) -> bool:
        return not (type(self) is type(other) and self.to_json() == other.to_json())

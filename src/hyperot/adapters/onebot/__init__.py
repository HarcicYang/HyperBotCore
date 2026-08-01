from ...protocol import ActionsBase, BaseListener
from .. import Adapter
from .actions import OneBotActions
from .listener import OneBotListener, reports


def build_adapter() -> Adapter:
    return Adapter(name="OneBot", actions_cls=OneBotActions, listener=OneBotListener(), reports=reports)


__all__ = ["ActionsBase", "Adapter", "BaseListener", "OneBotActions", "OneBotListener", "build_adapter", "reports"]

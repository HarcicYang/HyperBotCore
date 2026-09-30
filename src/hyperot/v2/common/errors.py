class HyperotError(Exception):
    """Base class for all V2 framework errors."""


class ConfigurationError(HyperotError):
    pass


class AdapterError(HyperotError):
    pass


class AdapterNotLoadedError(AdapterError):
    pass


class AdapterConnectionError(AdapterError):
    pass


class AdapterDisconnectedError(AdapterError):
    pass


class ActionError(HyperotError):
    pass


class ActionRejectedError(ActionError):
    pass


class ActionTimeoutError(ActionError):
    pass


class ActionNotFoundError(ActionError):
    pass


class CapabilityNotSupportedError(ActionError):
    def __init__(self, action_type: type[object] | str) -> None:
        name = action_type if isinstance(action_type, str) else action_type.__name__
        super().__init__(f"unsupported capability: {name}")
        self.action_type = action_type


class ExtensionNotAvailableError(HyperotError):
    pass


class ClientNotRunningError(HyperotError):
    pass

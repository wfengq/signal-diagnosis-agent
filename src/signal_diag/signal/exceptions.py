"""Signal-domain exceptions."""


class SignalError(Exception):
    """Base signal-domain exception."""


class SignalNotFoundError(SignalError):
    pass


class InvalidSignalError(SignalError):
    pass


class InvalidTimeRangeError(SignalError):
    pass


class UnsupportedChannelError(SignalError):
    pass

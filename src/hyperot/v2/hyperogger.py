from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from types import TracebackType
from typing import Any

from typing_extensions import override

from .style import NerdICONs, color_txt, rgb

TRACE_NUMBER = -1
INFO_NUMBER = 0
WARNING_NUMBER = 1
ERROR_NUMBER = 2
CRITICAL_NUMBER = 3
DEBUG_NUMBER = 10
_MIN_HANDLER_LEVEL = -100
_STDLIB_LEVEL_NUMBERS = {
    "TRACE": 5,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class Levels:
    def __init__(self, nf_icons: NerdICONs):
        self.nf_icons = nf_icons
        self.TRACE = color_txt(f"|{nf_icons.nf_cod_debug_breakpoint_log} Trace    |", rgb(184, 255, 254))
        self.INFO = color_txt(f"|{nf_icons.nf_fa_circle_info} Info     |", rgb(90, 221, 225))
        self.WARNING = color_txt(f"|{nf_icons.nf_fa_warn} Warning  |", rgb(82, 171, 237))
        self.ERROR = color_txt(f"|{nf_icons.nf_cod_error} Error    |", rgb(255, 48, 70))
        self.CRITICAL = color_txt(f"|{nf_icons.nf_cod_bracket_error} Critical |", rgb(178, 33, 48))
        self.DEBUG = color_txt(f"|{nf_icons.nf_cod_debug_alt} Debug    |", rgb(93, 227, 144))
        self.level_nums = {
            "TRACE": TRACE_NUMBER,
            "INFO": INFO_NUMBER,
            "WARNING": WARNING_NUMBER,
            "ERROR": ERROR_NUMBER,
            "CRITICAL": CRITICAL_NUMBER,
            "DEBUG": DEBUG_NUMBER,
        }
        self.level_names = {
            "TRACE": self.TRACE,
            "INFO": self.INFO,
            "WARNING": self.WARNING,
            "ERROR": self.ERROR,
            "CRITICAL": self.CRITICAL,
            "DEBUG": self.DEBUG,
        }


def _record_level(record: logging.LogRecord) -> str:
    explicit = getattr(record, "hyperot_level", None)
    if isinstance(explicit, str):
        return explicit
    match record.levelno:
        case logging.CRITICAL:
            return "CRITICAL"
        case logging.ERROR:
            return "ERROR"
        case logging.WARNING:
            return "WARNING"
        case logging.DEBUG:
            return "TRACE"
        case _:
            return "INFO"


class HyperotFormatter(logging.Formatter):
    def __init__(self, use_nf: bool) -> None:
        super().__init__()
        self.levels = Levels(NerdICONs(use_nf))

    @override
    def format(self, record: logging.LogRecord) -> str:
        level_name = _record_level(record)
        level = self.levels.level_names[level_name]
        now = datetime.now().astimezone().replace(tzinfo=None).isoformat(sep=" ", timespec="milliseconds")
        time = color_txt(
            self.levels.nf_icons.nf_weather_time_4 + " " + now,
            rgb(65, 128, 176),
        )
        message = record.getMessage()
        name = getattr(record, "hyperot_name", None)
        if name:
            message = f"{color_txt(f'[{name}]', rgb(97, 192, 224))} {message}"
        lines = message.splitlines() or [""]
        first = f" {time} {level} {color_txt(lines[0], rgb(215, 255, 255))}"
        if len(lines) == 1:
            output = first
        else:
            padding = " " * int((len(f"{time}{level}") - 2) / 2)
            output = "\n".join([first, *(padding + color_txt(line, rgb(215, 255, 255)) for line in lines[1:])])
        if record.exc_info and record.exc_info[0] is not None:
            output = f"{output}\n{format_exception(record.exc_info)}"
        return output


def format_exception(
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | None,
) -> str:
    if exc_info is None:
        return ""
    exc_type, exc_value, exc_tb = exc_info
    formatted = color_txt("Traceback (most recent call last)", rgb(178, 33, 48))
    trace = traceback.TracebackException(exc_type, exc_value, exc_tb)
    for summary in trace.stack:
        formatted += (
            "\n\n"
            f"  {color_txt('File', rgb(85, 173, 238))} "
            f"{color_txt(summary.filename, rgb(104, 255, 244))}, "
            f"{color_txt('line', rgb(85, 173, 238))} "
            f"{color_txt(str(summary.lineno), rgb(255, 191, 0))}, "
            f"{color_txt('in', rgb(85, 173, 238))} "
            f"{color_txt(summary.name, rgb(70, 172, 107))}"
        )
        if summary.line:
            formatted += f"\n    {color_txt(summary.line.strip(), rgb(150, 150, 150))}"
    formatted += (
        f"\n\n{color_txt(exc_type.__name__, rgb(255, 48, 70))}: {color_txt(str(exc_value), rgb(230, 230, 230))}"
    )
    if trace.__cause__ is not None:
        formatted += "\n\n" + color_txt("The above exception was the direct cause:", rgb(120, 120, 120))
        formatted += "\n" + "".join(trace.__cause__.format())
    return formatted


class _HyperotHandler(logging.Handler):
    def __init__(self, stream: Any, use_nf: bool) -> None:
        super().__init__(level=_MIN_HANDLER_LEVEL)
        self.setFormatter(HyperotFormatter(use_nf))
        self.stream = stream

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.stream.write(self.format(record) + "\n")
            self.flush()
        except Exception:  # noqa: BLE001
            self.handleError(record)


class Logger:
    def __init__(
        self,
        stdlib_logger: logging.Logger,
        level: str = "INFO",
        *,
        use_nf: bool = True,
        name: str | None = None,
    ) -> None:
        self._logger = stdlib_logger
        self._level = level
        self._use_nf = use_nf
        self._custom_name = name
        self.levels = Levels(NerdICONs(use_nf))
        self._logger.setLevel(_MIN_HANDLER_LEVEL)

    @classmethod
    def create(cls, key: str, level: str, use_nf: bool = True) -> Logger:
        configure_hyperot_logging(use_nf=use_nf)
        logger = cls(logging.getLogger(key), level, use_nf=use_nf)
        logger.set_level(level)
        logger._logger._hyperot_level = level  # pyrefly: ignore[missing-attribute]
        return logger

    @classmethod
    def fetch(cls, key: str) -> Logger:
        stdlib_logger = logging.getLogger(key)
        level = getattr(stdlib_logger, "_hyperot_level", "INFO")
        use_nf = getattr(stdlib_logger, "_hyperot_use_nf", True)
        if not any(isinstance(handler, _HyperotHandler) for handler in stdlib_logger.handlers):
            configure_hyperot_logging(use_nf=use_nf)
        return cls(stdlib_logger, level, use_nf=use_nf)

    def name_custom(self, name: str) -> Logger:
        return Logger(self._logger, self._level, use_nf=self._use_nf, name=name)

    def set_level(self, level: str) -> Logger:
        if level not in self.levels.level_names:
            raise ValueError(f"unknown log level: {level}")
        self._level = level
        self._logger._hyperot_level = level  # pyrefly: ignore[missing-attribute]
        return self

    def _emit(self, level: str, message: Any, *, exc_info: Any = None) -> None:
        threshold = self.levels.level_nums[self._level]
        number = self.levels.level_nums[level]
        if number < threshold:
            return
        self._logger.log(
            _STDLIB_LEVEL_NUMBERS[level],
            str(message),
            exc_info=exc_info,
            extra={"hyperot_level": level, "hyperot_name": self._custom_name},
        )

    def log(self, message: Any, level: str = "INFO", *, exc_info: Any = None) -> None:
        self._emit(level, message, exc_info=exc_info)

    def trace(self, message: Any) -> None:
        self._emit("TRACE", message)

    def debug(self, message: Any) -> None:
        self._emit("DEBUG", message)

    def info(self, message: Any) -> None:
        self._emit("INFO", message)

    def warning(self, message: Any) -> None:
        self._emit("WARNING", message)

    def error(self, message: Any, *, exc_info: Any = None) -> None:
        self._emit("ERROR", message, exc_info=exc_info)

    def critical(self, message: Any, *, exc_info: Any = None) -> None:
        self._emit("CRITICAL", message, exc_info=exc_info)


_CONFIGURED = False


def configure_hyperot_logging(
    *,
    use_nf: bool = True,
    stream: Any | None = None,
    replace: bool = False,
    global_handlers: bool = False,
) -> None:
    global _CONFIGURED
    root = logging.getLogger()
    if global_handlers:
        target = root
    else:
        root.handlers = [handler for handler in root.handlers if not isinstance(handler, _HyperotHandler)]
        target = logging.getLogger("hyperot.v2")
    if replace:
        target.handlers.clear()
    elif _CONFIGURED:
        return
    target.addHandler(_HyperotHandler(stream or sys.stdout, use_nf))
    target.setLevel(_MIN_HANDLER_LEVEL)
    target.propagate = False
    target._hyperot_use_nf = use_nf  # pyrefly: ignore[missing-attribute]
    _CONFIGURED = True


def configure_global_logging(*, use_nf: bool = True, replace: bool = False) -> None:
    configure_hyperot_logging(use_nf=use_nf, replace=replace, global_handlers=True)


def install_excepthook(logger: Logger) -> None:
    def hook(_exc_type: type[BaseException], _exc: BaseException, _tb: Any) -> None:
        logger.error("uncaught exception", exc_info=True)  # noqa: LOG014

    sys.excepthook = hook

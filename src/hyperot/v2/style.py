def rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    return r, g, b


def color_txt(text: str, color: tuple[int, int, int]) -> str:
    r, g, b = color
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


class NerdICONs:
    def __init__(self, enable: bool):
        self.enable = enable

    def __getattribute__(self, item: str) -> str:
        if item in {"enable", "__dict__", "__class__"}:
            return str(super().__getattribute__(item))
        if super().__getattribute__("enable"):
            return str(super().__getattribute__(item))
        return " "

    nf_fa_circle_info = " \uf05a"
    nf_cod_bracket_error = " \uebe6"
    nf_cod_error = " \uea87"
    nf_fa_warn = " \uf071"
    nf_cod_debug_alt = " \ueb91"
    nf_cod_debug_breakpoint_log = " \ueaab"
    nf_weather_time_4 = " \ue385"

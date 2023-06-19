import decimal
import math
import re

TEN_THOUSAND = 10**4
SYMBOLS = ["K", "M", "B", "T", "q", "Q", "s", "S", "o", "N",
           "d", "U", "D", "Td", "qd", "Qd", "sd", "Sd", "od", "nd",
           "V", "uV", "dV", "tV", "qV", "QV", "sV", "SV", "oV", "nV",
           "TI", "uT", "dT", "tT", "qT", "QT", "sT", "ST", "oT", "nT"]


def round_to_sigfigs(num: float, sigfigs: int) -> float:
    if num == 0:
        return 0
    else:
        return round(num, sigfigs - int(math.floor(math.log10(abs(num)))) - 1)


def format_number(num: float) -> str:
    QUADRAGINTILLION = 10**123

    rounded = round_to_sigfigs(round_to_sigfigs(decimal.Decimal(num), 4), 4)

    if rounded < 0:
        raise Exception("FORMAT ERROR: NUMBER CANNOT BE NEGATIVE")
    elif rounded < TEN_THOUSAND:
        return "{:,}".format(rounded)
    elif rounded < QUADRAGINTILLION:
        order = math.floor(math.log10(rounded) / 3) * 3
        return "{:<05}{}".format(float(rounded / 10**order), 
                                 SYMBOLS[order // 3 - 1])
    else:
        raise Exception("FORMAT ERROR: NUMBER TOO LARGE")


def unformat_number(str_num: str) -> float:
    symbol = re.sub(r"[0-9.]", "", str_num)

    if symbol == "":
        return float(str_num)
    else:
        try:
            order = 3 * (SYMBOLS.index(symbol) + 1)
        except ValueError:
            raise Exception("UNFORMAT ERROR: INVALID SYMBOL")
        else:
            return float(decimal.Decimal(str_num[:-len(symbol)]) * 10**(order))

def format_time(seconds: float) -> str:
    rounded = round(seconds)
    minutes = rounded // 60
    seconds = rounded % 60
    return "{}m {}s".format(minutes, seconds)

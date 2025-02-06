import re
from typing import Final

pattern_season_suffix: Final = re.compile("第.季$")
pattern_web_dl: Final = re.compile(r"\b(web-dl|webdl)\b", re.IGNORECASE)
pattern_dovi: Final = re.compile(r"\b(dovi|DV|Dolby Vision)\b", re.IGNORECASE)
pattern_2160p: Final = re.compile(r"\b2160p\b", re.IGNORECASE)

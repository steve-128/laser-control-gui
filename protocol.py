import re
from typing import Optional, Tuple

_KEY_VALUE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[:=]\s*(.+?)\s*$")


def parse_key_value(line: str) -> Optional[Tuple[str, str]]:
    match = _KEY_VALUE_RE.match(line)
    if not match:
        return None
    key = match.group(1).strip().lower()
    value = match.group(2).strip()
    return key, value


def build_query(command: str) -> str:
    command = command.strip()
    if not command.endswith("?"):
        command = f"{command}?"
    return command
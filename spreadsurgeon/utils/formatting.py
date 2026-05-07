"""Formatação de saídas textuais e estruturadas."""

from typing import Any


SEP_DOUBLE = "=" * 72
SEP_SINGLE = "-" * 72
SEP_THIN   = "·" * 72


def section(title: str) -> str:
    return f"\n{SEP_DOUBLE}\n  {title.upper()}\n{SEP_DOUBLE}"


def subsection(title: str) -> str:
    return f"\n{SEP_SINGLE}\n  {title}\n{SEP_SINGLE}"


def bullet(text: str, icon: str = "•") -> str:
    return f"  {icon} {text}"


def status_line(field: str, status: str, detail: str = "") -> str:
    detail_str = f"  → {detail}" if detail else ""
    return f"  [{status}] {field}{detail_str}"


def table(rows: list[tuple[str, str]], col_width: int = 30) -> str:
    lines = []
    for label, value in rows:
        lines.append(f"  {label:<{col_width}} {value}")
    return "\n".join(lines)


def numbered_list(items: list[str], start: int = 1) -> str:
    return "\n".join(f"  {i + start}. {item}" for i, item in enumerate(items))


def score_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"  [{bar}] {score}/100"


def render_dict(d: dict[str, Any], indent: int = 2) -> str:
    pad = " " * indent
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            lines.append(render_dict(v, indent + 2))
        elif isinstance(v, list):
            lines.append(f"{pad}{k}:")
            for item in v:
                lines.append(f"{pad}  - {item}")
        else:
            lines.append(f"{pad}{k}: {v}")
    return "\n".join(lines)


def alert(text: str, level: str = "AVISO") -> str:
    border = "!" * (len(text) + 12)
    return f"\n  {border}\n  !!! {level}: {text} !!!\n  {border}"

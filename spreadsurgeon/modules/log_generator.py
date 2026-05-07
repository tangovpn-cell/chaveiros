"""Gerador de logs de alteração rastreáveis."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogEntry:
    timestamp: str
    action: str
    field: str
    before: str
    after: str
    sku: str
    row: int
    source: str     # "correção automática" | "sugestão humana" | "bloqueado"
    note: str = ""


@dataclass
class ChangeLog:
    session_id: str
    created_at: str
    entries: list[LogEntry] = field(default_factory=list)
    mode: str = "seguro"  # sempre "seguro" — nunca inventa dado

    def add(self, action: str, field: str, before: str, after: str,
            sku: str = "", row: int = 0,
            source: str = "sugestão humana", note: str = ""):
        self.entries.append(LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action=action,
            field=field,
            before=before,
            after=after,
            sku=sku,
            row=row,
            source=source,
            note=note,
        ))

    def to_text(self) -> str:
        lines = [
            f"=== LOG DE ALTERAÇÕES — Sessão {self.session_id} ===",
            f"Gerado em: {self.created_at}",
            f"Modo: {self.mode.upper()} (nenhum dado inventado)",
            f"Total de entradas: {len(self.entries)}",
            "",
        ]
        for i, e in enumerate(self.entries, 1):
            lines.append(f"[{i}] {e.timestamp}")
            lines.append(f"     SKU: {e.sku} | Linha: {e.row}")
            lines.append(f"     Ação: {e.action}")
            lines.append(f"     Campo: {e.field}")
            lines.append(f"     Antes: {e.before}")
            lines.append(f"     Depois: {e.after}")
            lines.append(f"     Fonte: {e.source}")
            if e.note:
                lines.append(f"     Obs: {e.note}")
            lines.append("")
        return "\n".join(lines)

    def to_csv_rows(self) -> list[dict]:
        return [
            {
                "timestamp": e.timestamp,
                "session":   self.session_id,
                "sku":       e.sku,
                "row":       e.row,
                "action":    e.action,
                "field":     e.field,
                "before":    e.before,
                "after":     e.after,
                "source":    e.source,
                "note":      e.note,
            }
            for e in self.entries
        ]


def new_log(session_id: str = "") -> ChangeLog:
    sid = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
    return ChangeLog(
        session_id=sid,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

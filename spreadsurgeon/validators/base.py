"""Base para todos os validadores de canal."""

from dataclasses import dataclass, field
from typing import Optional
from spreadsurgeon.config import Status


@dataclass
class FieldIssue:
    row: int
    sku: str
    field: str
    status: Status
    value: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    channel: str
    total_rows: int = 0
    valid_rows: int = 0
    issues: list[FieldIssue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    corrections: list[str] = field(default_factory=list)
    pending_human: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.status == Status.ERRO)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues
                   if i.status in (Status.VERIFICAR, Status.PENDENTE))

    @property
    def block_count(self) -> int:
        return sum(1 for i in self.issues
                   if i.status in (Status.BLOQUEIO_FISCAL,
                                   Status.RISCO_PUBLICACAO,
                                   Status.RISCO_PREJUIZO))


class BaseValidator:
    channel: str = "base"

    def validate(self, rows: list[dict]) -> ValidationResult:
        raise NotImplementedError

    def _issue(self, row: int, sku: str, field: str, status: Status,
               value: str, message: str, suggestion: str = "") -> FieldIssue:
        return FieldIssue(row=row, sku=sku, field=field, status=status,
                          value=value, message=message, suggestion=suggestion)

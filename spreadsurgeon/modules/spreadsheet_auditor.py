"""Auditoria completa de planilhas: estrutura, dados e integridade."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import Status
from spreadsurgeon.parsers.file_parser import ParsedTable
from spreadsurgeon.utils.text_utils import (safe_str, validate_ean,
                                             validate_ncm, price_to_float,
                                             is_scientific_notation)


@dataclass
class AuditIssue:
    location: str       # ex: "Aba:Produtos | Linha 5 | Col: ean"
    severity: str       # ERRO | AVISO | INFO
    status: Status
    message: str
    suggestion: str = ""


@dataclass
class AuditReport:
    source: str
    total_sheets: int = 0
    total_rows: int = 0
    total_cols: int = 0
    issues: list[AuditIssue] = field(default_factory=list)
    analysis: dict = field(default_factory=dict)
    safe_corrections: list[str] = field(default_factory=list)
    human_pending: list[str] = field(default_factory=list)
    correction_plan: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERRO")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "AVISO")


# Palavras que sugerem campo de preço/custo
_PRICE_KEYWORDS = {"preco", "preço", "price", "valor", "custo", "cost",
                   "venda", "atacado", "varejo"}
_SKU_KEYWORDS   = {"sku", "codigo", "código", "cod", "ref", "referencia",
                   "referência"}
_EAN_KEYWORDS   = {"ean", "gtin", "barcode", "codigo_barras"}
_NCM_KEYWORDS   = {"ncm"}
_STOCK_KEYWORDS = {"estoque", "stock", "qty", "quantidade", "saldo"}


def _col_likely(col: str, keywords: set[str]) -> bool:
    col_l = col.lower().replace("_", "").replace("-", "")
    return any(k.replace("_", "") in col_l for k in keywords)


def audit_table(table: ParsedTable, sheet_label: str = "") -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    label = sheet_label or table.sheet_name or table.source_type

    # Cabeçalho vazio
    empty_headers = [h for h in table.headers if not h or h == "coluna_vazia"]
    if empty_headers:
        issues.append(AuditIssue(
            location=f"Aba:{label} | Cabeçalho",
            severity="AVISO",
            status=Status.VERIFICAR,
            message=f"{len(empty_headers)} coluna(s) sem cabeçalho detectadas",
            suggestion="Verificar se há colunas ocultas ou células mescladas no cabeçalho"
        ))

    skus_seen: dict[str, int] = {}
    eans_seen: dict[str, int] = {}

    for i, row in enumerate(table.rows, 2):
        loc_prefix = f"Aba:{label} | Linha {i}"

        # SKU duplicado
        for col in table.headers:
            if _col_likely(col, _SKU_KEYWORDS):
                val = safe_str(row.get(col, ""))
                if val:
                    if val in skus_seen:
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.ERRO,
                            message=f"SKU duplicado '{val}' — já na linha {skus_seen[val]}",
                            suggestion="Corrigir ou remover linha duplicada"
                        ))
                    else:
                        skus_seen[val] = i

        # Preço zerado / negativo / custo > preço
        prices_in_row: dict[str, float] = {}
        for col in table.headers:
            if _col_likely(col, _PRICE_KEYWORDS):
                val = safe_str(row.get(col, ""))
                if not val:
                    issues.append(AuditIssue(
                        location=f"{loc_prefix} | Col:{col}",
                        severity="AVISO",
                        status=Status.PENDENTE,
                        message=f"Campo '{col}' vazio",
                        suggestion="Preencher ou justificar campo vazio"
                    ))
                else:
                    pf = price_to_float(val)
                    if pf is None:
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.ERRO,
                            message=f"Valor não numérico em campo de preço: '{val}'",
                            suggestion="Corrigir para valor decimal (ex: 29,90 ou 29.90)"
                        ))
                    elif pf == 0:
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.RISCO_PUBLICACAO,
                            message=f"Preço zerado em '{col}'",
                            suggestion="Preencher preço antes de publicar"
                        ))
                    elif pf < 0:
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.RISCO_PREJUIZO,
                            message=f"Preço negativo em '{col}': {val}",
                            suggestion="Corrigir valor"
                        ))
                    else:
                        prices_in_row[col] = pf

        # Custo > Preço
        costs = {k: v for k, v in prices_in_row.items()
                 if any(x in k for x in ("custo", "cost"))}
        sales = {k: v for k, v in prices_in_row.items()
                 if any(x in k for x in ("venda", "price", "preco", "preço"))}
        if costs and sales:
            max_cost  = max(costs.values())
            min_price = min(sales.values())
            if max_cost >= min_price:
                issues.append(AuditIssue(
                    location=f"{loc_prefix}",
                    severity="ERRO",
                    status=Status.RISCO_PREJUIZO,
                    message=f"Custo ({max_cost}) ≥ Preço de venda ({min_price})",
                    suggestion="Revisar custo e preço para garantir margem positiva"
                ))

        # Estoque negativo
        for col in table.headers:
            if _col_likely(col, _STOCK_KEYWORDS):
                val = safe_str(row.get(col, ""))
                if val:
                    try:
                        if float(val.replace(",", ".")) < 0:
                            issues.append(AuditIssue(
                                location=f"{loc_prefix} | Col:{col}",
                                severity="AVISO",
                                status=Status.RISCO_PUBLICACAO,
                                message=f"Estoque negativo: {val}",
                                suggestion="Corrigir saldo de estoque"
                            ))
                    except ValueError:
                        pass

        # EAN: notação científica ou inválido
        for col in table.headers:
            if _col_likely(col, _EAN_KEYWORDS):
                val = safe_str(row.get(col, ""))
                if val:
                    if is_scientific_notation(val):
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.ERRO,
                            message=f"EAN em notação científica: '{val}'",
                            suggestion="Formatar coluna como Texto antes de inserir EAN"
                        ))
                    else:
                        ok, msg = validate_ean(val)
                        if not ok:
                            issues.append(AuditIssue(
                                location=f"{loc_prefix} | Col:{col}",
                                severity="AVISO",
                                status=Status.VERIFICAR,
                                message=f"EAN inválido: {msg}",
                                suggestion="Confirmar EAN na embalagem ou nota fiscal"
                            ))
                        elif val in eans_seen:
                            issues.append(AuditIssue(
                                location=f"{loc_prefix} | Col:{col}",
                                severity="AVISO",
                                status=Status.VERIFICAR,
                                message=f"EAN '{val}' duplicado — já na linha {eans_seen[val]}",
                                suggestion="Produtos distintos não devem compartilhar EAN"
                            ))
                        else:
                            eans_seen[val] = i

        # NCM inválido
        for col in table.headers:
            if _col_likely(col, _NCM_KEYWORDS):
                val = safe_str(row.get(col, ""))
                if val:
                    ok, msg = validate_ncm(val)
                    if not ok:
                        issues.append(AuditIssue(
                            location=f"{loc_prefix} | Col:{col}",
                            severity="ERRO",
                            status=Status.BLOQUEIO_FISCAL,
                            message=f"NCM inválido: {msg}",
                            suggestion="Corrigir NCM com tabela TIPI ou contador"
                        ))

        # Notação científica em qualquer campo
        for col in table.headers:
            val = safe_str(row.get(col, ""))
            if val and is_scientific_notation(val) and not _col_likely(col, _EAN_KEYWORDS):
                issues.append(AuditIssue(
                    location=f"{loc_prefix} | Col:{col}",
                    severity="AVISO",
                    status=Status.VERIFICAR,
                    message=f"Notação científica detectada em '{col}': {val}",
                    suggestion="Formatar coluna como Texto no Excel antes de exportar"
                ))

    return issues


def audit(tables: list[ParsedTable], source: str = "") -> AuditReport:
    report = AuditReport(source=source or "planilha")
    report.total_sheets = len(tables)
    report.total_rows   = sum(len(t.rows) for t in tables)
    report.total_cols   = max((len(t.headers) for t in tables), default=0)

    for i, table in enumerate(tables):
        label = table.sheet_name or f"Aba_{i+1}"
        issues = audit_table(table, label)
        report.issues.extend(issues)

        # Warnings do parser
        for w in table.warnings:
            report.issues.append(AuditIssue(
                location=f"Aba:{label} | Parser",
                severity="AVISO",
                status=Status.VERIFICAR,
                message=w,
                suggestion="Verificar formato do arquivo"
            ))

    report.analysis = {
        "total_sheets": report.total_sheets,
        "total_rows":   report.total_rows,
        "total_cols":   report.total_cols,
        "erros":        report.error_count,
        "avisos":       report.warning_count,
    }

    report.safe_corrections = [
        "Converter EANs em notação científica para texto (valor inteiro)",
        "Identificar e remover SKUs duplicados",
        "Sinalizar preços zerados para revisão humana",
    ]
    report.human_pending = [
        "Validar NCMs com contador — nunca inferir dado fiscal",
        "Confirmar EANs inválidos na embalagem ou nota fiscal",
        "Verificar custo vs. preço para garantir margem",
        "Avaliar se estoque negativo é erro de lançamento ou devolução",
    ]
    report.correction_plan = [
        "1. Corrigir todos os BLOQUEIO FISCAL (NCM, CEST) antes de qualquer ação",
        "2. Corrigir ERRO de EAN em notação científica",
        "3. Resolver SKUs duplicados",
        "4. Preencher preços zerados ou negativos",
        "5. Verificar margem (custo < preço)",
        "6. Revisar estoque negativo",
        "7. Preencher campos PENDENTE com dados reais",
        "8. Executar /gerar_checklist antes de importar",
    ]
    report.log = [
        f"Auditoria executada em {report.total_rows} linhas / {report.total_sheets} aba(s)",
        f"Erros: {report.error_count} | Avisos: {report.warning_count}",
        "Modo seguro ativo: nenhum dado foi alterado automaticamente",
    ]
    return report

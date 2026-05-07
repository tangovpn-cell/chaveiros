"""Criador de campanhas comerciais com validação operacional."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import Status
from spreadsurgeon.utils.text_utils import safe_str, price_to_float


@dataclass
class CampaignInput:
    name: str
    objective: str
    target_audience: str
    skus: list[str]
    main_headline: str
    selling_points: list[str]
    offer: str
    channel: str
    creative_suggestion: str
    success_metric: str
    # Dados de validação operacional
    stock_per_sku: dict = field(default_factory=dict)   # {sku: qtd}
    price_per_sku: dict = field(default_factory=dict)   # {sku: float}
    margin_per_sku: dict = field(default_factory=dict)  # {sku: float%}
    catalog_ready: dict = field(default_factory=dict)   # {sku: bool}
    images_ok: dict = field(default_factory=dict)       # {sku: bool}
    title_ok: dict = field(default_factory=dict)        # {sku: bool}


@dataclass
class CampaignResult:
    name: str
    objective: str
    target_audience: str
    skus: list[str]
    main_headline: str
    selling_points: list[str]
    offer: str
    recommended_channel: str
    creative_suggestion: str
    success_metric: str
    operational_risk: str
    validation_status: str      # APROVADA | BLOQUEADA | PENDENTE
    blocking_issues: list[str] = field(default_factory=list)
    pending_validations: list[str] = field(default_factory=list)
    approved_skus: list[str] = field(default_factory=list)
    blocked_skus: list[str] = field(default_factory=list)


def _validate_campaign_operationally(inp: CampaignInput) -> tuple[list[str], list[str], list[str], list[str]]:
    """Retorna (bloqueios, pendencias, aprovados, bloqueados)."""
    blockers: list[str] = []
    pending: list[str] = []
    approved: list[str] = []
    blocked: list[str] = []

    for sku in inp.skus:
        sku_issues = []

        # Estoque
        stock = inp.stock_per_sku.get(sku)
        if stock is not None:
            if stock <= 0:
                sku_issues.append(f"Estoque zero ({stock})")
        else:
            pending.append(f"SKU {sku}: estoque não informado — validar antes de ativar")

        # Preço
        price = inp.price_per_sku.get(sku)
        if price is not None:
            if price <= 0:
                sku_issues.append(f"Preço inválido ({price})")
        else:
            pending.append(f"SKU {sku}: preço não informado")

        # Margem
        margin = inp.margin_per_sku.get(sku)
        if margin is not None:
            if margin < 0:
                sku_issues.append(f"Margem negativa ({margin:.1f}%) — RISCO DE PREJUÍZO")
            elif margin < 5:
                sku_issues.append(f"Margem muito baixa ({margin:.1f}%) — risco em campanha")
        else:
            pending.append(f"SKU {sku}: margem não informada")

        # Cadastro
        if inp.catalog_ready.get(sku) is False:
            sku_issues.append("Cadastro incompleto")
        elif sku not in inp.catalog_ready:
            pending.append(f"SKU {sku}: cadastro não validado")

        # Imagens
        if inp.images_ok.get(sku) is False:
            sku_issues.append("Imagem ausente ou inválida")
        elif sku not in inp.images_ok:
            pending.append(f"SKU {sku}: imagens não validadas")

        # Título
        if inp.title_ok.get(sku) is False:
            sku_issues.append("Título inadequado")

        if sku_issues:
            blocked.append(sku)
            for issue in sku_issues:
                blockers.append(f"[SKU {sku}] {issue}")
        else:
            if not any(sku in p for p in pending):
                approved.append(sku)

    return blockers, pending, approved, blocked


def create_campaign(inp: CampaignInput) -> CampaignResult:
    blockers, pending, approved, blocked_skus = _validate_campaign_operationally(inp)

    if blockers:
        status = "BLOQUEADA"
        risk = f"Campanha bloqueada por {len(blockers)} problema(s) operacional(is)"
    elif pending:
        status = "PENDENTE"
        risk = f"{len(pending)} validação(ões) pendente(s) antes da ativação"
    else:
        status = "APROVADA"
        risk = "Nenhum risco operacional identificado nos dados fornecidos"

    return CampaignResult(
        name=inp.name,
        objective=inp.objective,
        target_audience=inp.target_audience,
        skus=inp.skus,
        main_headline=inp.main_headline,
        selling_points=inp.selling_points,
        offer=inp.offer,
        recommended_channel=inp.channel,
        creative_suggestion=inp.creative_suggestion,
        success_metric=inp.success_metric,
        operational_risk=risk,
        validation_status=status,
        blocking_issues=blockers,
        pending_validations=pending,
        approved_skus=approved,
        blocked_skus=blocked_skus,
    )

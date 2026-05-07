"""Criador de kits com validação de estoque e lógica comercial."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.utils.text_utils import safe_str


@dataclass
class KitComponent:
    sku: str
    name: str
    price: float
    stock: float
    qty_in_kit: int = 1


@dataclass
class KitInput:
    name: str
    components: list[KitComponent]
    logic: str          # ex: "Fechadura + cilindro + 2 chaves"
    channel: str
    discount_pct: float = 0.0
    suggested_offer: str = ""


@dataclass
class KitResult:
    name: str
    skus: list[str]
    logic: str
    kit_price: float
    individual_price: float
    discount_applied: float
    ideal_channel: str
    suggested_offer: str
    stock_risk: str
    bottleneck_sku: str     # SKU com menor estoque
    bottleneck_qty: float
    validation_needed: list[str]
    status: str             # VIAVEL | RISCO | BLOQUEADO


def create_kit(inp: KitInput) -> KitResult:
    validation_needed: list[str] = []
    issues: list[str] = []

    # Preço individual
    individual_price = sum(c.price * c.qty_in_kit for c in inp.components)

    # Preço do kit com desconto
    kit_price = individual_price * (1 - inp.discount_pct / 100)

    # Estoque limitante
    bottleneck: Optional[KitComponent] = None
    for comp in inp.components:
        if comp.stock <= 0:
            issues.append(
                f"SKU {comp.sku} ({comp.name}) com estoque zero — kit bloqueado"
            )
        else:
            kit_qty = comp.stock // comp.qty_in_kit
            if bottleneck is None or kit_qty < (bottleneck.stock // bottleneck.qty_in_kit):
                bottleneck = comp

    if not bottleneck:
        status = "BLOQUEADO"
        stock_risk = "Todos os componentes com estoque zero — kit inviável"
        bn_sku = "N/A"
        bn_qty = 0.0
    else:
        bn_qty = bottleneck.stock // bottleneck.qty_in_kit
        bn_sku = bottleneck.sku
        if bn_qty < 5:
            status = "RISCO"
            stock_risk = (
                f"Estoque do kit limitado por SKU {bn_sku} ({bottleneck.name}): "
                f"apenas {bn_qty:.0f} kit(s) possível(is)"
            )
        else:
            status = "VIAVEL" if not issues else "RISCO"
            stock_risk = (
                f"Capacidade máxima de {bn_qty:.0f} kit(s) "
                f"(limitado por SKU {bn_sku})"
            )

    if issues:
        status = "BLOQUEADO" if any("zero" in i for i in issues) else "RISCO"
        validation_needed.extend(issues)

    # Validações necessárias
    for comp in inp.components:
        if not comp.name:
            validation_needed.append(f"SKU {comp.sku}: nome não informado")
        if comp.price <= 0:
            validation_needed.append(f"SKU {comp.sku}: preço inválido ou zerado")

    if inp.discount_pct == 0:
        validation_needed.append("Desconto do kit não definido — sugerir 10-15%")

    offer = inp.suggested_offer or (
        f"Kit {inp.name} por R$ {kit_price:.2f} "
        f"(economia de R$ {individual_price - kit_price:.2f})"
    )

    return KitResult(
        name=inp.name,
        skus=[c.sku for c in inp.components],
        logic=inp.logic,
        kit_price=round(kit_price, 2),
        individual_price=round(individual_price, 2),
        discount_applied=inp.discount_pct,
        ideal_channel=inp.channel,
        suggested_offer=offer,
        stock_risk=stock_risk,
        bottleneck_sku=bn_sku,
        bottleneck_qty=bn_qty,
        validation_needed=validation_needed,
        status=status,
    )

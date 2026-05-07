"""Módulo de estratégia comercial: análise e recomendação por produto."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.utils.text_utils import safe_str, price_to_float


@dataclass
class ProductProfile:
    sku: str
    name: str
    category: str = ""
    brand: str = ""
    channel: str = ""
    quantity_sold: float = 0
    revenue: float = 0
    margin_pct: float = 0
    stock: float = 0
    price: float = 0
    cost: float = 0
    cancellations: float = 0
    state: str = ""
    payment_method: str = ""
    trend: str = ""          # alta | estavel | queda


@dataclass
class StrategyRec:
    sku: str
    name: str
    segment: str            # alto_giro | alto_ticket | kit | marketplace | recompra | trafego | bloqueado
    recommended_action: str
    ad_type: str
    ideal_channel: str
    suggested_offer: str
    operational_risk: str
    next_step: str
    priority: int = 1       # 1=alta, 2=média, 3=baixa


@dataclass
class StrategyReport:
    diagnosis: list[str] = field(default_factory=list)
    priority_products: list[str] = field(default_factory=list)
    segments: dict = field(default_factory=dict)
    recommendations: list[StrategyRec] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def _classify_product(p: ProductProfile) -> str:
    """Classifica o produto em um dos segmentos estratégicos."""
    # Bloqueado: sem estoque, sem margem, sem cadastro confiável
    if p.stock <= 0:
        return "bloqueado"
    if p.margin_pct < 0:
        return "bloqueado"
    if p.price <= 0:
        return "bloqueado"
    # Recompra: alta frequência, ticket médio/baixo
    if p.quantity_sold > 20 and p.price < 80:
        return "recompra"
    # Alto giro e baixo ticket
    if p.quantity_sold > 10 and p.price < 120:
        return "alto_giro"
    # Alto ticket e boa margem
    if p.price > 200 and p.margin_pct > 25:
        return "alto_ticket"
    # Kit: produtos com baixo giro mas complementares (heurística simples)
    if p.quantity_sold < 5 and p.margin_pct > 20:
        return "kit"
    # Marketplace: produtos com boa margem e estoque
    if p.margin_pct > 15 and p.stock > 5:
        return "marketplace"
    # Tráfego: produtos com potencial mas baixa venda
    if p.quantity_sold < 5 and p.price > 50 and p.margin_pct > 10:
        return "trafego"
    return "marketplace"


_SEGMENT_LABELS = {
    "alto_giro":    "Alto Giro e Baixo Ticket",
    "alto_ticket":  "Alto Ticket e Boa Margem",
    "kit":          "Produtos para Kits",
    "marketplace":  "Produtos para Marketplace",
    "recompra":     "Produtos para Recompra",
    "trafego":      "Produtos para Tráfego Pago",
    "bloqueado":    "Não Deve ser Anunciado Ainda",
}

_AD_TYPE = {
    "alto_giro":    "Anúncio clássico ou premium com frete grátis",
    "alto_ticket":  "Anúncio premium com parcelamento destacado",
    "kit":          "Anúncio de kit/combo com desconto progressivo",
    "marketplace":  "Anúncio padrão com foco em preço competitivo",
    "recompra":     "Anúncio recorrente com fidelização / cupom",
    "trafego":      "Campanha de awareness com tráfego pago",
    "bloqueado":    "NÃO ANUNCIAR — regularizar cadastro primeiro",
}

_IDEAL_CHANNEL = {
    "alto_giro":    "Shopee | Mercado Livre | WhatsApp",
    "alto_ticket":  "Site próprio | Mercado Livre Premium | Televendas",
    "kit":          "Site próprio | WhatsApp | Tray",
    "marketplace":  "Mercado Livre | Shopee | Magalu",
    "recompra":     "WhatsApp | Site com recorrência | Televendas",
    "trafego":      "Meta Ads | Google Shopping | Mercado Livre",
    "bloqueado":    "Nenhum — produto bloqueado",
}


def _build_rec(p: ProductProfile, segment: str) -> StrategyRec:
    offer = ""
    risk  = ""
    next_ = ""

    if segment == "bloqueado":
        offer = "Sem oferta — produto bloqueado"
        risk  = "Estoque zero, margem negativa ou preço inválido"
        next_ = "Regularizar estoque, custo e preço antes de anunciar"
    elif segment == "alto_giro":
        margin_val = p.price * (1 - p.margin_pct / 100)
        offer = f"Preço: R$ {p.price:.2f} | Oferta de frete grátis acima de X"
        risk  = "Risco de ruptura de estoque por alta demanda"
        next_ = "Garantir reposição de estoque | Ativar anúncio com frete"
    elif segment == "alto_ticket":
        offer = f"Parcelado em até 12x | Preço: R$ {p.price:.2f}"
        risk  = "Ticket alto exige imagem de alta qualidade e ficha completa"
        next_ = "Completar ficha técnica e imagens antes de promover"
    elif segment == "kit":
        offer = "Kit com desconto de 10-15% vs. compra individual"
        risk  = "Risco de estoque se componentes do kit tiverem saldos diferentes"
        next_ = "Mapear componentes do kit e validar estoque conjunto"
    elif segment == "recompra":
        offer = "Cupom de recompra | Clube de benefícios"
        risk  = "Dependência de recorrência — monitorar churn"
        next_ = "Criar régua de comunicação no WhatsApp ou e-mail"
    elif segment == "trafego":
        offer = f"Destaque de benefício principal | Preço: R$ {p.price:.2f}"
        risk  = "Custo de aquisição pode não compensar com margem baixa"
        next_ = "Calcular CAC máximo aceitável antes de ativar campanha"
    else:  # marketplace
        offer = f"Preço competitivo: R$ {p.price:.2f}"
        risk  = "Concorrência de preço — validar margem após fees do canal"
        next_ = "Comparar preço com concorrentes no canal antes de ativar"

    return StrategyRec(
        sku=p.sku,
        name=p.name,
        segment=segment,
        recommended_action=_SEGMENT_LABELS[segment],
        ad_type=_AD_TYPE[segment],
        ideal_channel=_IDEAL_CHANNEL[segment],
        suggested_offer=offer,
        operational_risk=risk,
        next_step=next_,
        priority=1 if segment not in ("bloqueado", "trafego") else 3,
    )


def create_strategy(products: list[ProductProfile]) -> StrategyReport:
    report = StrategyReport()

    if not products:
        report.diagnosis.append("Nenhum produto fornecido para análise")
        return report

    segments: dict[str, list[str]] = {s: [] for s in _SEGMENT_LABELS}
    recs: list[StrategyRec] = []

    total_revenue = sum(p.revenue for p in products)
    total_qty     = sum(p.quantity_sold for p in products)
    blocked_count = 0

    for p in products:
        seg = _classify_product(p)
        segments[seg].append(p.sku)
        recs.append(_build_rec(p, seg))
        if seg == "bloqueado":
            blocked_count += 1
            report.blocked.append(
                f"[BLOQUEADO] SKU {p.sku} — {p.name}: "
                f"estoque={p.stock} | margem={p.margin_pct:.1f}% | preço={p.price:.2f}"
            )

    report.segments = {_SEGMENT_LABELS[k]: v for k, v in segments.items() if v}
    report.recommendations = sorted(recs, key=lambda r: r.priority)

    # Diagnóstico
    report.diagnosis = [
        f"Total de produtos analisados: {len(products)}",
        f"Receita total identificada: R$ {total_revenue:,.2f}",
        f"Volume total vendido: {total_qty:.0f} unidades",
        f"Produtos bloqueados (não devem ser anunciados): {blocked_count}",
        f"Segmentos identificados: {sum(1 for v in segments.values() if v)}",
    ]

    # Prioridades
    priority_segs = ["alto_giro", "alto_ticket", "recompra"]
    for seg in priority_segs:
        for sku in segments[seg]:
            report.priority_products.append(f"[{_SEGMENT_LABELS[seg]}] {sku}")

    report.next_steps = [
        "1. Regularizar todos os produtos BLOQUEADOS antes de qualquer campanha",
        "2. Priorizar produtos de alto giro para anúncios com frete",
        "3. Montar kits com produtos de baixo giro e boa margem",
        "4. Criar régua de recompra para produtos recorrentes",
        "5. Calcular CAC antes de investir em tráfego pago",
        "6. Nunca anunciar produto sem estoque, margem e cadastro confiável",
    ]

    return report

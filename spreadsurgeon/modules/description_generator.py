"""Gerador de descrição técnica em HTML para e-commerce."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import (HTML_SECTION_STYLE, HTML_TABLE_STYLE,
                                  HTML_ROW_EVEN, HTML_ROW_ODD,
                                  HTML_TD_LABEL, HTML_TD_VALUE, Status)
from spreadsurgeon.utils.text_utils import safe_str
from spreadsurgeon.modules.title_standardizer import standardize_title


@dataclass
class DescriptionData:
    """Dados de entrada para geração da descrição."""
    sku: str = ""
    raw_title: str = ""
    category: str = ""
    brand: str = ""
    specs: dict = field(default_factory=dict)        # campo: valor
    bullets: list[str] = field(default_factory=list) # benefícios
    compatibility: list[str] = field(default_factory=list)
    in_the_box: list[str] = field(default_factory=list)
    installation_notes: str = ""
    usage_notes: str = ""
    raw_description: str = ""


@dataclass
class DescriptionResult:
    sku: str
    diagnosis: list[str]
    optimized_title: str
    html_description: str
    missing_fields: list[str]
    marketplace_description: str
    suggested_attributes: dict
    warnings: list[str] = field(default_factory=list)


def _h3(text: str) -> str:
    return f'<h3 {HTML_SECTION_STYLE}>{text}</h3>'


def _table(rows: list[tuple[str, str]]) -> str:
    cells = []
    for i, (label, value) in enumerate(rows):
        style = HTML_ROW_EVEN if i % 2 == 0 else HTML_ROW_ODD
        cells.append(
            f'<tr {style}>'
            f'<td {HTML_TD_LABEL}>{label}</td>'
            f'<td {HTML_TD_VALUE}>{value}</td>'
            f'</tr>'
        )
    return (
        f'<table {HTML_TABLE_STYLE}>'
        '<tbody>'
        + "".join(cells) +
        '</tbody></table>'
    )


def _section(title: str, content: str) -> str:
    return f"{_h3(title)}\n{content}\n"


def _specs_table(specs: dict) -> str:
    if not specs:
        return '<p style="color:#999;font-family:Arial,sans-serif;">Especificações técnicas a confirmar.</p>'
    rows = [(k, v) for k, v in specs.items() if v]
    return _table(rows)


def _benefits_table(bullets: list[str]) -> str:
    if not bullets:
        return '<p style="color:#999;font-family:Arial,sans-serif;">Benefícios a confirmar.</p>'
    rows = [(f"✓ {b}", "") for b in bullets]
    return _table(rows)


def _compatibility_table(items: list[str]) -> str:
    if not items:
        return '<p style="color:#999;font-family:Arial,sans-serif;">Compatibilidade a verificar — NUNCA inventar aplicação.</p>'
    rows = [(c, "") for c in items]
    return _table(rows)


def _inbox_table(items: list[str]) -> str:
    if not items:
        return '<p style="color:#999;font-family:Arial,sans-serif;">Itens inclusos a confirmar na embalagem.</p>'
    rows = [(f"• {it}", "") for it in items]
    return _table(rows)


def _detect_missing(data: DescriptionData) -> list[str]:
    missing = []
    if not data.brand:
        missing.append("marca")
    if not data.specs:
        missing.append("especificações técnicas (dimensões, material, peso)")
    if not data.bullets:
        missing.append("benefícios e diferenciais do produto")
    if not data.compatibility and data.category in ("Automotivo", "Chaves", "Cilindros"):
        missing.append("compatibilidade e aplicação (crítico para categoria automotiva)")
    if not data.in_the_box:
        missing.append("itens inclusos na embalagem")
    if not data.installation_notes:
        missing.append("instruções de instalação")
    return missing


def _diagnose(data: DescriptionData) -> list[str]:
    diag = []
    if not data.raw_title:
        diag.append("PENDENTE: Título vazio — impossível gerar descrição completa")
    if not data.specs:
        diag.append("PENDENTE: Especificações técnicas ausentes — campos marcados como 'a confirmar'")
    if not data.brand:
        diag.append("VERIFICAR: Marca não informada")
    if data.category in ("Automotivo", "Chaves") and not data.compatibility:
        diag.append("VERIFICAR: Compatibilidade/aplicação ausente para categoria automotiva — NÃO será inventada")
    if not data.in_the_box:
        diag.append("PENDENTE: Itens inclusos não informados — descrição incompleta")
    if not diag:
        diag.append("Dados suficientes para geração de descrição técnica")
    return diag


def generate_html_description(data: DescriptionData) -> DescriptionResult:
    missing = _detect_missing(data)
    diagnosis = _diagnose(data)
    warnings: list[str] = []

    # Título otimizado
    title_result = standardize_title(
        raw_title=data.raw_title or "PENDENTE",
        category=data.category,
        brand=data.brand,
        channel="site",
    )
    optimized_title = title_result.final_title

    # Resumo do produto
    summary_text = data.raw_description or (
        f"{optimized_title}. " +
        (f"Marca: {data.brand}. " if data.brand else "") +
        (f"Categoria: {data.category}." if data.category else "")
    )
    summary_rows = [("Produto", optimized_title)]
    if data.brand:
        summary_rows.append(("Marca", data.brand))
    if data.category:
        summary_rows.append(("Categoria", data.category))
    if data.sku:
        summary_rows.append(("SKU / Referência", data.sku))

    # HTML principal
    sections = []

    sections.append(_section(
        "📦 Resumo do Produto",
        _table(summary_rows)
    ))

    sections.append(_section(
        "🔧 Aplicação e Compatibilidade",
        _compatibility_table(data.compatibility)
    ))

    sections.append(_section(
        "📐 Especificações Técnicas",
        _specs_table(data.specs)
    ))

    sections.append(_section(
        "⭐ Benefícios e Diferenciais",
        _benefits_table(data.bullets)
    ))

    install_content = (
        f'<p style="font-family:Arial,sans-serif;font-size:13px;padding:8px;">'
        f'{data.installation_notes or "Instruções de instalação a confirmar com fabricante."}'
        f'</p>'
    )
    if data.usage_notes:
        install_content += (
            f'<p style="font-family:Arial,sans-serif;font-size:13px;padding:8px;">'
            f'<strong>Uso:</strong> {data.usage_notes}'
            f'</p>'
        )
    sections.append(_section("🔨 Instalação e Uso", install_content))

    sections.append(_section(
        "📋 Itens Inclusos",
        _inbox_table(data.in_the_box)
    ))

    disclaimer = (
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#888;'
        'margin-top:16px;border-top:1px solid #ddd;padding-top:8px;">'
        'Imagens meramente ilustrativas. Especificações sujeitas a alteração '
        'pelo fabricante sem aviso prévio. Consulte o manual do produto.'
        '</p>'
    )

    html = (
        '<div style="font-family:Arial,sans-serif;max-width:800px;'
        'margin:0 auto;padding:8px;">\n'
        + "\n".join(sections)
        + disclaimer
        + '\n</div>'
    )

    # Descrição complementar para marketplace (texto plano)
    marketplace_parts = [optimized_title]
    if data.brand:
        marketplace_parts.append(f"Marca: {data.brand}")
    if data.specs:
        marketplace_parts.append("Especificações: " +
                                  " | ".join(f"{k}: {v}" for k, v in data.specs.items()))
    if data.bullets:
        marketplace_parts.append("Benefícios: " + " | ".join(data.bullets))
    marketplace_desc = ". ".join(marketplace_parts)

    # Atributos sugeridos
    suggested_attrs: dict = {}
    for k, v in data.specs.items():
        suggested_attrs[k] = v
    if data.brand:
        suggested_attrs["marca"] = data.brand
    if data.category:
        suggested_attrs["categoria"] = data.category

    if missing:
        warnings.append(
            "MODO SEGURO: campos ausentes foram marcados como 'a confirmar'. "
            "NUNCA foram inventados dados."
        )

    return DescriptionResult(
        sku=data.sku,
        diagnosis=diagnosis,
        optimized_title=optimized_title,
        html_description=html,
        missing_fields=missing,
        marketplace_description=marketplace_desc,
        suggested_attributes=suggested_attrs,
        warnings=warnings,
    )

"""Padronizador de títulos por categoria de produto."""

import re
from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import CATEGORIAS, TITULO_MAX
from spreadsurgeon.utils.text_utils import (safe_str, extract_internal_code,
                                             title_case_br)


@dataclass
class TitleResult:
    original: str
    category: str
    structure_applied: str
    final_title: str
    adjustments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    internal_code: Optional[str] = None
    length: int = 0

    def __post_init__(self):
        self.length = len(self.final_title)


# Estruturas preferenciais por categoria
CATEGORY_STRUCTURES = {
    "Chaves": "Chave + Tipo + Marca + Código",
    "Fechaduras Pado": "Fechadura + Tipo/Modelo + Acabamento + Chave + Pado",
    "Cadeados": "Cadeado + Largura/Tipo + Aro + Material + Marca",
    "Cilindros": "Cilindro + Tipo + Medidas (ex+in) + Acabamento + Marca",
    "Dobradiças": "Dobradiça + Tipo + Material + Medida + Acabamento",
    "Acessórios": "Acessório + Tipo + Material + Aplicação + Medida",
    "Digitais": "Fechadura Digital + Tipo + Função + Marca + Modelo",
    "Puxadores": "Puxador + Tipo + Material + Medida + Acabamento",
    "Automotivo": "Tipo + Marca do Produto + Aplicação/Modelo + Código",
    "Pinos e Molas": "Pino/Mola + Tipo + Medida + Quantidade + Marca",
    "Ferragens": "Tipo de Ferragem + Material + Medida + Aplicação",
    "Ferramentas": "Ferramenta + Tipo + Especificação + Marca",
}

# Abreviações a evitar no início
AVOID_START = re.compile(
    r"^(ref\.?\s*|cód\.?\s*|código\s*|code\s*|item\s*|produto\s*)",
    re.IGNORECASE
)

# Padrão: código entre parênteses no início
CODE_AT_START = re.compile(r"^\(([A-Za-z0-9\-_/]+)\)\s*")


def detect_category(title: str) -> str:
    """Infere categoria pelo título. Retorna categoria ou 'Geral'."""
    t = title.lower()
    rules = [
        (["fechadura digital", "digital", "biométrica", "biometrica"], "Digitais"),
        (["fechadura", "trinco", "trava"], "Fechaduras Pado"),
        (["cadeado"], "Cadeados"),
        (["cilindro", "miolo", "segredo"], "Cilindros"),
        (["dobradiça", "dobradica", "dobradiças"], "Dobradiças"),
        (["puxador"], "Puxadores"),
        (["chave", "canivete", "tetra"], "Chaves"),
        (["pino", "mola", "molas", "pinos"], "Pinos e Molas"),
        (["automotivo", "carro", "veículo", "veiculo", "transponder",
          "codificada", "codificado", "lâmina"], "Automotivo"),
        (["dobradiça", "parafuso", "rolamento", "trilho", "corrediça"], "Ferragens"),
        (["chave de fenda", "alicate", "martelo", "broca", "chave combinada",
          "extrator", "calibrador"], "Ferramentas"),
    ]
    for keywords, cat in rules:
        if any(k in t for k in keywords):
            return cat
    return "Acessórios"


def _remove_redundant_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _move_code_to_end(title: str) -> tuple[str, Optional[str]]:
    """Código no início move para o final."""
    m = CODE_AT_START.match(title)
    if m:
        code = m.group(1)
        rest = title[m.end():].strip()
        return rest, code
    return extract_internal_code(title)


def standardize_title(
    raw_title: str,
    category: str = "",
    brand: str = "",
    channel: str = "site",
    max_len: int = 0,
) -> TitleResult:
    title = safe_str(raw_title).strip()
    adjustments: list[str] = []
    warnings: list[str] = []

    if not title:
        return TitleResult(
            original=raw_title, category="PENDENTE",
            structure_applied="N/A",
            final_title="PENDENTE",
            warnings=["Título vazio — não é possível padronizar"],
        )

    # 1. Detectar categoria
    if not category or category == "Geral":
        category = detect_category(title)
        adjustments.append(f"Categoria inferida: {category}")

    # 2. Mover código interno ao início para o final
    title, internal_code = _move_code_to_end(title)
    if internal_code:
        adjustments.append(
            f"Código interno '{internal_code}' movido para o final do título"
        )

    # 3. Remover prefixos de código redundantes
    before = title
    title = AVOID_START.sub("", title).strip()
    if title != before:
        adjustments.append("Removido prefixo de código do início do título")

    # 4. Limpar espaços duplos e pontuação excessiva
    title = _remove_redundant_spaces(title)
    title = re.sub(r"\s+([,.:;])", r"\1", title)

    # 5. Title case com respeito a preposições portuguesas
    title = title_case_br(title)
    adjustments.append("Capitalização padronizada (title case BR)")

    # 6. Adicionar marca se ausente e fornecida
    if brand and brand.lower() not in title.lower():
        title = f"{title} {brand}"
        adjustments.append(f"Marca '{brand}' adicionada ao título")

    # 7. Recolocar código interno no final
    if internal_code:
        title = f"{title} ({internal_code})"

    # 8. Limitar tamanho por canal
    max_len = max_len or TITULO_MAX.get(channel, 200)
    if len(title) > max_len:
        title = title[: max_len - 3].rstrip() + "..."
        warnings.append(
            f"Título truncado para {max_len} chars (limite do canal '{channel}')"
        )

    structure = CATEGORY_STRUCTURES.get(category, "Tipo + Atributos + Marca + Código")

    return TitleResult(
        original=raw_title,
        category=category,
        structure_applied=structure,
        final_title=title,
        adjustments=adjustments,
        warnings=warnings,
        internal_code=internal_code,
    )


def batch_standardize(
    records: list[dict],
    title_col: str,
    category_col: str = "",
    brand_col: str = "",
    channel: str = "site",
) -> list[TitleResult]:
    results = []
    for rec in records:
        raw = safe_str(rec.get(title_col, ""))
        cat = safe_str(rec.get(category_col, "")) if category_col else ""
        brand = safe_str(rec.get(brand_col, "")) if brand_col else ""
        results.append(standardize_title(raw, cat, brand, channel))
    return results

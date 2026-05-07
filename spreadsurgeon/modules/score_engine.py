"""Motor de score de qualidade de cadastro (0-100)."""

from dataclasses import dataclass, field
from spreadsurgeon.config import SCORE_PESOS, Status
from spreadsurgeon.utils.text_utils import (safe_str, validate_ean,
                                             validate_ncm, price_to_float)


@dataclass
class ScoreDetail:
    criterion: str
    weight: int
    earned: int
    status: str
    note: str = ""


@dataclass
class ScoreResult:
    sku: str
    total: int = 0
    details: list[ScoreDetail] = field(default_factory=list)
    label: str = ""

    @property
    def grade(self) -> str:
        if self.total >= 90: return "A"
        if self.total >= 75: return "B"
        if self.total >= 60: return "C"
        if self.total >= 40: return "D"
        return "F"


def score_row(row: dict, col_map: dict) -> ScoreResult:
    """Pontua um registro. col_map = {campo_canonico: nome_coluna_real}."""

    def get(field: str) -> str:
        col = col_map.get(field)
        return safe_str(row.get(col or "", "")) if col else ""

    sku = get("sku") or get("codigo") or get("item_sku") or "?"
    details: list[ScoreDetail] = []
    total = 0

    pesos = SCORE_PESOS

    # 1. Título
    title = get("titulo") or get("descricao") or get("item_name") or get("nome")
    w = pesos["titulo"]
    if not title:
        details.append(ScoreDetail("Título", w, 0, "ERRO", "Título vazio"))
    elif len(title) < 10:
        earned = w // 3
        details.append(ScoreDetail("Título", w, earned, "FRACO", "Título muito curto"))
        total += earned
    elif len(title) < 30:
        earned = w * 2 // 3
        details.append(ScoreDetail("Título", w, earned, "REGULAR", "Título razoável"))
        total += earned
    else:
        details.append(ScoreDetail("Título", w, w, "OK", "Título adequado"))
        total += w

    # 2. Descrição
    desc = get("descricao_longa") or get("description") or get("descricao")
    w = pesos["descricao"]
    if not desc:
        details.append(ScoreDetail("Descrição", w, 0, "ERRO", "Sem descrição"))
    elif len(desc) < 50:
        earned = w // 3
        details.append(ScoreDetail("Descrição", w, earned, "FRACO", "Descrição muito curta"))
        total += earned
    elif len(desc) < 200:
        earned = w * 2 // 3
        details.append(ScoreDetail("Descrição", w, earned, "REGULAR", "Descrição curta"))
        total += earned
    else:
        details.append(ScoreDetail("Descrição", w, w, "OK", "Descrição adequada"))
        total += w

    # 3. Imagem
    img = get("imagem") or get("main_image_url") or get("imagem_principal")
    w = pesos["imagens"]
    if not img:
        details.append(ScoreDetail("Imagens", w, 0, "ERRO", "Sem imagem"))
    elif not img.startswith("http"):
        earned = w // 2
        details.append(ScoreDetail("Imagens", w, earned, "VERIFICAR", "URL de imagem suspeita"))
        total += earned
    else:
        details.append(ScoreDetail("Imagens", w, w, "OK", "Imagem presente"))
        total += w

    # 4. Preço
    price_str = get("preco_venda") or get("preco") or get("price") or get("standard_price")
    w = pesos["preco"]
    price = price_to_float(price_str) if price_str else None
    if price is None or price == 0:
        details.append(ScoreDetail("Preço", w, 0, "ERRO", "Preço zerado ou inválido"))
    else:
        details.append(ScoreDetail("Preço", w, w, "OK", f"Preço: {price_str}"))
        total += w

    # 5. Custo/Margem
    custo_str = get("custo") or get("cost")
    w = pesos["custo_margem"]
    if not custo_str:
        earned = w // 2
        details.append(ScoreDetail("Custo/Margem", w, earned, "PENDENTE", "Custo não informado"))
        total += earned
    elif price:
        custo = price_to_float(custo_str)
        if custo and custo >= price:
            details.append(ScoreDetail("Custo/Margem", w, 0, "ERRO",
                                       "Custo ≥ Preço — RISCO DE PREJUÍZO"))
        elif custo:
            margem = ((price - custo) / price) * 100
            if margem < 10:
                earned = w // 3
                details.append(ScoreDetail("Custo/Margem", w, earned, "ALERTA",
                                           f"Margem muito baixa: {margem:.1f}%"))
                total += earned
            else:
                details.append(ScoreDetail("Custo/Margem", w, w, "OK",
                                           f"Margem: {margem:.1f}%"))
                total += w
    else:
        details.append(ScoreDetail("Custo/Margem", w, w // 2, "PENDENTE",
                                   "Sem preço para calcular margem"))
        total += w // 2

    # 6. Estoque
    est_str = get("estoque") or get("stock") or get("quantity")
    w = pesos["estoque"]
    if not est_str:
        details.append(ScoreDetail("Estoque", w, 0, "ERRO", "Estoque não informado"))
    else:
        try:
            est = float(est_str.replace(",", "."))
            if est <= 0:
                details.append(ScoreDetail("Estoque", w, 0, "ERRO",
                                           "Estoque zero ou negativo"))
            else:
                details.append(ScoreDetail("Estoque", w, w, "OK",
                                           f"Estoque: {est_str}"))
                total += w
        except ValueError:
            details.append(ScoreDetail("Estoque", w, 0, "ERRO",
                                       f"Valor de estoque inválido: {est_str}"))

    # 7. EAN/NCM
    ean_str = get("ean") or get("gtin")
    ncm_str = get("ncm")
    w = pesos["ean_ncm"]
    ean_ok = validate_ean(ean_str)[0] if ean_str else False
    ncm_ok = validate_ncm(ncm_str)[0] if ncm_str else False
    if ean_ok and ncm_ok:
        details.append(ScoreDetail("EAN/NCM", w, w, "OK", "EAN e NCM válidos"))
        total += w
    elif ean_ok or ncm_ok:
        earned = w // 2
        details.append(ScoreDetail("EAN/NCM", w, earned, "PARCIAL",
                                   "Apenas um dos dois validado"))
        total += earned
    else:
        details.append(ScoreDetail("EAN/NCM", w, 0, "ERRO",
                                   "EAN e NCM ausentes ou inválidos"))

    # 8. Categoria
    cat = get("categoria") or get("category") or get("category_id")
    w = pesos["categoria"]
    if cat:
        details.append(ScoreDetail("Categoria", w, w, "OK", f"Categoria: {cat}"))
        total += w
    else:
        details.append(ScoreDetail("Categoria", w, 0, "PENDENTE", "Categoria não informada"))

    # 9. Marca
    brand = get("marca") or get("brand") or get("brand_name")
    w = pesos["marca"]
    if brand:
        details.append(ScoreDetail("Marca", w, w, "OK", f"Marca: {brand}"))
        total += w
    else:
        details.append(ScoreDetail("Marca", w, 0, "PENDENTE", "Marca não informada"))

    # 10. Ficha técnica
    # Heurística: conta campos técnicos preenchidos
    tech_fields = [k for k in row if any(t in k for t in
                   ("comprimento", "largura", "altura", "peso", "material",
                    "cor", "color", "dimension", "length", "width", "height",
                    "weight", "voltagem", "potencia", "potência"))]
    filled_tech = sum(1 for f in tech_fields if safe_str(row.get(f, "")))
    w = pesos["ficha_tecnica"]
    if filled_tech >= 3:
        details.append(ScoreDetail("Ficha Técnica", w, w, "OK",
                                   f"{filled_tech} atributos técnicos"))
        total += w
    elif filled_tech > 0:
        earned = w // 2
        details.append(ScoreDetail("Ficha Técnica", w, earned, "PARCIAL",
                                   f"Apenas {filled_tech} atributo(s) técnico(s)"))
        total += earned
    else:
        details.append(ScoreDetail("Ficha Técnica", w, 0, "PENDENTE",
                                   "Nenhum atributo técnico encontrado"))

    result = ScoreResult(sku=sku, total=min(total, 100), details=details)
    result.label = (
        "EXCELENTE" if result.total >= 90 else
        "BOM"       if result.total >= 75 else
        "REGULAR"   if result.total >= 60 else
        "FRACO"     if result.total >= 40 else
        "CRÍTICO"
    )
    return result


def score_rows(rows: list[dict], col_map: dict) -> list[ScoreResult]:
    return [score_row(row, col_map) for row in rows]


def aggregate_score(scores: list[ScoreResult]) -> dict:
    if not scores:
        return {}
    avg = sum(s.total for s in scores) / len(scores)
    dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for s in scores:
        dist[s.grade] += 1
    return {
        "media":        round(avg, 1),
        "total_skus":   len(scores),
        "distribuicao": dist,
        "criticos":     [s.sku for s in scores if s.grade == "F"],
        "excelentes":   [s.sku for s in scores if s.grade == "A"],
    }

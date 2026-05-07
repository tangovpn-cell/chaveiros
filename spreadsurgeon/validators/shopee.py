"""Validador para anúncios da Shopee."""

from spreadsurgeon.config import Status, CAMPOS_OBRIGATORIOS, TITULO_MAX
from spreadsurgeon.utils.text_utils import safe_str, price_to_float
from spreadsurgeon.validators.base import BaseValidator, ValidationResult

SHOPEE_COL_ALIASES = {
    "item_name":   ["item_name", "nome", "titulo", "título", "title", "product_name"],
    "price":       ["price", "preco", "preço", "valor"],
    "stock":       ["stock", "estoque", "qty", "quantidade"],
    "category":    ["category", "categoria"],
    "description": ["description", "descricao", "descrição"],
    "main_image":  ["main_image", "imagem", "image", "foto", "image_url"],
    "brand":       ["brand", "marca"],
    "sku":         ["sku", "seller_sku", "codigo", "código"],
}

# Classificação de título Shopee
def classify_shopee_title(title: str) -> str:
    """Retorna AJUSTAR | MANTER | VERIFICAR."""
    if not title:
        return "AJUSTAR"
    ln = len(title)
    if ln > TITULO_MAX["shopee"]:
        return "AJUSTAR"
    # Boas práticas básicas: tem pelo menos 2 palavras, sem caps excessivo
    words = title.split()
    if len(words) < 3:
        return "VERIFICAR"
    upper_ratio = sum(1 for w in words if w.isupper()) / len(words)
    if upper_ratio > 0.5:
        return "VERIFICAR"
    return "MANTER"


def _find_col(headers: list[str], canonical: str) -> str | None:
    aliases = SHOPEE_COL_ALIASES.get(canonical, [canonical])
    for h in headers:
        if h.lower().strip() in [a.lower() for a in aliases]:
            return h
    return None


class ShopeeValidator(BaseValidator):
    channel = "shopee"

    def validate(self, rows: list[dict]) -> ValidationResult:
        result = ValidationResult(channel="shopee", total_rows=len(rows))
        if not rows:
            result.pending_human.append("Nenhuma linha para validar")
            return result

        headers = list(rows[0].keys())
        cols = {c: _find_col(headers, c) for c in SHOPEE_COL_ALIASES}

        for i, row in enumerate(rows, 1):
            sku_col = cols.get("sku")
            sku = safe_str(row.get(sku_col or "", "")) or f"LINHA_{i}"

            # Título
            title_col = cols.get("item_name")
            title = safe_str(row.get(title_col or "", "")) if title_col else ""
            classification = classify_shopee_title(title)

            if not title:
                result.issues.append(self._issue(
                    i, sku, "item_name", Status.RISCO_PUBLICACAO, "",
                    "Título vazio", "Preencher nome do produto"
                ))
            elif len(title) > TITULO_MAX["shopee"]:
                result.issues.append(self._issue(
                    i, sku, "item_name", Status.ERRO, title,
                    f"Título com {len(title)} chars — máximo {TITULO_MAX['shopee']}",
                    "Reduzir título"
                ))
            elif classification == "VERIFICAR":
                result.issues.append(self._issue(
                    i, sku, "item_name", Status.VERIFICAR, title,
                    f"Título classificado como VERIFICAR: '{title}'",
                    "Estrutura preferencial: Tipo + Atributo + Aplicação/Modelo + Marca + Variação"
                ))
            # MANTER → sem issue

            # Preço
            price_col = cols.get("price")
            price_str = safe_str(row.get(price_col or "", "")) if price_col else ""
            price = price_to_float(price_str) if price_str else None
            if price is None or price == 0:
                result.issues.append(self._issue(
                    i, sku, "price", Status.RISCO_PUBLICACAO, price_str,
                    "Preço zerado ou inválido", "Preencher preço de venda"
                ))

            # Estoque
            stock_col = cols.get("stock")
            stock_str = safe_str(row.get(stock_col or "", "")) if stock_col else ""
            if stock_str:
                try:
                    st = int(float(stock_str))
                    if st <= 0:
                        result.issues.append(self._issue(
                            i, sku, "stock", Status.RISCO_PUBLICACAO, stock_str,
                            "Estoque zero — produto não aparece nos resultados",
                            "Atualizar estoque antes de ativar"
                        ))
                except ValueError:
                    pass
            else:
                result.issues.append(self._issue(
                    i, sku, "stock", Status.PENDENTE, "",
                    "Estoque não informado", "Preencher quantidade"
                ))

            # Categoria
            cat_col = cols.get("category")
            cat = safe_str(row.get(cat_col or "", "")) if cat_col else ""
            if not cat:
                result.issues.append(self._issue(
                    i, sku, "category", Status.PENDENTE, "",
                    "Categoria vazia", "Informar categoria Shopee"
                ))

            # Descrição
            desc_col = cols.get("description")
            desc = safe_str(row.get(desc_col or "", "")) if desc_col else ""
            if not desc:
                result.issues.append(self._issue(
                    i, sku, "description", Status.PENDENTE, "",
                    "Descrição vazia",
                    "Preencher descrição técnica do produto"
                ))

            # Imagem
            img_col = cols.get("main_image")
            img = safe_str(row.get(img_col or "", "")) if img_col else ""
            if not img:
                result.issues.append(self._issue(
                    i, sku, "main_image", Status.RISCO_PUBLICACAO, "",
                    "Imagem principal ausente", "Adicionar imagem principal"
                ))

        rows_with_errors = {iss.row for iss in result.issues
                            if iss.status == Status.ERRO}
        result.valid_rows = result.total_rows - len(rows_with_errors)

        result.corrections = [
            "Título Shopee: máximo 120 caracteres",
            "Estrutura preferencial: Tipo + Atributo + Aplicação/Modelo + Marca + Variação",
            "Títulos classificados: AJUSTAR (corrigir) | MANTER (ok) | VERIFICAR (revisar)",
        ]
        result.next_steps = [
            "Corrigir títulos classificados como AJUSTAR",
            "Revisar títulos VERIFICAR com equipe comercial",
            "Preencher categorias antes de ativar",
        ]
        return result

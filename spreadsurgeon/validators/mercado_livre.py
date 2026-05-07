"""Validador para anúncios do Mercado Livre."""

import re
from spreadsurgeon.config import Status, CAMPOS_OBRIGATORIOS, TITULO_MAX
from spreadsurgeon.utils.text_utils import (safe_str, validate_ean,
                                             price_to_float)
from spreadsurgeon.validators.base import BaseValidator, ValidationResult

AUTOMOTIVO_BRANDS_RISK = [
    "volkswagen", "vw", "ford", "chevrolet", "gm", "fiat", "toyota",
    "honda", "hyundai", "renault", "peugeot", "citroën", "citroen",
    "nissan", "mitsubishi", "mercedes", "bmw", "audi",
]

ML_COL_ALIASES = {
    "title":             ["title", "titulo", "título", "nome", "item_name"],
    "price":             ["price", "preco", "preço", "valor", "standard_price"],
    "available_quantity":["available_quantity", "estoque", "stock", "qty",
                         "quantidade"],
    "category_id":       ["category_id", "categoria", "category"],
    "condition":         ["condition", "condicao", "condição"],
    "listing_type_id":   ["listing_type_id", "tipo_anuncio", "listing_type"],
    "gtin":              ["gtin", "ean", "barcode"],
    "brand":             ["brand", "marca"],
    "pictures":          ["pictures", "imagens", "fotos", "images"],
    "warranty":          ["warranty", "garantia"],
    "description":       ["description", "descricao", "descrição"],
}


def _find_col(headers: list[str], canonical: str) -> str | None:
    aliases = ML_COL_ALIASES.get(canonical, [canonical])
    for h in headers:
        if h.lower().strip() in [a.lower() for a in aliases]:
            return h
    return None


class MercadoLivreValidator(BaseValidator):
    channel = "mercado_livre"

    def validate(self, rows: list[dict]) -> ValidationResult:
        result = ValidationResult(channel="mercado_livre", total_rows=len(rows))
        if not rows:
            result.pending_human.append("Nenhuma linha para validar")
            return result

        headers = list(rows[0].keys())
        cols = {c: _find_col(headers, c) for c in ML_COL_ALIASES}

        for i, row in enumerate(rows, 1):
            title_col = cols.get("title")
            title = safe_str(row.get(title_col or "", "")) if title_col else ""
            sku = title[:30] if title else f"LINHA_{i}"

            # Título: máx 60 chars
            if not title:
                result.issues.append(self._issue(
                    i, sku, "title", Status.RISCO_PUBLICACAO, "",
                    "Título vazio", "Preencher título"
                ))
            else:
                if len(title) > TITULO_MAX["mercado_livre"]:
                    result.issues.append(self._issue(
                        i, sku, "title", Status.ERRO, title,
                        f"Título com {len(title)} chars — máximo {TITULO_MAX['mercado_livre']}",
                        f"Reduzir para até {TITULO_MAX['mercado_livre']} caracteres"
                    ))
                # Risco de marca registrada automotiva
                title_lower = title.lower()
                for brand in AUTOMOTIVO_BRANDS_RISK:
                    if brand in title_lower:
                        result.issues.append(self._issue(
                            i, sku, "title", Status.VERIFICAR, title,
                            f"Marca de montadora '{brand}' no título — risco de bloqueio no ML",
                            "Verificar política de marcas do ML para categoria automotiva. "
                            "Considerar usar apenas código de compatibilidade"
                        ))
                        break

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
            qty_col = cols.get("available_quantity")
            qty_str = safe_str(row.get(qty_col or "", "")) if qty_col else ""
            if qty_str:
                try:
                    qty = int(float(qty_str))
                    if qty <= 0:
                        result.issues.append(self._issue(
                            i, sku, "available_quantity", Status.RISCO_PUBLICACAO, qty_str,
                            "Estoque zero ou negativo — anúncio pausado automaticamente",
                            "Corrigir estoque antes de ativar anúncio"
                        ))
                except ValueError:
                    pass
            else:
                result.issues.append(self._issue(
                    i, sku, "available_quantity", Status.PENDENTE, "",
                    "Estoque não informado", "Preencher quantidade disponível"
                ))

            # Categoria
            cat_col = cols.get("category_id")
            cat = safe_str(row.get(cat_col or "", "")) if cat_col else ""
            if not cat:
                result.issues.append(self._issue(
                    i, sku, "category_id", Status.PENDENTE, "",
                    "Categoria não informada",
                    "Informar category_id do ML (ex: MLB1234)"
                ))

            # Condição
            cond_col = cols.get("condition")
            cond = safe_str(row.get(cond_col or "", "")).lower() if cond_col else ""
            if cond and cond not in ("new", "novo", "used", "usado",
                                    "refurbished", "recondicionado"):
                result.issues.append(self._issue(
                    i, sku, "condition", Status.VERIFICAR, cond,
                    f"Condição '{cond}' não reconhecida",
                    "Usar: new | used | refurbished"
                ))

            # EAN/GTIN
            gtin_col = cols.get("gtin")
            gtin = safe_str(row.get(gtin_col or "", "")) if gtin_col else ""
            if gtin:
                ok, msg = validate_ean(gtin)
                if not ok:
                    result.issues.append(self._issue(
                        i, sku, "gtin", Status.VERIFICAR, gtin, msg,
                        "Confirmar GTIN com o fabricante"
                    ))

            # Imagens
            img_col = cols.get("pictures")
            img = safe_str(row.get(img_col or "", "")) if img_col else ""
            if not img:
                result.issues.append(self._issue(
                    i, sku, "pictures", Status.RISCO_PUBLICACAO, "",
                    "Sem imagem — obrigatório no ML",
                    "Adicionar ao menos 1 imagem (mínimo 500x500px)"
                ))

        rows_with_errors = {iss.row for iss in result.issues
                            if iss.status == Status.ERRO}
        result.valid_rows = result.total_rows - len(rows_with_errors)

        result.corrections = [
            "Título limitado a 60 caracteres no Mercado Livre",
            "Evitar marcas de montadora em títulos automotivos",
            "condition deve ser: new, used ou refurbished",
        ]
        result.next_steps = [
            "Verificar títulos com mais de 60 chars e truncar",
            "Confirmar category_id com a API do ML ou painel",
            "Validar garantia se produto exige declaração",
        ]
        return result

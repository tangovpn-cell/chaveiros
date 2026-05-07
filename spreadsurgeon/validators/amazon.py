"""Validador de templates Amazon (XLSM)."""

import re
from spreadsurgeon.config import (Status, CAMPOS_OBRIGATORIOS,
                                  AMAZON_DATA_START, TITULO_MAX)
from spreadsurgeon.utils.text_utils import (safe_str, validate_ean,
                                             price_to_float)
from spreadsurgeon.validators.base import BaseValidator, ValidationResult

# Pares de dimensão que exigem unidade correspondente
DIMENSION_PAIRS = [
    ("item_length",        "item_length_unit_of_measure"),
    ("item_width",         "item_width_unit_of_measure"),
    ("item_height",        "item_height_unit_of_measure"),
    ("item_weight",        "item_weight_unit_of_measure"),
    ("package_length",     "package_length_unit_of_measure"),
    ("package_width",      "package_width_unit_of_measure"),
    ("package_height",     "package_height_unit_of_measure"),
    ("package_weight",     "package_weight_unit_of_measure"),
]

AMAZON_COL_ALIASES = {
    "item_sku":          ["item_sku", "seller_sku", "sku"],
    "item_name":         ["item_name", "title", "titulo", "nome"],
    "brand_name":        ["brand_name", "brand", "marca"],
    "standard_price":    ["standard_price", "price", "preco", "preço"],
    "quantity":          ["quantity", "stock", "estoque"],
    "main_image_url":    ["main_image_url", "imagem", "image_url"],
    "bullet_point1":     ["bullet_point1"],
    "description":       ["description", "descricao", "descrição"],
    "external_product_id": ["external_product_id", "ean", "gtin", "upc"],
    "external_product_id_type": ["external_product_id_type"],
}


def _find_col(headers: list[str], canonical: str) -> str | None:
    aliases = AMAZON_COL_ALIASES.get(canonical, [canonical])
    for h in headers:
        if h.lower().strip() in [a.lower() for a in aliases]:
            return h
    return None


class AmazonValidator(BaseValidator):
    channel = "amazon"

    def validate(self, rows: list[dict]) -> ValidationResult:
        result = ValidationResult(channel="amazon", total_rows=len(rows))
        if not rows:
            result.pending_human.append("Nenhuma linha de dados encontrada")
            return result

        headers = list(rows[0].keys())
        cols = {canon: _find_col(headers, canon) for canon in AMAZON_COL_ALIASES}

        missing = [c for c in CAMPOS_OBRIGATORIOS["amazon"]
                   if not _find_col(headers, c)]
        if missing:
            result.pending_human.append(
                f"Campos obrigatórios ausentes: {', '.join(missing)}"
            )

        for i, row in enumerate(rows, 1):
            sku_col = cols.get("item_sku")
            sku = safe_str(row.get(sku_col or "", "")) or f"LINHA_{i}"

            # Título
            title_col = cols.get("item_name")
            title = safe_str(row.get(title_col or "", "")) if title_col else ""
            if not title:
                result.issues.append(self._issue(
                    i, sku, "item_name", Status.RISCO_PUBLICACAO, "",
                    "Título vazio", "Preencher item_name"
                ))
            elif len(title) > TITULO_MAX["amazon"]:
                result.issues.append(self._issue(
                    i, sku, "item_name", Status.VERIFICAR, title,
                    f"Título com {len(title)} chars (máx {TITULO_MAX['amazon']})",
                    "Reduzir título"
                ))

            # Preço
            price_col = cols.get("standard_price")
            price_str = safe_str(row.get(price_col or "", "")) if price_col else ""
            price = price_to_float(price_str) if price_str else None
            if price is None or price == 0:
                result.issues.append(self._issue(
                    i, sku, "standard_price", Status.RISCO_PUBLICACAO, price_str,
                    "Preço zerado ou inválido", "Preencher standard_price"
                ))

            # EAN/GTIN
            ean_col = cols.get("external_product_id")
            ean_str = safe_str(row.get(ean_col or "", "")) if ean_col else ""
            ean_type_col = cols.get("external_product_id_type")
            ean_type = safe_str(row.get(ean_type_col or "", "")) if ean_type_col else ""
            if ean_str:
                ok, msg = validate_ean(ean_str)
                if not ok:
                    result.issues.append(self._issue(
                        i, sku, "external_product_id", Status.VERIFICAR, ean_str,
                        msg, "Confirmar GTIN/EAN correto"
                    ))
                if ean_str and not ean_type:
                    result.issues.append(self._issue(
                        i, sku, "external_product_id_type", Status.PENDENTE, "",
                        "Tipo de ID externo não informado",
                        "Preencher: EAN, GTIN, UPC ou ISBN"
                    ))

            # Imagem
            img_col = cols.get("main_image_url")
            img = safe_str(row.get(img_col or "", "")) if img_col else ""
            if not img:
                result.issues.append(self._issue(
                    i, sku, "main_image_url", Status.RISCO_PUBLICACAO, "",
                    "Imagem principal ausente", "Adicionar URL de imagem HTTPS"
                ))

            # Pares de dimensão
            for dim_field, unit_field in DIMENSION_PAIRS:
                dim_col  = _find_col(headers, dim_field)
                unit_col = _find_col(headers, unit_field)
                dim_val  = safe_str(row.get(dim_col or "", "")) if dim_col else ""
                unit_val = safe_str(row.get(unit_col or "", "")) if unit_col else ""
                if dim_val and not unit_val:
                    result.issues.append(self._issue(
                        i, sku, dim_field, Status.VERIFICAR, dim_val,
                        f"Dimensão '{dim_field}' preenchida sem unidade correspondente",
                        f"Preencher '{unit_field}' — NÃO copiar medida silenciosamente. "
                        f"Marcar como VERIFICAR MEDIDA REAL se for hipótese"
                    ))

            # Bullet points
            for bp in ["bullet_point1", "bullet_point2"]:
                bp_col = _find_col(headers, bp)
                bp_val = safe_str(row.get(bp_col or "", "")) if bp_col else ""
                if not bp_val:
                    result.issues.append(self._issue(
                        i, sku, bp, Status.PENDENTE, "",
                        f"{bp} vazio", f"Preencher {bp} com benefício real do produto"
                    ))

        rows_with_errors = {iss.row for iss in result.issues
                            if iss.status == Status.ERRO}
        result.valid_rows = result.total_rows - len(rows_with_errors)

        result.corrections = [
            "Preservar estrutura XLSM com abas auxiliares e validações da Amazon",
            "Nunca copiar medidas por inferência — marcar VERIFICAR MEDIDA REAL se necessário",
            "Dados começam na linha 7 (índice 6); linhas 4-6 são rótulos/técnico/exemplo",
            "EAN deve ser sempre tratado como texto para evitar notação científica",
        ]
        result.next_steps = [
            "Corrigir RISCO DE PUBLICAÇÃO antes de enviar template",
            "Verificar todos os pares dimensão/unidade",
            "Confirmar bullet points com informação real do produto",
            "Validar imagens em resolução mínima Amazon (500x500px, fundo branco)",
        ]
        return result

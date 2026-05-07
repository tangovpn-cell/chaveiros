"""Validador de planilhas para importação no Bling."""

import re
from spreadsurgeon.config import (Status, CAMPOS_OBRIGATORIOS,
                                  BLING_ENCODING, BLING_SEPARATOR,
                                  BLING_DECIMAL)
from spreadsurgeon.utils.text_utils import (validate_ean, validate_ncm,
                                             safe_str, price_to_float,
                                             is_scientific_notation)
from spreadsurgeon.validators.base import BaseValidator, ValidationResult

# Mapeamento de variações de nome de coluna → campo canônico
BLING_COL_MAP = {
    "codigo": ["codigo", "código", "sku", "cod"],
    "descricao": ["descricao", "descrição", "nome", "produto", "name"],
    "preco_venda": ["preco_venda", "preço_venda", "preco", "preço", "price",
                    "valor_venda", "valor"],
    "custo": ["custo", "preco_custo", "preço_custo", "cost"],
    "unidade": ["unidade", "un", "unit", "medida"],
    "ean": ["ean", "gtin", "codigo_barras", "código_de_barras", "barcode"],
    "ncm": ["ncm"],
    "cest": ["cest"],
    "estoque": ["estoque", "quantidade", "qty", "stock", "saldo"],
    "imagem": ["imagem", "imagens", "image", "foto", "fotos", "url_imagem",
               "url_foto"],
    "categoria": ["categoria", "category", "departamento"],
    "marca": ["marca", "brand"],
}


def _find_col(headers: list[str], canonical: str) -> str | None:
    aliases = BLING_COL_MAP.get(canonical, [canonical])
    for h in headers:
        if h.lower().strip() in [a.lower() for a in aliases]:
            return h
    return None


def _resolve_cols(headers: list[str]) -> dict[str, str | None]:
    return {canon: _find_col(headers, canon) for canon in BLING_COL_MAP}


class BlingValidator(BaseValidator):
    channel = "bling"

    def validate(self, rows: list[dict]) -> ValidationResult:
        result = ValidationResult(channel="bling", total_rows=len(rows))
        if not rows:
            result.pending_human.append("Nenhuma linha para validar")
            return result

        headers = list(rows[0].keys())
        cols = _resolve_cols(headers)

        # Campos obrigatórios ausentes
        missing_required = []
        for req in CAMPOS_OBRIGATORIOS["bling"]:
            if cols.get(req) is None:
                missing_required.append(req)

        if missing_required:
            result.pending_human.append(
                f"Colunas obrigatórias não encontradas: {', '.join(missing_required)}"
            )

        skus_seen = {}

        for i, row in enumerate(rows, 1):
            sku = safe_str(row.get(cols.get("codigo") or "", "")) or f"LINHA_{i}"

            # SKU duplicado
            if sku in skus_seen:
                result.issues.append(self._issue(
                    i, sku, "codigo", Status.ERRO, sku,
                    f"SKU duplicado — já apareceu na linha {skus_seen[sku]}",
                    "Verificar e corrigir SKU duplicado antes da importação"
                ))
            else:
                skus_seen[sku] = i

            # Descrição vazia
            desc_col = cols.get("descricao")
            desc = safe_str(row.get(desc_col or "", "")) if desc_col else ""
            if not desc:
                result.issues.append(self._issue(
                    i, sku, "descricao", Status.ERRO, "",
                    "Descrição vazia", "Preencher nome do produto"
                ))

            # Preço zerado ou inválido
            preco_col = cols.get("preco_venda")
            preco_str = safe_str(row.get(preco_col or "", "")) if preco_col else ""
            preco = price_to_float(preco_str) if preco_str else None
            if preco is None or preco == 0:
                result.issues.append(self._issue(
                    i, sku, "preco_venda", Status.RISCO_PUBLICACAO, preco_str,
                    "Preço zerado ou inválido",
                    "Preencher preço de venda antes da importação"
                ))

            # Custo > Preço
            custo_col = cols.get("custo")
            custo_str = safe_str(row.get(custo_col or "", "")) if custo_col else ""
            custo = price_to_float(custo_str) if custo_str else None
            if custo and preco and custo > preco:
                result.issues.append(self._issue(
                    i, sku, "custo", Status.RISCO_PREJUIZO, custo_str,
                    f"Custo ({custo_str}) maior que preço ({preco_str})",
                    "Revisar custo e preço de venda para evitar prejuízo"
                ))

            # EAN
            ean_col = cols.get("ean")
            ean_str = safe_str(row.get(ean_col or "", "")) if ean_col else ""
            if ean_str:
                if is_scientific_notation(ean_str):
                    result.issues.append(self._issue(
                        i, sku, "ean", Status.ERRO, ean_str,
                        "EAN em notação científica — Excel converteu o número",
                        "Formatar célula como Texto antes de inserir o EAN"
                    ))
                else:
                    ok, msg = validate_ean(ean_str)
                    if not ok:
                        result.issues.append(self._issue(
                            i, sku, "ean", Status.VERIFICAR, ean_str, msg,
                            "Confirmar EAN correto no produto físico ou nota fiscal"
                        ))

            # NCM
            ncm_col = cols.get("ncm")
            ncm_str = safe_str(row.get(ncm_col or "", "")) if ncm_col else ""
            if ncm_str:
                ok, msg = validate_ncm(ncm_str)
                if not ok:
                    result.issues.append(self._issue(
                        i, sku, "ncm", Status.BLOQUEIO_FISCAL, ncm_str, msg,
                        "Corrigir NCM com contador ou tabela TIPI"
                    ))

            # Unidade
            un_col = cols.get("unidade")
            un_str = safe_str(row.get(un_col or "", "")) if un_col else ""
            if not un_str:
                result.issues.append(self._issue(
                    i, sku, "unidade", Status.PENDENTE, "",
                    "Unidade vazia", "Preencher: UN, PC, CX, KG, etc."
                ))

            # Estoque negativo
            est_col = cols.get("estoque")
            est_str = safe_str(row.get(est_col or "", "")) if est_col else ""
            if est_str:
                try:
                    est_val = float(est_str.replace(",", "."))
                    if est_val < 0:
                        result.issues.append(self._issue(
                            i, sku, "estoque", Status.RISCO_PUBLICACAO, est_str,
                            "Estoque negativo",
                            "Corrigir saldo antes de anunciar"
                        ))
                except ValueError:
                    pass

            # Imagem
            img_col = cols.get("imagem")
            img_str = safe_str(row.get(img_col or "", "")) if img_col else ""
            if not img_str:
                result.issues.append(self._issue(
                    i, sku, "imagem", Status.PENDENTE, "",
                    "Sem imagem cadastrada",
                    "Adicionar URL de imagem (múltiplas separadas por pipe |)"
                ))
            else:
                urls = [u.strip() for u in img_str.split("|")]
                for url in urls:
                    if url and not url.startswith("http"):
                        result.issues.append(self._issue(
                            i, sku, "imagem", Status.VERIFICAR, url,
                            f"URL de imagem inválida: '{url}'",
                            "URLs devem começar com http:// ou https://"
                        ))

        # Contagem de válidas
        rows_with_errors = {iss.row for iss in result.issues
                            if iss.status == Status.ERRO}
        result.valid_rows = result.total_rows - len(rows_with_errors)

        result.corrections = [
            "EANs em notação científica foram identificados — formatar coluna como Texto",
            "Preços devem usar vírgula como separador decimal (ex: 29,90)",
            "Imagens múltiplas separadas por pipe (|)",
            "Separator do CSV deve ser ponto e vírgula (;)",
            f"Encoding recomendado para Bling: {BLING_ENCODING}",
        ]
        result.next_steps = [
            "Corrigir todos os erros marcados como ERRO antes da importação",
            "Validar itens marcados como BLOQUEIO FISCAL com contador",
            "Verificar imagens em navegador antes de importar",
            "Exportar CSV final com encoding latin-1 e separador ;",
        ]
        return result

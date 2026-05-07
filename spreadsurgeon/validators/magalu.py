"""Validador para catálogo do Magazine Luiza."""

from spreadsurgeon.config import Status, CAMPOS_OBRIGATORIOS, TITULO_MAX
from spreadsurgeon.utils.text_utils import (safe_str, validate_ean,
                                             validate_ncm, price_to_float)
from spreadsurgeon.validators.base import BaseValidator, ValidationResult

MAGALU_COL_ALIASES = {
    "nome":         ["nome", "title", "titulo", "título", "item_name",
                     "product_name", "descricao", "descrição"],
    "ean":          ["ean", "gtin", "barcode", "codigo_barras"],
    "marca":        ["marca", "brand"],
    "descricao":    ["descricao", "descrição", "description", "long_description"],
    "preco":        ["preco", "preço", "price", "valor", "standard_price"],
    "estoque":      ["estoque", "stock", "qty", "quantidade"],
    "ncm":          ["ncm"],
    "cest":         ["cest"],
    "imagem_principal": ["imagem_principal", "main_image", "image_url", "foto"],
    "categoria":    ["categoria", "category"],
    "garantia":     ["garantia", "warranty"],
}


def _find_col(headers: list[str], canonical: str) -> str | None:
    aliases = MAGALU_COL_ALIASES.get(canonical, [canonical])
    for h in headers:
        if h.lower().strip() in [a.lower() for a in aliases]:
            return h
    return None


class MagaluValidator(BaseValidator):
    channel = "magalu"

    def validate(self, rows: list[dict]) -> ValidationResult:
        result = ValidationResult(channel="magalu", total_rows=len(rows))
        if not rows:
            result.pending_human.append("Nenhuma linha para validar")
            return result

        headers = list(rows[0].keys())
        cols = {c: _find_col(headers, c) for c in MAGALU_COL_ALIASES}

        for i, row in enumerate(rows, 1):
            sku = f"LINHA_{i}"

            # Nome
            nome_col = cols.get("nome")
            nome = safe_str(row.get(nome_col or "", "")) if nome_col else ""
            if not nome:
                result.issues.append(self._issue(
                    i, sku, "nome", Status.RISCO_PUBLICACAO, "",
                    "Nome do produto vazio", "Preencher nome"
                ))

            # EAN — obrigatório no Magalu
            ean_col = cols.get("ean")
            ean_str = safe_str(row.get(ean_col or "", "")) if ean_col else ""
            if not ean_str:
                result.issues.append(self._issue(
                    i, sku, "ean", Status.RISCO_PUBLICACAO, "",
                    "EAN obrigatório para Magalu", "Informar EAN/GTIN do produto"
                ))
            else:
                ok, msg = validate_ean(ean_str)
                if not ok:
                    result.issues.append(self._issue(
                        i, sku, "ean", Status.VERIFICAR, ean_str, msg,
                        "Confirmar EAN correto com o fabricante"
                    ))

            # Marca
            marca_col = cols.get("marca")
            marca = safe_str(row.get(marca_col or "", "")) if marca_col else ""
            if not marca:
                result.issues.append(self._issue(
                    i, sku, "marca", Status.PENDENTE, "",
                    "Marca não informada", "Preencher marca do produto"
                ))

            # Descrição
            desc_col = cols.get("descricao")
            desc = safe_str(row.get(desc_col or "", "")) if desc_col else ""
            if not desc:
                result.issues.append(self._issue(
                    i, sku, "descricao", Status.PENDENTE, "",
                    "Descrição vazia", "Preencher descrição técnica"
                ))

            # Preço
            preco_col = cols.get("preco")
            preco_str = safe_str(row.get(preco_col or "", "")) if preco_col else ""
            preco = price_to_float(preco_str) if preco_str else None
            if preco is None or preco == 0:
                result.issues.append(self._issue(
                    i, sku, "preco", Status.RISCO_PUBLICACAO, preco_str,
                    "Preço zerado ou inválido", "Preencher preço de venda"
                ))

            # Estoque
            est_col = cols.get("estoque")
            est_str = safe_str(row.get(est_col or "", "")) if est_col else ""
            if est_str:
                try:
                    if int(float(est_str)) <= 0:
                        result.issues.append(self._issue(
                            i, sku, "estoque", Status.RISCO_PUBLICACAO, est_str,
                            "Estoque zero ou negativo",
                            "Atualizar estoque antes de enviar"
                        ))
                except ValueError:
                    pass

            # NCM — fiscal bloqueante
            ncm_col = cols.get("ncm")
            ncm_str = safe_str(row.get(ncm_col or "", "")) if ncm_col else ""
            if not ncm_str:
                result.issues.append(self._issue(
                    i, sku, "ncm", Status.BLOQUEIO_FISCAL, "",
                    "NCM ausente — dado fiscal obrigatório no Magalu",
                    "Consultar tabela TIPI ou contador para NCM correto. "
                    "NÃO inferir NCM — risco tributário."
                ))
            else:
                ok, msg = validate_ncm(ncm_str)
                if not ok:
                    result.issues.append(self._issue(
                        i, sku, "ncm", Status.BLOQUEIO_FISCAL, ncm_str, msg,
                        "Corrigir NCM com contador ou tabela TIPI"
                    ))

            # Imagem
            img_col = cols.get("imagem_principal")
            img = safe_str(row.get(img_col or "", "")) if img_col else ""
            if not img:
                result.issues.append(self._issue(
                    i, sku, "imagem_principal", Status.RISCO_PUBLICACAO, "",
                    "Imagem principal ausente", "Adicionar imagem"
                ))

        rows_with_errors = {iss.row for iss in result.issues
                            if iss.status in (Status.ERRO, Status.BLOQUEIO_FISCAL)}
        result.valid_rows = result.total_rows - len(rows_with_errors)

        result.corrections = [
            "EAN é obrigatório no Magalu — sem EAN, produto é rejeitado",
            "NCM faltante gera BLOQUEIO FISCAL — nunca inferir dado fiscal",
            "Magalu exige ficha técnica detalhada para aprovação",
        ]
        result.next_steps = [
            "Resolver todos os BLOQUEIO FISCAL antes de enviar",
            "Confirmar EAN com nota fiscal ou embalagem do produto",
            "Validar imagens: mínimo 500x500px, fundo branco preferencial",
        ]
        return result

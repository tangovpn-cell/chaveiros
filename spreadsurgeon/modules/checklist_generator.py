"""Gerador de checklist pré-envio por canal."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import CANAIS


@dataclass
class ChecklistItem:
    item: str
    status: str     # OK | PENDENTE | FALHOU
    critical: bool = False
    note: str = ""


@dataclass
class Checklist:
    channel: str
    product_name: str
    sku: str
    items: list[ChecklistItem] = field(default_factory=list)
    score: int = 0          # % de itens OK
    ready_to_send: bool = False
    blockers: list[str] = field(default_factory=list)

    def compute(self):
        total   = len(self.items)
        ok      = sum(1 for i in self.items if i.status == "OK")
        self.score = int(ok / total * 100) if total else 0

        critical_fails = [i for i in self.items
                          if i.critical and i.status != "OK"]
        self.blockers  = [i.item for i in critical_fails]
        self.ready_to_send = len(critical_fails) == 0


_BASE_ITEMS = [
    ("SKU / Código definido e único",              True),
    ("Nome/Título preenchido",                     True),
    ("Descrição técnica preenchida",               False),
    ("Preço de venda definido e positivo",         True),
    ("Custo preenchido e margem positiva",         True),
    ("Estoque positivo",                           True),
    ("Imagem principal presente e válida",         True),
    ("EAN/GTIN válido ou ausência justificada",    False),
    ("NCM válido (8 dígitos)",                     True),
    ("Marca preenchida",                           False),
    ("Categoria definida",                         False),
    ("Sem SKU duplicado na planilha",              True),
    ("Ficha técnica com pelo menos 3 atributos",   False),
    ("Sem notação científica em nenhum campo",     True),
    ("Encoding e separador corretos para o canal", True),
]

_CHANNEL_EXTRAS: dict[str, list[tuple[str, bool]]] = {
    "bling": [
        ("CSV com separador ponto e vírgula (;)",   True),
        ("Encoding latin-1 ou UTF-8 confirmado",    True),
        ("Decimal com vírgula (ex: 29,90)",         True),
        ("Imagens separadas por pipe (|)",          False),
        ("Unidade de medida preenchida (UN, PC…)",  True),
    ],
    "amazon": [
        ("XLSM preservado com abas auxiliares",     True),
        ("Dados a partir da linha 7",               True),
        ("Pares dimensão + unidade preenchidos",    True),
        ("Bullet points preenchidos (mín 2)",       True),
        ("Imagem HTTPS, fundo branco, 500x500px+",  True),
        ("external_product_id_type preenchido",     False),
    ],
    "mercado_livre": [
        ("Título ≤ 60 caracteres",                  True),
        ("category_id do ML informado",             True),
        ("condition: new | used | refurbished",     True),
        ("Sem marca de montadora em título autom.", False),
        ("Imagem mínima 500x500px",                 True),
        ("listing_type_id definido",                False),
    ],
    "shopee": [
        ("Título ≤ 120 caracteres",                 True),
        ("Estrutura: Tipo+Atributo+Aplicação+Marca",False),
        ("Categoria Shopee definida",               True),
        ("Imagem mín 500x500px",                    True),
    ],
    "magalu": [
        ("EAN obrigatório e válido",                True),
        ("NCM obrigatório e válido",                True),
        ("Descrição longa preenchida",              True),
        ("Ficha técnica completa",                  True),
        ("Garantia informada",                      False),
        ("Imagem fundo branco, 1000x1000px+",       True),
    ],
}


def generate_checklist(
    channel: str,
    product_data: dict,
    col_map: dict = None,
) -> Checklist:
    """
    product_data: dict com campos do produto (pode ser uma linha da planilha)
    col_map: {campo_canonico: nome_real_na_planilha}
    """
    col_map = col_map or {}

    def get(field_name: str) -> str:
        col = col_map.get(field_name, field_name)
        return str(product_data.get(col, "")).strip()

    sku  = get("sku") or get("codigo") or get("item_sku") or "?"
    name = get("nome") or get("descricao") or get("item_name") or get("titulo") or "?"

    checklist = Checklist(channel=channel, product_name=name, sku=sku)

    def _check(label: str, critical: bool, ok: bool, note: str = "") -> ChecklistItem:
        return ChecklistItem(
            item=label,
            status="OK" if ok else "PENDENTE",
            critical=critical,
            note=note,
        )

    # Itens base com avaliação real
    from spreadsurgeon.utils.text_utils import (validate_ean, validate_ncm,
                                                price_to_float,
                                                is_scientific_notation)

    ean_str   = get("ean") or get("gtin") or get("external_product_id")
    ncm_str   = get("ncm")
    price_str = get("preco_venda") or get("preco") or get("price") or get("standard_price")
    cost_str  = get("custo") or get("cost")
    stock_str = get("estoque") or get("stock") or get("quantity")
    img_str   = get("imagem") or get("main_image_url") or get("imagem_principal")
    brand_str = get("marca") or get("brand")
    cat_str   = get("categoria") or get("category") or get("category_id")

    price = price_to_float(price_str) if price_str else None
    cost  = price_to_float(cost_str)  if cost_str  else None

    try:
        stock = float(stock_str.replace(",", ".")) if stock_str else None
    except ValueError:
        stock = None

    ean_ok, _ = validate_ean(ean_str) if ean_str else (False, "")
    ncm_ok, _ = validate_ncm(ncm_str) if ncm_str else (False, "")

    margin_ok = (cost is not None and price is not None and
                 price > 0 and cost < price)

    # Check all values for scientific notation
    sci_found = any(
        is_scientific_notation(str(v))
        for v in product_data.values()
        if v
    )

    checklist.items = [
        _check("SKU / Código definido e único",             True,  bool(sku and sku != "?")),
        _check("Nome/Título preenchido",                    True,  bool(name and name != "?")),
        _check("Descrição técnica preenchida",              False, bool(get("descricao") or get("description"))),
        _check("Preço de venda definido e positivo",        True,  price is not None and price > 0),
        _check("Custo preenchido e margem positiva",        True,  margin_ok,
               note="" if margin_ok else "Custo ou preço ausente — margem não calculável"),
        _check("Estoque positivo",                          True,  stock is not None and stock > 0),
        _check("Imagem principal presente e válida",        True,  bool(img_str) and img_str.startswith("http")),
        _check("EAN/GTIN válido ou ausência justificada",   False, ean_ok,
               note="" if ean_ok else "EAN ausente ou inválido"),
        _check("NCM válido (8 dígitos)",                    True,  ncm_ok,
               note="" if ncm_ok else "NCM ausente ou inválido — BLOQUEIO FISCAL"),
        _check("Marca preenchida",                          False, bool(brand_str)),
        _check("Categoria definida",                        False, bool(cat_str)),
        _check("Sem notação científica em nenhum campo",    True,  not sci_found,
               note="Notação científica detectada — formatar como Texto" if sci_found else ""),
    ]

    # Itens específicos do canal
    channel_items = _CHANNEL_EXTRAS.get(channel, [])
    for label, critical in channel_items:
        # Para itens específicos não avaliamos automaticamente — marcamos como PENDENTE para revisão
        checklist.items.append(ChecklistItem(
            item=label,
            status="PENDENTE",
            critical=critical,
            note="Verificar manualmente antes do envio",
        ))

    checklist.compute()
    return checklist

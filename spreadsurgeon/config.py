"""Constantes, regras e configurações globais do Lions SpreadSurgeon."""

from enum import Enum

# ── Status markers ─────────────────────────────────────────────────────────────
class Status(str, Enum):
    OK            = "OK"
    PENDENTE      = "PENDENTE"
    VERIFICAR     = "VERIFICAR"
    BLOQUEIO_FISCAL = "BLOQUEIO FISCAL"
    RISCO_PUBLICACAO = "RISCO DE PUBLICAÇÃO"
    RISCO_PREJUIZO   = "RISCO DE PREJUÍZO"
    ERRO          = "ERRO"


# ── Canais suportados ──────────────────────────────────────────────────────────
CANAIS = ["bling", "tray", "mercado_livre", "shopee", "amazon", "magalu",
          "site", "loja_fisica", "televendas", "whatsapp"]

# ── Campos que NUNCA devem ser modificados sem autorização ────────────────────
CAMPOS_PROTEGIDOS = ["sku", "ean", "gtin", "ncm", "cest", "codigo_interno",
                     "id_produto", "id_variacao"]

# ── NCM: deve ter 8 dígitos ───────────────────────────────────────────────────
NCM_LENGTH = 8

# ── EAN/GTIN válidos: 8, 12, 13 ou 14 dígitos ────────────────────────────────
GTIN_LENGTHS = {8, 12, 13, 14}

# ── Limites de título por canal ───────────────────────────────────────────────
TITULO_MAX = {
    "mercado_livre": 60,
    "shopee": 120,
    "amazon": 200,
    "magalu": 150,
    "bling": 120,
    "tray": 160,
    "site": 200,
}

# ── Categorias de produto suportadas ─────────────────────────────────────────
CATEGORIAS = [
    "Chaves",
    "Fechaduras Pado",
    "Cadeados",
    "Cilindros",
    "Dobradiças",
    "Acessórios",
    "Digitais",
    "Puxadores",
    "Automotivo",
    "Pinos e Molas",
    "Ferragens",
    "Ferramentas",
]

# ── Campos obrigatórios mínimos por canal ────────────────────────────────────
CAMPOS_OBRIGATORIOS = {
    "bling": ["codigo", "descricao", "preco_venda", "unidade"],
    "amazon": ["item_sku", "item_name", "brand_name", "bullet_point1",
               "bullet_point2", "description", "standard_price",
               "quantity", "main_image_url"],
    "mercado_livre": ["title", "price", "available_quantity", "category_id",
                      "condition", "listing_type_id"],
    "shopee": ["item_name", "price", "stock", "category", "description",
               "main_image"],
    "magalu": ["nome", "ean", "marca", "descricao", "preco", "estoque",
               "ncm", "imagem_principal"],
}

# ── Mapeamentos de encoding ───────────────────────────────────────────────────
BLING_ENCODING = "latin-1"
BLING_SEPARATOR = ";"
BLING_DECIMAL = ","

# ── Score: pesos dos critérios ────────────────────────────────────────────────
SCORE_PESOS = {
    "titulo":         15,
    "descricao":      15,
    "imagens":        15,
    "preco":          10,
    "custo_margem":   10,
    "estoque":        10,
    "ean_ncm":        10,
    "categoria":       5,
    "marca":           5,
    "ficha_tecnica":   5,
}

# ── Estrutura do template Amazon ─────────────────────────────────────────────
AMAZON_HEADER_ROW   = 3   # 0-indexed → linha 4
AMAZON_TECHNICAL_ROW = 4  # linha 5
AMAZON_EXAMPLE_ROW  = 5   # linha 6
AMAZON_DATA_START   = 6   # linha 7+

# ── Estrutura HTML padrão para descrição ─────────────────────────────────────
HTML_SECTION_STYLE = (
    'style="background:#000;color:#fff;border-left:4px solid #FF8C00;'
    'padding:8px 12px;font-family:Arial,sans-serif;font-size:14px;'
    'margin:16px 0 4px 0;"'
)
HTML_TABLE_STYLE = (
    'style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;'
    'font-size:13px;"'
)
HTML_ROW_EVEN  = 'style="background:#f9f9f9;"'
HTML_ROW_ODD   = 'style="background:#ffffff;"'
HTML_TD_LABEL  = 'style="padding:6px 10px;font-weight:bold;width:40%;'  \
                 'border-bottom:1px solid #ddd;"'
HTML_TD_VALUE  = 'style="padding:6px 10px;border-bottom:1px solid #ddd;"'

# ── Comandos reconhecidos ─────────────────────────────────────────────────────
COMANDOS = {
    "/analisar_planilha",
    "/corrigir_erros",
    "/mapear_colunas",
    "/padronizar_titulo",
    "/validar_sku_ean",
    "/validar_bling",
    "/validar_amazon",
    "/validar_mercado_livre",
    "/validar_shopee",
    "/validar_magalu",
    "/gerar_checklist",
    "/criar_estrategia",
    "/criar_campanha",
    "/criar_kit",
    "/qa_final",
    "/gerar_json",
}

# ── Regex ─────────────────────────────────────────────────────────────────────
import re

RE_SCIENTIFIC  = re.compile(r"^\d+\.?\d*[Ee][+\-]?\d+$")
RE_ONLY_DIGITS = re.compile(r"^\d+$")
RE_PRICE_BR    = re.compile(r"^\d{1,}(\.\d{3})*(,\d{2})?$")
RE_PRICE_US    = re.compile(r"^\d{1,}(\,\d{3})*(\.\d{2})?$")

"""Diagnóstico de erros de importação em marketplaces e ERPs."""

from dataclasses import dataclass, field
from typing import Optional

from spreadsurgeon.config import Status


@dataclass
class ImportError:
    channel: str
    row: int
    sku: str
    field: str
    error_message: str
    probable_cause: str
    suggested_fix: str
    status: Status
    next_step: str


@dataclass
class ImportDiagnosisReport:
    channel: str
    total_errors: int
    errors: list[ImportError] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)


# Regras de correspondência: fragmento da mensagem de erro → diagnóstico
_ERROR_RULES = [
    # EAN / GTIN
    {
        "keywords": ["gtin", "ean", "barcode", "código de barras"],
        "field":    "ean",
        "cause":    "EAN inválido, em notação científica ou com dígito verificador incorreto",
        "fix":      "Formatar célula como Texto, confirmar EAN na embalagem/NF e recalcular dígito verificador",
        "status":   Status.ERRO,
        "next":     "Corrigir EAN e reenviar linha",
    },
    # NCM / fiscal
    {
        "keywords": ["ncm", "fiscal", "tribut", "icms", "nf-e", "nfe", "nota fiscal"],
        "field":    "ncm",
        "cause":    "NCM ausente, incorreto ou incompatível com o produto",
        "fix":      "Consultar tabela TIPI ou contador — NÃO inferir NCM",
        "status":   Status.BLOQUEIO_FISCAL,
        "next":     "Bloquear envio até NCM ser validado por profissional fiscal",
    },
    # Título / nome longo
    {
        "keywords": ["title", "titulo", "name", "nome", "caracteres", "characters", "too long"],
        "field":    "titulo",
        "cause":    "Título ultrapassa o limite de caracteres do canal",
        "fix":      "Reduzir título respeitando o limite do canal (ML: 60 | Shopee: 120 | Amazon: 200)",
        "status":   Status.ERRO,
        "next":     "Corrigir título e reenviar",
    },
    # Preço zerado
    {
        "keywords": ["price", "preco", "preço", "valor", "zero", "0.00"],
        "field":    "preco",
        "cause":    "Preço zerado ou em formato incorreto (ponto vs vírgula decimal)",
        "fix":      "Preencher preço. Usar vírgula decimal no Bling (29,90) e ponto no Amazon (29.90)",
        "status":   Status.RISCO_PUBLICACAO,
        "next":     "Corrigir formato de preço e reenviar",
    },
    # Imagem
    {
        "keywords": ["image", "imagem", "foto", "url", "invalid url", "http"],
        "field":    "imagem",
        "cause":    "URL de imagem inválida ou imagem sem resolução mínima exigida",
        "fix":      "Verificar URL no navegador. Usar HTTPS. Garantir resolução mínima (500x500px)",
        "status":   Status.RISCO_PUBLICACAO,
        "next":     "Substituir URL e reenviar",
    },
    # Categoria
    {
        "keywords": ["categor", "category", "department"],
        "field":    "categoria",
        "cause":    "Categoria inválida ou não mapeada no canal",
        "fix":      "Consultar lista oficial de categorias do canal e usar ID correto",
        "status":   Status.ERRO,
        "next":     "Corrigir category_id e reenviar",
    },
    # SKU duplicado
    {
        "keywords": ["duplicate", "duplicado", "already exists", "já existe", "sku"],
        "field":    "sku",
        "cause":    "SKU duplicado — mesmo código já cadastrado no canal",
        "fix":      "Verificar se o produto já existe. Se sim, use atualização em vez de criação",
        "status":   Status.ERRO,
        "next":     "Identificar SKU existente e usar endpoint de atualização",
    },
    # Encoding
    {
        "keywords": ["encoding", "utf", "latin", "charset", "caractere especial", "special char"],
        "field":    "encoding",
        "cause":    "Caracteres especiais corrompidos por encoding incorreto",
        "fix":      "Exportar CSV em UTF-8 (ou latin-1 para Bling). Não abrir CSV no Excel antes de exportar",
        "status":   Status.ERRO,
        "next":     "Re-exportar arquivo com encoding correto",
    },
    # Estoque
    {
        "keywords": ["stock", "estoque", "quantity", "quantidade", "inventory"],
        "field":    "estoque",
        "cause":    "Estoque zero, negativo ou em formato inválido",
        "fix":      "Corrigir valor de estoque. Estoque deve ser inteiro positivo",
        "status":   Status.RISCO_PUBLICACAO,
        "next":     "Atualizar saldo de estoque e reenviar",
    },
    # Variação / variante
    {
        "keywords": ["variation", "variação", "variante", "variant", "size", "color"],
        "field":    "variacao",
        "cause":    "Variação não mapeada corretamente ou pai/filho inconsistente",
        "fix":      "Verificar estrutura pai/filho de variações. Cadastrar produto pai antes das variantes",
        "status":   Status.ERRO,
        "next":     "Reenviar produto pai primeiro, depois as variações",
    },
]


def _match_rule(error_msg: str) -> Optional[dict]:
    msg_lower = error_msg.lower()
    for rule in _ERROR_RULES:
        if any(k in msg_lower for k in rule["keywords"]):
            return rule
    return None


def diagnose_import_errors(
    errors_raw: list[dict],
    channel: str,
) -> ImportDiagnosisReport:
    """
    errors_raw: lista de dicts com chaves: row, sku, field, error_message
    """
    report = ImportDiagnosisReport(channel=channel)
    classified: list[ImportError] = []

    status_counts: dict[str, int] = {}

    for e in errors_raw:
        row     = int(e.get("row", 0))
        sku     = str(e.get("sku", "?"))
        field   = str(e.get("field", "?"))
        msg     = str(e.get("error_message", ""))

        rule = _match_rule(f"{field} {msg}")

        if rule:
            ie = ImportError(
                channel=channel,
                row=row,
                sku=sku,
                field=rule["field"],
                error_message=msg,
                probable_cause=rule["cause"],
                suggested_fix=rule["fix"],
                status=rule["status"],
                next_step=rule["next"],
            )
        else:
            ie = ImportError(
                channel=channel,
                row=row,
                sku=sku,
                field=field,
                error_message=msg,
                probable_cause="Causa não identificada automaticamente — requer análise manual",
                suggested_fix="Analisar mensagem de erro original do canal",
                status=Status.VERIFICAR,
                next_step="Verificar documentação do canal e entrar em contato com suporte se necessário",
            )

        classified.append(ie)
        key = ie.status.value
        status_counts[key] = status_counts.get(key, 0) + 1

    report.errors = classified
    report.total_errors = len(classified)
    report.summary = {
        "canal":    channel,
        "total":    report.total_errors,
        "por_status": status_counts,
    }
    report.next_steps = [
        f"1. Corrigir todos os erros de status '{Status.BLOQUEIO_FISCAL.value}' primeiro",
        f"2. Resolver erros de '{Status.ERRO.value}' antes de reenviar",
        f"3. Validar itens '{Status.VERIFICAR.value}' com equipe ou suporte do canal",
        "4. Re-exportar arquivo com correções aplicadas",
        "5. Executar /validar_bling ou /validar_amazon antes do próximo envio",
    ]
    return report

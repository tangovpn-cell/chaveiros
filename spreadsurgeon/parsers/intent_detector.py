"""Detector automático de intenção do usuário e tipo de entrada."""

import re
from dataclasses import dataclass
from typing import Optional

from spreadsurgeon.config import COMANDOS, CANAIS


@dataclass
class Intent:
    command: Optional[str]       # comando explícito (/analisar_planilha, etc.)
    channel: Optional[str]       # canal detectado (bling, amazon, etc.)
    action: str                  # ação principal inferida
    file_type: Optional[str]     # tipo de arquivo detectado
    confidence: str              # high | medium | low
    notes: list[str]


def detect_intent(user_input: str, filename: str = "") -> Intent:
    text = user_input.strip().lower()
    notes = []

    # 1. Comando explícito
    command = None
    for cmd in COMANDOS:
        if cmd in text:
            command = cmd
            break

    # 2. Canal
    channel = None
    canal_aliases = {
        "bling": ["bling"],
        "amazon": ["amazon", "amz"],
        "mercado_livre": ["mercado livre", "meli", "mercadolivre", "ml"],
        "shopee": ["shopee"],
        "magalu": ["magalu", "magazine luiza", "magazineluiza"],
        "tray": ["tray"],
        "site": ["site", "woocommerce", "loja virtual", "vtex"],
        "loja_fisica": ["loja física", "loja fisica", "pdv"],
        "televendas": ["televendas", "tele vendas"],
        "whatsapp": ["whatsapp", "zap"],
    }
    for canal, aliases in canal_aliases.items():
        if any(a in text for a in aliases):
            channel = canal
            break

    # 3. Tipo de arquivo (pelo nome)
    file_type = None
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("csv", "tsv", "txt", "xlsx", "xlsm", "xls"):
            file_type = ext

    # 4. Ação inferida
    action_map = [
        (["analisa", "audita", "verifica", "checar", "check"], "audit"),
        (["corrige", "corrigi", "corrigir", "fix", "ajust"], "fix"),
        (["mapeia", "mapear", "mapear colunas"], "map_columns"),
        (["padroniza", "padronizar", "título", "titulo"], "standardize_title"),
        (["valida", "validar", "validação", "importa"], "validate"),
        (["estratégia", "estrategia", "estratégico"], "strategy"),
        (["campanha", "campaign", "promo"], "campaign"),
        (["kit", "combo", "pacote"], "kit"),
        (["descrição", "descricao", "html", "detalhe"], "description"),
        (["erro de importação", "erro de import", "rejeição"], "import_error"),
        (["checklist", "check list", "pré-envio"], "checklist"),
        (["score", "qualidade", "nota"], "score"),
        (["json", "exporta", "exportar"], "export_json"),
    ]
    action = "general"
    for keywords, act in action_map:
        if any(k in text for k in keywords):
            action = act
            break

    # Mapeamento comando → action
    if command:
        cmd_action = {
            "/analisar_planilha":   "audit",
            "/corrigir_erros":      "fix",
            "/mapear_colunas":      "map_columns",
            "/padronizar_titulo":   "standardize_title",
            "/validar_sku_ean":     "validate_sku_ean",
            "/validar_bling":       "validate",
            "/validar_amazon":      "validate",
            "/validar_mercado_livre": "validate",
            "/validar_shopee":      "validate",
            "/validar_magalu":      "validate",
            "/gerar_checklist":     "checklist",
            "/criar_estrategia":    "strategy",
            "/criar_campanha":      "campaign",
            "/criar_kit":           "kit",
            "/qa_final":            "audit",
            "/gerar_json":          "export_json",
        }
        action = cmd_action.get(command, action)

        # Canal pelo comando
        if not channel:
            cmd_channel = {
                "/validar_bling":         "bling",
                "/validar_amazon":        "amazon",
                "/validar_mercado_livre": "mercado_livre",
                "/validar_shopee":        "shopee",
                "/validar_magalu":        "magalu",
            }
            channel = cmd_channel.get(command)

    # 5. Confiança
    confidence = "low"
    if command:
        confidence = "high"
    elif channel and action != "general":
        confidence = "medium"
    elif action != "general":
        confidence = "medium"

    if confidence == "low":
        notes.append("Intenção não detectada com clareza — assumindo auditoria geral")

    return Intent(command=command, channel=channel, action=action,
                  file_type=file_type, confidence=confidence, notes=notes)

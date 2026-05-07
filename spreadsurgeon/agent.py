"""Lions SpreadSurgeon — Agente principal de orquestração."""

import json
import os
from dataclasses import asdict
from typing import Optional

from spreadsurgeon.config import Status, COMANDOS
from spreadsurgeon.parsers.file_parser import parse_file, parse_pasted
from spreadsurgeon.parsers.intent_detector import detect_intent
from spreadsurgeon.validators.bling import BlingValidator
from spreadsurgeon.validators.amazon import AmazonValidator
from spreadsurgeon.validators.mercado_livre import MercadoLivreValidator
from spreadsurgeon.validators.shopee import ShopeeValidator
from spreadsurgeon.validators.magalu import MagaluValidator
from spreadsurgeon.modules.spreadsheet_auditor import audit
from spreadsurgeon.modules.score_engine import score_rows, aggregate_score
from spreadsurgeon.modules.title_standardizer import standardize_title, batch_standardize
from spreadsurgeon.modules.description_generator import generate_html_description, DescriptionData
from spreadsurgeon.modules.commercial_strategy import create_strategy, ProductProfile
from spreadsurgeon.modules.campaign_creator import create_campaign, CampaignInput
from spreadsurgeon.modules.kit_creator import create_kit, KitInput, KitComponent
from spreadsurgeon.modules.checklist_generator import generate_checklist
from spreadsurgeon.modules.import_error_diagnostics import diagnose_import_errors
from spreadsurgeon.modules.log_generator import new_log
from spreadsurgeon.utils.formatting import (section, subsection, bullet,
                                             status_line, table, numbered_list,
                                             score_bar, render_dict, alert)
from spreadsurgeon.utils.text_utils import safe_str


VALIDATORS = {
    "bling":         BlingValidator(),
    "amazon":        AmazonValidator(),
    "mercado_livre": MercadoLivreValidator(),
    "shopee":        ShopeeValidator(),
    "magalu":        MagaluValidator(),
}


class SpreadSurgeon:
    """Agente principal — recebe entrada e roteia para o módulo correto."""

    def __init__(self):
        self.log = new_log()

    # ── Ponto de entrada principal ────────────────────────────────────────────
    def process(
        self,
        user_input: str,
        filepath: str = "",
        pasted_data: str = "",
    ) -> str:
        intent = detect_intent(user_input, filepath)
        parts: list[str] = []

        # Banner
        parts.append(
            "\n╔══════════════════════════════════════════════════════════════════════╗\n"
            "║          LIONS SPREADSURGEON — Agente Operacional E-commerce         ║\n"
            "║   Modo Seguro Ativo: Nenhum dado será inventado ou alterado sem      ║\n"
            "║   autorização. Campos problemáticos serão marcados com status.       ║\n"
            "╚══════════════════════════════════════════════════════════════════════╝"
        )

        if intent.notes:
            for n in intent.notes:
                parts.append(bullet(n, "ℹ"))

        # Carregar dados
        tables = []
        if filepath and os.path.exists(filepath):
            result = parse_file(filepath)
            tables = result.tables
            if result.errors:
                parts.append(alert("; ".join(result.errors), "ERRO DE LEITURA"))
        elif pasted_data:
            result = parse_pasted(pasted_data)
            tables = result.tables

        rows = tables[0].rows if tables else []

        action = intent.action
        channel = intent.channel or "bling"

        # ── Roteamento ────────────────────────────────────────────────────────
        if action == "audit" or intent.command in ("/analisar_planilha", "/qa_final"):
            parts.append(self._run_audit(tables, filepath))

        elif action == "validate" or intent.command in (
                "/validar_bling", "/validar_amazon", "/validar_mercado_livre",
                "/validar_shopee", "/validar_magalu", "/validar_sku_ean"):
            parts.append(self._run_validate(rows, channel))

        elif action == "map_columns" or intent.command == "/mapear_colunas":
            parts.append(self._run_map_columns(tables))

        elif action == "standardize_title" or intent.command == "/padronizar_titulo":
            if rows:
                parts.append(self._run_batch_titles(rows, channel))
            else:
                # Tenta padronizar o próprio input como título
                parts.append(self._run_single_title(user_input.replace("/padronizar_titulo", "").strip(), channel))

        elif action == "strategy" or intent.command == "/criar_estrategia":
            parts.append(self._run_strategy(rows))

        elif action == "campaign" or intent.command == "/criar_campanha":
            parts.append(self._run_campaign_template())

        elif action == "kit" or intent.command == "/criar_kit":
            parts.append(self._run_kit_template())

        elif action == "checklist" or intent.command == "/gerar_checklist":
            if rows:
                parts.append(self._run_checklist(rows[0], channel))
            else:
                parts.append(alert("Nenhum dado carregado. Forneça um arquivo ou cole dados.", "PENDENTE"))

        elif action == "import_error":
            parts.append(self._run_import_error_template(channel))

        elif action == "description":
            parts.append(self._run_description_template())

        elif action == "export_json" or intent.command == "/gerar_json":
            if rows:
                parts.append(self._run_export_json(rows))
            else:
                parts.append(alert("Nenhum dado para exportar", "PENDENTE"))

        else:
            # Auditoria geral por padrão
            if tables:
                parts.append(self._run_audit(tables, filepath))
            else:
                parts.append(self._help())

        # Log
        parts.append(section("Log de Sessão"))
        parts.append(self.log.to_text())

        return "\n".join(parts)

    # ── Módulos ───────────────────────────────────────────────────────────────

    def _run_audit(self, tables, source: str) -> str:
        if not tables:
            return alert("Nenhum dado carregado para auditoria", "PENDENTE")

        report = audit(tables, source)
        out = [section("AUDITORIA DE PLANILHA")]
        out.append(subsection("ANÁLISE GERAL"))
        out.append(table([
            ("Abas / tabelas",  str(report.total_sheets)),
            ("Total de linhas", str(report.total_rows)),
            ("Total de colunas",str(report.total_cols)),
            ("Erros",           str(report.error_count)),
            ("Avisos",          str(report.warning_count)),
        ]))

        if report.issues:
            out.append(subsection("ERROS E AVISOS"))
            for iss in report.issues[:50]:   # limitar saída
                out.append(status_line(iss.location, iss.status.value, iss.message))
                if iss.suggestion:
                    out.append(f"      → {iss.suggestion}")
            if len(report.issues) > 50:
                out.append(f"  ... e mais {len(report.issues)-50} item(ns). Exportar JSON para lista completa.")

        out.append(subsection("CORREÇÕES SEGURAS"))
        out.append(numbered_list(report.safe_corrections))

        out.append(subsection("PENDÊNCIAS HUMANAS"))
        out.append(numbered_list(report.human_pending))

        out.append(subsection("PLANO DE CORREÇÃO"))
        out.append(numbered_list(report.correction_plan))

        self.log.add("auditoria", "planilha", source, "auditada", source="auditoria automática")
        return "\n".join(out)

    def _run_validate(self, rows: list[dict], channel: str) -> str:
        validator = VALIDATORS.get(channel, VALIDATORS["bling"])
        result = validator.validate(rows)
        out = [section(f"VALIDAÇÃO — {channel.upper().replace('_', ' ')}")]
        out.append(table([
            ("Total linhas",    str(result.total_rows)),
            ("Linhas válidas",  str(result.valid_rows)),
            ("Erros",           str(result.error_count)),
            ("Avisos",          str(result.warning_count)),
            ("Bloqueios",       str(result.block_count)),
        ]))
        if result.issues:
            out.append(subsection("PROBLEMAS ENCONTRADOS"))
            for iss in result.issues[:60]:
                out.append(status_line(
                    f"L{iss.row} | {iss.sku} | {iss.field}",
                    iss.status.value,
                    iss.message
                ))
                if iss.suggestion:
                    out.append(f"      → {iss.suggestion}")
        if result.pending_human:
            out.append(subsection("PENDÊNCIAS HUMANAS"))
            out.append(numbered_list(result.pending_human))
        if result.corrections:
            out.append(subsection("REGRAS DO CANAL"))
            out.append(numbered_list(result.corrections))
        out.append(subsection("PRÓXIMOS PASSOS"))
        out.append(numbered_list(result.next_steps))
        return "\n".join(out)

    def _run_map_columns(self, tables) -> str:
        if not tables:
            return alert("Nenhuma tabela carregada", "PENDENTE")
        out = [section("MAPEAMENTO DE COLUNAS")]
        for t in tables:
            label = t.sheet_name or t.source_type
            out.append(subsection(f"Aba: {label}"))
            out.append(f"  Total de colunas: {len(t.headers)}")
            out.append(f"  Total de linhas:  {len(t.rows)}")
            out.append(f"  Colunas detectadas:")
            for h in t.headers:
                out.append(f"    • {h}")
            if t.warnings:
                out.append("  Avisos do parser:")
                for w in t.warnings:
                    out.append(f"    ⚠ {w}")
        return "\n".join(out)

    def _run_single_title(self, raw: str, channel: str) -> str:
        result = standardize_title(raw, channel=channel)
        out = [section("PADRONIZAÇÃO DE TÍTULO")]
        out.append(table([
            ("Categoria detectada",  result.category),
            ("Estrutura aplicada",   result.structure_applied),
            ("Título original",      result.original),
            ("Título final",         result.final_title),
            ("Comprimento",          str(result.length)),
        ]))
        if result.adjustments:
            out.append(subsection("Ajustes realizados"))
            out.append(numbered_list(result.adjustments))
        if result.warnings:
            out.append(subsection("Avisos"))
            for w in result.warnings:
                out.append(bullet(w, "⚠"))
        return "\n".join(out)

    def _run_batch_titles(self, rows: list[dict], channel: str) -> str:
        # Tentar encontrar coluna de título
        title_col = next(
            (c for c in rows[0] if any(k in c for k in
             ("titulo", "título", "title", "nome", "item_name", "descricao"))),
            None
        )
        if not title_col:
            return alert("Coluna de título não encontrada. Use /mapear_colunas primeiro.", "PENDENTE")
        results = batch_standardize(rows, title_col=title_col, channel=channel)
        out = [section(f"PADRONIZAÇÃO DE TÍTULOS — {len(results)} itens")]
        for r in results:
            out.append(f"\n  Original : {r.original[:80]}")
            out.append(f"  Final    : {r.final_title}")
            out.append(f"  Cat.     : {r.category} | Chars: {r.length}")
            if r.warnings:
                for w in r.warnings:
                    out.append(f"  ⚠ {w}")
        return "\n".join(out)

    def _run_strategy(self, rows: list[dict]) -> str:
        if not rows:
            return alert("Nenhum dado carregado para análise estratégica", "PENDENTE")

        products = []
        for row in rows:
            def g(k): return safe_str(row.get(k, ""))
            from spreadsurgeon.utils.text_utils import price_to_float
            price  = price_to_float(g("preco_venda") or g("preco") or g("price")) or 0
            cost   = price_to_float(g("custo") or g("cost")) or 0
            margin = ((price - cost) / price * 100) if price > 0 else 0
            try:
                stock = float((g("estoque") or g("stock") or "0").replace(",", "."))
            except ValueError:
                stock = 0
            try:
                qty_sold = float((g("qtd_vendida") or g("qty_sold") or "0").replace(",", "."))
            except ValueError:
                qty_sold = 0
            revenue = price * qty_sold
            products.append(ProductProfile(
                sku=g("sku") or g("codigo") or f"SKU_{len(products)+1}",
                name=g("descricao") or g("nome") or g("item_name") or "?",
                category=g("categoria"),
                brand=g("marca"),
                channel=g("canal"),
                quantity_sold=qty_sold,
                revenue=revenue,
                margin_pct=margin,
                stock=stock,
                price=price,
                cost=cost,
            ))

        report = create_strategy(products)
        out = [section("ESTRATÉGIA COMERCIAL")]
        out.append(subsection("1. DIAGNÓSTICO RÁPIDO"))
        out.append(numbered_list(report.diagnosis))
        out.append(subsection("2. PRODUTOS PRIORITÁRIOS"))
        out.append(numbered_list(report.priority_products) if report.priority_products
                   else "  Nenhum produto prioritário identificado com os dados fornecidos")
        out.append(subsection("3. SEGMENTAÇÃO"))
        for seg, skus in report.segments.items():
            out.append(f"  [{seg}] → {', '.join(skus[:10])}" +
                       (f" e +{len(skus)-10}" if len(skus) > 10 else ""))
        if report.blocked:
            out.append(subsection("PRODUTOS BLOQUEADOS — NÃO ANUNCIAR"))
            for b in report.blocked:
                out.append(f"  ✗ {b}")
        out.append(subsection("PRÓXIMOS PASSOS"))
        out.append(numbered_list(report.next_steps))
        return "\n".join(out)

    def _run_campaign_template(self) -> str:
        return section("CRIADOR DE CAMPANHA") + """

  Preencha os dados abaixo e re-execute com /criar_campanha:

  Nome da campanha:       [ex: Promoção Fechaduras Junho]
  Objetivo:               [ex: Aumentar volume de vendas em 20%]
  Público:                [ex: Chaveiros e serralheiros SP]
  SKUs indicados:         [ex: FEL-001, FEL-002, CAD-010]
  Chamada principal:      [ex: Segurança que não falha]
  Argumentos de venda:    [ex: Garantia 5 anos, instalação fácil]
  Oferta:                 [ex: Frete grátis acima de R$ 150]
  Canal recomendado:      [ex: WhatsApp + Mercado Livre]
  Criativo sugerido:      [ex: Vídeo de 30s demonstrando instalação]
  Métrica de sucesso:     [ex: 50 unidades vendidas em 7 dias]

  ⚠ ATENÇÃO: A campanha só será aprovada após validação de:
    - Estoque disponível para os SKUs
    - Margem positiva após descontos
    - Cadastro completo e imagens aprovadas
    - Título e categoria corretos no canal
"""

    def _run_kit_template(self) -> str:
        return section("CRIADOR DE KIT") + """

  Preencha os dados abaixo e re-execute com /criar_kit:

  Nome do kit:            [ex: Kit Segurança Porta Principal]
  Componentes (SKU|Nome|Preço|Estoque|Qtd no kit):
    [ex: FEL-001|Fechadura Pado 300|89.90|15|1]
    [ex: CIL-005|Cilindro 40mm|29.90|12|1]
    [ex: CHA-010|Chave Reserva|5.00|50|2]
  Lógica do kit:          [ex: Fechadura + cilindro compatível + 2 chaves reserva]
  Canal ideal:            [ex: Site próprio | WhatsApp]
  Desconto do kit (%):    [ex: 12]
  Oferta sugerida:        [ex: Kit completo por R$ 120,00]

  ⚠ O kit só será marcado como VIÁVEL se todos os componentes
    tiverem estoque positivo e margem positiva após desconto.
"""

    def _run_checklist(self, row: dict, channel: str) -> str:
        checklist = generate_checklist(channel, row)
        out = [section(f"CHECKLIST PRÉ-ENVIO — {channel.upper().replace('_', ' ')}")]
        out.append(table([
            ("SKU",            checklist.sku),
            ("Produto",        checklist.product_name[:60]),
            ("Canal",          checklist.channel),
            ("Score",          f"{checklist.score}%"),
            ("Pronto p/ envio",  "✅ SIM" if checklist.ready_to_send else "❌ NÃO"),
        ]))
        out.append(subsection("Itens"))
        for item in checklist.items:
            icon = "✅" if item.status == "OK" else ("🚫" if item.critical else "⚠")
            crit = " [CRÍTICO]" if item.critical else ""
            out.append(f"  {icon} {item.status:<9} {item.item}{crit}")
            if item.note:
                out.append(f"          → {item.note}")
        if checklist.blockers:
            out.append(subsection("BLOQUEADORES — Resolver antes de enviar"))
            out.append(numbered_list(checklist.blockers))
        return "\n".join(out)

    def _run_import_error_template(self, channel: str) -> str:
        return section("DIAGNÓSTICO DE ERRO DE IMPORTAÇÃO") + f"""

  Canal detectado: {channel}

  Para diagnóstico automático, forneça os erros no formato:
    row=5; sku=FEL-001; field=ean; error_message=Invalid GTIN

  Ou cole a mensagem de erro do canal abaixo.

  Erros comuns por canal:
    Bling:        EAN em notação científica | Encoding incorreto | Preço com ponto
    Amazon:       Dimensão sem unidade | Bullet vazio | XLSM corrompido
    Mercado Livre:Título > 60 chars | category_id inválido | Imagem sem HTTPS
    Shopee:       Título > 120 chars | Categoria inválida
    Magalu:       NCM ausente (BLOQUEIO FISCAL) | EAN inválido
"""

    def _run_description_template(self) -> str:
        return section("GERADOR DE DESCRIÇÃO TÉCNICA HTML") + """

  Forneça os dados do produto no formato abaixo:

  sku:            [ex: FEL-300-CP]
  titulo:         [ex: Fechadura Pado 300 Cromada com Chave]
  categoria:      [ex: Fechaduras Pado]
  marca:          [ex: Pado]
  especificacoes:
    Material:     [ex: Zamak cromado]
    Medidas:      [ex: 20x15cm]
    Acabamento:   [ex: Cromado brilhante]
    Voltagem:     [ex: N/A]
  beneficios:
    - [ex: Alta resistência a arrombamento]
    - [ex: Chave com sistema de segredo exclusivo]
  compatibilidade:
    - [ex: Portas de madeira espessura 35-55mm]
  itens_inclusos:
    - [ex: 1 Fechadura]
    - [ex: 3 Chaves]
    - [ex: Manual de instalação]
  instalacao:     [ex: Encaixe padrão 55mm, instalação sem furação adicional]

  ⚠ MODO SEGURO: Campos não informados serão marcados como
    "a confirmar" — NUNCA serão inventados.
"""

    def _run_export_json(self, rows: list[dict]) -> str:
        out = [section("EXPORTAÇÃO JSON")]
        j = json.dumps(rows[:100], ensure_ascii=False, indent=2)
        out.append(j)
        if len(rows) > 100:
            out.append(f"\n  ... exportados 100 de {len(rows)} registros.")
        return "\n".join(out)

    def _help(self) -> str:
        return section("LIONS SPREADSURGEON — COMANDOS DISPONÍVEIS") + "\n" + "\n".join(
            f"  {cmd}" for cmd in sorted(COMANDOS)
        ) + """

  USO BÁSICO:
    python -m spreadsurgeon.cli /analisar_planilha --file planilha.xlsx
    python -m spreadsurgeon.cli /validar_bling --file produtos.csv
    python -m spreadsurgeon.cli /padronizar_titulo "Fechadura Pado 300 cromada"
    python -m spreadsurgeon.cli /criar_estrategia --file vendas.xlsx
    python -m spreadsurgeon.cli /gerar_checklist --file produto.csv --canal magalu

  ENTRADAS ACEITAS: CSV, TSV, TXT, XLSX, XLSM, XLS, dados colados

  MODO SEGURO SEMPRE ATIVO:
    • Nunca inventa dados
    • Nunca altera SKU sem autorização
    • Nunca preenche campo no escuro
    • Sempre separa: fato confirmado | inferência | sugestão
    • Sempre marca: PENDENTE | VERIFICAR | BLOQUEIO FISCAL |
                    RISCO DE PUBLICAÇÃO | RISCO DE PREJUÍZO
"""

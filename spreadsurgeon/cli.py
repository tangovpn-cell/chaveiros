#!/usr/bin/env python3
"""CLI do Lions SpreadSurgeon."""

import argparse
import sys

from spreadsurgeon.agent import SpreadSurgeon


def main():
    parser = argparse.ArgumentParser(
        prog="spreadsurgeon",
        description="Lions SpreadSurgeon — Agente operacional para e-commerce",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="",
        help="Comando (/analisar_planilha, /validar_bling, etc.) ou texto livre",
    )
    parser.add_argument(
        "--file", "-f",
        default="",
        help="Caminho para o arquivo a processar (CSV, XLSX, XLSM, XLS, TXT, TSV)",
    )
    parser.add_argument(
        "--canal", "-c",
        default="",
        help="Canal alvo: bling | amazon | mercado_livre | shopee | magalu | site",
    )
    parser.add_argument(
        "--paste", "-p",
        default="",
        help="Dados colados diretamente (texto CSV inline)",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Arquivo de saída (texto ou .json). Se omitido, exibe no terminal.",
    )
    args = parser.parse_args()

    user_input = args.command
    if args.canal:
        user_input = f"{user_input} {args.canal}"

    agent = SpreadSurgeon()
    result = agent.process(
        user_input=user_input,
        filepath=args.file,
        pasted_data=args.paste,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[SpreadSurgeon] Resultado salvo em: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()

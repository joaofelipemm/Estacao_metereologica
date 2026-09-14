"""Sincroniza um arquivo CSV com o Supabase."""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from database_sync import DEFAULT_STATE_FILE, sync_csv_to_database


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Envia leituras novas do CSV para o Supabase."
	)
	parser.add_argument("arquivo", type=Path, help="Caminho do arquivo CSV.")
	parser.add_argument(
		"--estado",
		type=Path,
		default=None,
		help="Arquivo de checkpoint; por padrao fica ao lado do CSV.",
	)
	parser.add_argument("--tabela", default="leituras")
	parser.add_argument("--lote", type=int, default=100)
	return parser


def main() -> None:
	load_dotenv()
	arguments = build_argument_parser().parse_args()
	if not arguments.arquivo.exists():
		raise SystemExit(f"arquivo nao encontrado: {arguments.arquivo}")
	state_file = arguments.estado or arguments.arquivo.with_name(DEFAULT_STATE_FILE)
	sent_count = sync_csv_to_database(
		arguments.arquivo,
		state_file,
		arguments.tabela,
		arguments.lote,
	)
	print(f"Concluido: {sent_count} registro(s) novo(s) enviado(s).")


if __name__ == "__main__":
	main()
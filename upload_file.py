"""Envia leituras de um arquivo CSV para uma tabela do Supabase."""

import argparse
import csv
import os
from datetime import datetime
from pathlib import Path

import requests

try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover
	def load_dotenv(*_args, **_kwargs):
		return False


load_dotenv()

DEFAULT_TABLE = "leituras"
CSV_COLUMNS = {"data", "hora", "temperatura", "umidade"}


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Envia as leituras de um CSV para o Supabase."
	)
	parser.add_argument("arquivo", type=Path, help="Caminho do arquivo CSV.")
	parser.add_argument(
		"--tabela",
		default=DEFAULT_TABLE,
		help=f"Tabela de destino (padrao: {DEFAULT_TABLE}).",
	)
	parser.add_argument(
		"--lote",
		type=int,
		default=100,
		help="Quantidade de registros por requisicao (padrao: 100).",
	)
	return parser


def get_required_environment() -> tuple[str, str]:
	project_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
	supabase_key = (
		os.getenv("SUPABASE_SERVICE_ROLE_KEY")
		or os.getenv("SUPABASE_ANON_KEY")
		or os.getenv("SUPABASE_KEY", "")
	).strip()
	if not project_url or not supabase_key:
		raise RuntimeError(
			"configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY) no .env"
		)
	if not project_url.startswith(("http://", "https://")):
		raise RuntimeError("SUPABASE_URL deve comecar com http:// ou https://")
	return project_url, supabase_key


def normalize_date(value: str) -> str:
	value = value.strip()
	for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
		try:
			return datetime.strptime(value, date_format).strftime("%Y-%m-%d")
		except ValueError:
			continue
	raise ValueError(f"data invalida: {value}")


def read_rows(csv_file: Path) -> list[dict[str, object]]:
	with csv_file.open("r", newline="", encoding="utf-8-sig") as file:
		reader = csv.DictReader(file)
		fieldnames = set(reader.fieldnames or [])
		missing_columns = CSV_COLUMNS - fieldnames
		if missing_columns:
			raise ValueError(
				"CSV sem as colunas obrigatorias: " + ", ".join(sorted(missing_columns))
			)

		rows = []
		for line_number, row in enumerate(reader, start=2):
			try:
				rows.append(
					{
						"data": normalize_date(row["data"] or ""),
						"hora": (row["hora"] or "").strip(),
						"temperatura": float((row["temperatura"] or "").replace(",", ".")),
						"umidade": float((row["umidade"] or "").replace(",", ".")),
					}
				)
			except (TypeError, ValueError) as error:
				raise ValueError(f"erro na linha {line_number}: {error}") from error
	return rows


def upload_rows(rows: list[dict[str, object]], table: str, batch_size: int) -> None:
	if batch_size < 1:
		raise ValueError("--lote deve ser maior que zero")
	project_url, supabase_key = get_required_environment()
	headers = {
		"apikey": supabase_key,
		"Authorization": f"Bearer {supabase_key}",
		"Content-Type": "application/json",
		"Prefer": "return=minimal",
	}
	url = f"{project_url}/rest/v1/{table}"

	for start in range(0, len(rows), batch_size):
		batch = rows[start : start + batch_size]
		response = requests.post(url, json=batch, headers=headers, timeout=30)
		try:
			response.raise_for_status()
		except requests.HTTPError as error:
			raise RuntimeError(
				f"Supabase recusou o lote {start + 1}-{start + len(batch)}: "
				f"{response.text}"
			) from error
		print(f"Enviado lote {start + 1}-{start + len(batch)} de {len(rows)}")


def main() -> None:
	arguments = build_argument_parser().parse_args()
	if not arguments.arquivo.exists():
		raise SystemExit(f"arquivo nao encontrado: {arguments.arquivo}")
	rows = read_rows(arguments.arquivo)
	if not rows:
		print("Nenhum registro para enviar.")
		return
	upload_rows(rows, arguments.tabela, arguments.lote)
	print(f"Concluido: {len(rows)} registro(s) enviado(s) para {arguments.tabela}.")


if __name__ == "__main__":
	main()

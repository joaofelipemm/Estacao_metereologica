"""Sincronizacao incremental do CSV com o Supabase."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests

from csv_storage import read_csv_rows_since


DEFAULT_STATE_FILE = "ultima_sincronizacao.json"
DEFAULT_TABLE = "leituras"


def load_last_sync(state_file: Path) -> datetime | None:
	"""Le a data/hora do ultimo envio confirmado."""
	if not state_file.exists():
		return None
	try:
		value = json.loads(state_file.read_text(encoding="utf-8"))["ultima_sincronizacao"]
		return datetime.fromisoformat(value)
	except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
		raise ValueError(f"checkpoint invalido em {state_file}: {error}") from error


def save_last_sync(state_file: Path, last_sync: datetime) -> None:
	"""Salva o checkpoint somente depois de um envio bem-sucedido."""
	state_file.parent.mkdir(parents=True, exist_ok=True)
	state_file.write_text(
		json.dumps({"ultima_sincronizacao": last_sync.isoformat()}, indent=2),
		encoding="utf-8",
	)


def get_supabase_config() -> tuple[str, str]:
	project_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
	supabase_key = (
		os.getenv("SUPABASE_SERVICE_ROLE_KEY")
		or os.getenv("SUPABASE_ANON_KEY")
		or os.getenv("SUPABASE_KEY", "")
	).strip()
	if not project_url or not supabase_key:
		raise RuntimeError("configure SUPABASE_URL e SUPABASE_KEY no .env")
	if not project_url.startswith(("http://", "https://")):
		raise RuntimeError("SUPABASE_URL deve comecar com http:// ou https://")
	return project_url, supabase_key


def sync_csv_to_database(
	csv_file: Path,
	state_file: Path,
	table: str = DEFAULT_TABLE,
	batch_size: int = 100,
) -> int:
	"""Envia somente dados novos e atualiza o checkpoint ao final."""
	if batch_size < 1:
		raise ValueError("batch_size deve ser maior que zero")
	if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
		raise ValueError("nome de tabela invalido")

	last_sync = load_last_sync(state_file)
	rows = read_csv_rows_since(csv_file, last_sync)
	if not rows:
		return 0
	project_url, supabase_key = get_supabase_config()
	headers = {
		"apikey": supabase_key,
		"Authorization": f"Bearer {supabase_key}",
		"Content-Type": "application/json",
		"Prefer": "return=minimal",
	}
	url = f"{project_url}/rest/v1/{table}"

	for start in range(0, len(rows), batch_size):
		batch = rows[start : start + batch_size]
		try:
			response = requests.post(
				url,
				json=[payload for _, payload in batch],
				headers=headers,
				timeout=30,
			)
			response.raise_for_status()
		except requests.RequestException as error:
			raise RuntimeError(
				f"falha no lote {start + 1}-{start + len(batch)} do Supabase: {error}"
			) from error

	save_last_sync(state_file, rows[-1][0])
	return len(rows)
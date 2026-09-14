"""Leitura de uma porta serial e armazenamento das leituras em CSV e PostgreSQL."""

import argparse
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import serial
from serial.tools import list_ports

try:
	import psycopg2
except ImportError:  # pragma: no cover
	psycopg2 = None

try:
	import requests
except ImportError:  # pragma: no cover
	requests = None

try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover
	def load_dotenv(*_args, **_kwargs):
		return False


load_dotenv()

DEFAULT_OUTPUT_DIRECTORY = Path(r"G:\Meu Drive\Estacao_prototype")
DEFAULT_OUTPUT_FILE = "leituras.csv"
DEFAULT_BAUDRATE = 9600
CSV_HEADER = ["data", "hora", "temperatura", "umidade"]
DB_TABLE_NAME = "leituras"


def build_argument_parser() -> argparse.ArgumentParser:
	"""Cria o parser com as configuracoes da porta serial e do arquivo CSV."""
	parser = argparse.ArgumentParser(
		description="Le a porta serial e salva cada linha recebida em um CSV."
	)
	parser.add_argument(
		"--porta",
		default=None,
		help="Porta serial a ser lida; se omitida, detecta uma porta disponivel.",
	)
	parser.add_argument(
		"--baudrate",
		type=int,
		default=DEFAULT_BAUDRATE,
		help=f"Velocidade da porta (padrao: {DEFAULT_BAUDRATE}).",
	)
	parser.add_argument(
		"--arquivo",
		type=Path,
		default=DEFAULT_OUTPUT_DIRECTORY / DEFAULT_OUTPUT_FILE,
		help="Caminho do CSV de saida.",
	)
	parser.add_argument(
		"--timeout",
		type=float,
		default=1.0,
		help="Tempo, em segundos, para aguardar uma linha (padrao: 1).",
	)
	parser.add_argument(
		"--once",
		action="store_true",
		help="Le apenas uma linha; util para teste da conexao.",
	)
	return parser


def normalize_database_dsn(dsn: str) -> str:
	"""Escapa caracteres especiais na senha/usuario da DSN do PostgreSQL."""
	dsn = dsn.strip()
	if not dsn.startswith(("postgresql://", "postgres://")):
		return dsn

	parsed = urlsplit(dsn)
	if not parsed.username or parsed.password is None:
		return dsn

	encoded_user = quote(parsed.username, safe="")
	encoded_password = quote(parsed.password, safe="")
	netloc = f"{encoded_user}:{encoded_password}@{parsed.hostname}"
	if parsed.port:
		netloc = f"{netloc}:{parsed.port}"
	return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def get_database_dsn() -> str | None:
	"""Retorna a string de conexao do PostgreSQL quando houver uma DSN valida."""
	dsn = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
	if not dsn:
		return None
	dsn = dsn.strip()
	if dsn.startswith(("http://", "https://")):
		return None
	return normalize_database_dsn(dsn)


def get_supabase_project_url() -> str | None:
	"""Retorna a URL do projeto Supabase quando configurada no ambiente."""
	value = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_DB_URL")
	if not value:
		return None
	value = value.strip()
	if value.startswith(("http://", "https://")):
		return value.rstrip("/")
	return None


def get_supabase_key() -> str | None:
	"""Retorna a chave public/anon do Supabase configurada no ambiente."""
	for key_name in ("SUPABASE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
		value = os.getenv(key_name)
		if value and value.strip():
			return value.strip()
	return None


def ensure_database_table() -> None:
	"""Cria a tabela do banco se ela ainda nao existir."""
	dsn = get_database_dsn()
	if not dsn or psycopg2 is None:
		return

	try:
		with psycopg2.connect(dsn) as conn:
			with conn.cursor() as cursor:
				cursor.execute(
					f"""
					CREATE TABLE IF NOT EXISTS {DB_TABLE_NAME} (
						id SERIAL PRIMARY KEY,
						data DATE NOT NULL,
						hora TIME NOT NULL,
						temperatura NUMERIC(5,2) NOT NULL,
						umidade NUMERIC(5,2) NOT NULL,
						created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
					);
					"""
				)
				cursor.execute(
					f"""
					CREATE INDEX IF NOT EXISTS idx_{DB_TABLE_NAME}_data_hora
					ON {DB_TABLE_NAME} (data, hora);
					"""
				)
	except Exception as error:  # pragma: no cover - falha de infra nao deve quebrar a leitura
		print(f"Banco de dados indisponivel; gravando apenas localmente. ({error})")


def find_available_port() -> str:
	"""Seleciona a unica porta serial disponivel ou informa como escolher uma."""
	available_ports = list(list_ports.comports())
	if len(available_ports) == 1:
		return available_ports[0].device
	if not available_ports:
		raise serial.SerialException("nenhuma porta serial foi encontrada")

	port_names = ", ".join(port.device for port in available_ports)
	raise serial.SerialException(
		f"mais de uma porta foi encontrada ({port_names}); use --porta"
	)


def ensure_csv_header(output_file: Path) -> None:
	"""Cria o CSV ou separa um arquivo antigo antes de aplicar o novo formato."""
	output_file.parent.mkdir(parents=True, exist_ok=True)
	if output_file.exists() and output_file.stat().st_size > 0:
		with output_file.open("r", newline="", encoding="utf-8") as csv_file:
			current_header = next(csv.reader(csv_file), [])
		if current_header == CSV_HEADER:
			return

		backup_file = output_file.with_name(f"{output_file.stem}_antigo.csv")
		output_file.replace(backup_file)

	with output_file.open("a", newline="", encoding="utf-8") as csv_file:
		writer = csv.writer(csv_file)
		writer.writerow(CSV_HEADER)


def parse_sensor_reading(data: str) -> tuple[str, str]:
	"""Extrai temperatura e umidade de uma linha enviada pelo sensor."""
	normalized_data = data.strip().lower().replace(";", ",")
	named_values = re.findall(
		r"(?:temperatura|temp)\s*[:=]\s*(-?\d+(?:[.,]\d+)?)|"
		r"(?:umidade|humidity|hum)\s*[:=]\s*(\d+(?:[.,]\d+)?)",
		normalized_data,
	)
	if named_values:
		temperature = next((temperature for temperature, _ in named_values if temperature), None)
		humidity = next((humidity for _, humidity in named_values if humidity), None)
	else:
		values = [value.strip() for value in normalized_data.split(",")]
		if len(values) != 2:
			raise ValueError("use temperatura,umidade ou temperatura=valor,umidade=valor")
		temperature, humidity = values

	if temperature is None or humidity is None:
		raise ValueError("a leitura precisa conter temperatura e umidade")

	return temperature.replace(",", "."), humidity.replace(",", ".")


def insert_reading_to_database(current_time: datetime, temperature: str, humidity: str) -> None:
	"""Insere a leitura no PostgreSQL via DSN ou no Supabase via REST API."""
	dsn = get_database_dsn()
	if dsn and psycopg2 is not None:
		try:
			with psycopg2.connect(dsn) as conn:
				with conn.cursor() as cursor:
					cursor.execute(
						f"INSERT INTO {DB_TABLE_NAME} (data, hora, temperatura, umidade) VALUES (%s, %s, %s, %s);",
						(
							current_time.strftime("%Y-%m-%d"),
							current_time.strftime("%H:%M:%S"),
							float(temperature.replace(",", ".")),
							float(humidity.replace(",", ".")),
						),
					)
		except Exception as error:
			print(f"Falha ao gravar no banco: {error}")
		return

	supabase_url = get_supabase_project_url()
	supabase_key = get_supabase_key()
	if not supabase_url or not supabase_key or requests is None:
		return

	payload = [{
		"data": current_time.strftime("%Y-%m-%d"),
		"hora": current_time.strftime("%H:%M:%S"),
		"temperatura": float(temperature.replace(",", ".")),
		"umidade": float(humidity.replace(",", ".")),
	}]
	headers = {
		"apikey": supabase_key,
		"Authorization": f"Bearer {supabase_key}",
		"Content-Type": "application/json",
		"Accept": "application/json",
	}
	url = f"{supabase_url}/rest/v1/{DB_TABLE_NAME}"

	try:
		response = requests.post(url, json=payload, headers=headers, timeout=10)
		response.raise_for_status()
	except Exception as error:
		print(f"Falha ao gravar no Supabase via REST: {error}")


def append_reading(output_file: Path, data: str) -> None:
	"""Adiciona temperatura e umidade ao CSV com data e hora locais formatadas."""
	temperature, humidity = parse_sensor_reading(data)
	current_time = datetime.now()
	with output_file.open("a", newline="", encoding="utf-8") as csv_file:
		writer = csv.writer(csv_file)
		writer.writerow(
			[
				current_time.strftime("%d/%m/%Y"),
				current_time.strftime("%H:%M:%S"),
				temperature,
				humidity,
			]
		)
	insert_reading_to_database(current_time, temperature, humidity)


def read_serial_data(
	port_name: str,
	baudrate: int,
	timeout: float,
	output_file: Path,
	read_once: bool = False,
) -> None:
	"""Le linhas da porta serial e grava cada linha recebida no arquivo CSV."""
	ensure_csv_header(output_file)
	ensure_database_table()

	with serial.Serial(port_name, baudrate=baudrate, timeout=timeout) as serial_port:
		print(f"Lendo {port_name} a {baudrate} baud. CSV: {output_file}")
		while True:
			received_data = serial_port.readline().decode("utf-8", errors="replace").strip()
			if received_data:
				try:
					append_reading(output_file, received_data)
					temperature, humidity = parse_sensor_reading(received_data)
					print(f"Leitura gravada: temperatura={temperature}, umidade={humidity}")
				except ValueError as error:
					print(f"Leitura ignorada ({error}): {received_data}")

			if read_once:
				break


def main() -> None:
	"""Le os argumentos, abre a serial e inicia a gravacao das leituras."""
	parser = build_argument_parser()
	arguments = parser.parse_args()
	port_name = arguments.porta

	try:
		if port_name is None:
			port_name = find_available_port()

		read_serial_data(
			port_name=port_name,
			baudrate=arguments.baudrate,
			timeout=arguments.timeout,
			output_file=arguments.arquivo,
			read_once=arguments.once,
		)
	except serial.SerialException as error:
		parser.error(f"nao foi possivel acessar {port_name or 'a porta serial'}: {error}")
	except KeyboardInterrupt:
		print("\nLeitura interrompida pelo usuario.")


if __name__ == "__main__":
	main()

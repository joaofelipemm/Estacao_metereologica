"""Executa a captura serial, grava o CSV e sincroniza o Supabase."""

import argparse
import time
from pathlib import Path

import serial
from dotenv import load_dotenv

from csv_storage import write_reading_to_csv
from database_sync import DEFAULT_STATE_FILE, sync_csv_to_database
from serial_reader import find_available_port, read_serial_messages


DEFAULT_OUTPUT_DIRECTORY = Path(r"G:\Meu Drive\Estacao_prototype")
DEFAULT_OUTPUT_FILE = "leituras.csv"
DEFAULT_BAUDRATE = 9600
DEFAULT_DATABASE_INTERVAL = 60.0


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Le a porta serial, grava o CSV e atualiza o Supabase."
	)
	parser.add_argument("--porta", help="Porta serial; se omitida, detecta uma disponivel.")
	parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
	parser.add_argument(
		"--arquivo",
		type=Path,
		default=DEFAULT_OUTPUT_DIRECTORY / DEFAULT_OUTPUT_FILE,
		help="Caminho do CSV de saida.",
	)
	parser.add_argument(
		"--estado",
		type=Path,
		default=DEFAULT_OUTPUT_DIRECTORY / DEFAULT_STATE_FILE,
		help="Arquivo que guarda a ultima data/hora enviada ao banco.",
	)
	parser.add_argument("--timeout", type=float, default=1.0)
	parser.add_argument("--lote", type=int, default=100)
	parser.add_argument(
		"--intervalo-banco",
		type=float,
		default=DEFAULT_DATABASE_INTERVAL,
		help="Intervalo minimo entre atualizacoes do banco, em segundos (padrao: 60).",
	)
	parser.add_argument("--once", action="store_true", help="Le apenas uma mensagem.")
	parser.add_argument(
		"--sem-banco",
		action="store_true",
		help="Grava no CSV sem tentar sincronizar com o Supabase.",
	)
	return parser


def handle_sensor_message(
	message: str,
	output_file: Path,
	state_file: Path,
	batch_size: int,
	use_database: bool,
	database_interval: float,
	last_database_update: float,
) -> float:
	"""Grava toda mensagem e sincroniza o banco no intervalo configurado."""
	try:
		reading_time = write_reading_to_csv(output_file, message)
		print(f"Leitura gravada: {reading_time:%d/%m/%Y %H:%M:%S}")
		current_clock = time.monotonic()
		if use_database and current_clock - last_database_update >= database_interval:
			sent_count = sync_csv_to_database(output_file, state_file, batch_size=batch_size)
			if sent_count:
				print(f"{sent_count} leitura(s) sincronizada(s) com o Supabase.")
			return current_clock
	except (RuntimeError, ValueError) as error:
		print(f"Leitura processada localmente, mas nao sincronizada: {error}")
	return last_database_update


def main() -> None:
	load_dotenv()
	parser = build_argument_parser()
	arguments = parser.parse_args()
	port_name = arguments.porta
	last_database_update = 0.0
	if arguments.intervalo_banco <= 0:
		parser.error("--intervalo-banco deve ser maior que zero")

	def on_message(message: str) -> None:
		nonlocal last_database_update
		last_database_update = handle_sensor_message(
			message,
			arguments.arquivo,
			arguments.estado,
			arguments.lote,
			not arguments.sem_banco,
			arguments.intervalo_banco,
			last_database_update,
		)

	try:
		port_name = port_name or find_available_port()
		read_serial_messages(
			port_name=port_name,
			baudrate=arguments.baudrate,
			timeout=arguments.timeout,
			read_once=arguments.once,
			on_message=on_message,
		)
	except serial.SerialException as error:
		parser.error(f"nao foi possivel acessar {port_name or 'a porta serial'}: {error}")
	except KeyboardInterrupt:
		print("\nLeitura interrompida pelo usuario.")


if __name__ == "__main__":
	main()
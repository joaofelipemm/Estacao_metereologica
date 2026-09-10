"""Leitura de uma porta serial e armazenamento das leituras em CSV."""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports


DEFAULT_OUTPUT_DIRECTORY = Path(r"G:\Meu Drive\Estacao_prototype")
DEFAULT_OUTPUT_FILE = "leituras.csv"
DEFAULT_BAUDRATE = 9600
CSV_HEADER = ["data", "hora", "temperatura", "umidade"]


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


def read_serial_data(
	port_name: str,
	baudrate: int,
	timeout: float,
	output_file: Path,
	read_once: bool = False,
) -> None:
	"""Le linhas da porta serial e grava cada linha recebida no arquivo CSV."""
	ensure_csv_header(output_file)

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

"""Funcoes para interpretar e armazenar leituras no CSV."""

import csv
import re
from datetime import datetime
from pathlib import Path


CSV_HEADER = ["data", "hora", "temperatura", "umidade"]
CSV_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def parse_sensor_reading(data: str) -> tuple[str, str]:
	"""Extrai temperatura e umidade de uma mensagem do sensor."""
	normalized_data = data.strip().lower().replace(";", ",")
	named_values = re.findall(
		r"(?:temperatura|temp)\s*[:=]\s*(-?\d+(?:[.,]\d+)?)|"
		r"(?:umidade|humidity|hum)\s*[:=]\s*(\d+(?:[.,]\d+)?)",
		normalized_data,
	)
	if named_values:
		temperature = next((value for value, _ in named_values if value), None)
		humidity = next((value for _, value in named_values if value), None)
	else:
		values = [value.strip() for value in normalized_data.split(",")]
		if len(values) != 2:
			raise ValueError("use temperatura,umidade ou temperatura=valor,umidade=valor")
		temperature, humidity = values

	if temperature is None or humidity is None:
		raise ValueError("a leitura precisa conter temperatura e umidade")
	return temperature.replace(",", "."), humidity.replace(",", ".")


def ensure_csv_header(output_file: Path) -> None:
	"""Cria o CSV e garante que ele use o cabecalho atual."""
	output_file.parent.mkdir(parents=True, exist_ok=True)
	if output_file.exists() and output_file.stat().st_size > 0:
		with output_file.open("r", newline="", encoding="utf-8") as csv_file:
			if next(csv.reader(csv_file), []) == CSV_HEADER:
				return
		backup_file = output_file.with_name(f"{output_file.stem}_antigo.csv")
		output_file.replace(backup_file)

	with output_file.open("a", newline="", encoding="utf-8") as csv_file:
		csv.writer(csv_file).writerow(CSV_HEADER)


def write_reading_to_csv(output_file: Path, data: str) -> datetime:
	"""Valida uma mensagem, grava a leitura e retorna sua data/hora."""
	temperature, humidity = parse_sensor_reading(data)
	reading_time = datetime.now().replace(microsecond=0)
	ensure_csv_header(output_file)
	with output_file.open("a", newline="", encoding="utf-8") as csv_file:
		csv.writer(csv_file).writerow(
			[
				reading_time.strftime("%d/%m/%Y"),
				reading_time.strftime("%H:%M:%S"),
				temperature,
				humidity,
			]
		)
	return reading_time


def read_csv_rows_since(
	csv_file: Path, last_sync: datetime | None
) -> list[tuple[datetime, dict[str, object]]]:
	"""Retorna leituras do CSV posteriores ao ultimo checkpoint."""
	rows = []
	with csv_file.open("r", newline="", encoding="utf-8-sig") as file:
		for line_number, row in enumerate(csv.DictReader(file), start=2):
			try:
				reading_time = datetime.strptime(
					f"{row['data']} {row['hora']}", CSV_DATETIME_FORMAT
				)
				if last_sync is not None and reading_time <= last_sync:
					continue
				payload = {
					"data": reading_time.strftime("%Y-%m-%d"),
					"hora": reading_time.strftime("%H:%M:%S"),
					"temperatura": float((row["temperatura"] or "").replace(",", ".")),
					"umidade": float((row["umidade"] or "").replace(",", ".")),
				}
				rows.append((reading_time, payload))
			except (KeyError, TypeError, ValueError) as error:
				raise ValueError(f"erro na linha {line_number}: {error}") from error
	return rows
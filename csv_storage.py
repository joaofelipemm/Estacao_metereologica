"""Funcoes para interpretar e armazenar leituras no CSV."""

import csv
from datetime import datetime
from pathlib import Path


CSV_HEADER = ["data", "hora", "chuva_acumulada", "taxa_chuva", "temperatura", "umidade"]
CSV_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def parse_sensor_reading(data: str) -> tuple[str, str, str, str, str, str]:
	"""Extrai a leitura completa do protocolo do sensor: dia, mes, ano, hora, minuto, chuva, temperatura e umidade."""
	normalized_data = data.strip().replace(";", ",").replace(" ", "")
	values = [value.strip() for value in normalized_data.split(",")]
	if len(values) != 9:
		raise ValueError(
			"leitura invalida: esperado dia,mes,ano,hora,minuto,chuva_acumulada,taxa_chuva,temperatura,umidade"
		)

	day, month, year, hour, minute, rain_accumulated, rain_rate, temperature, humidity = values
	if not all(part for part in [day, month, year, hour, minute, rain_accumulated, rain_rate, temperature, humidity]):
		raise ValueError("a leitura contem valores vazios")

	reading_date = datetime.strptime(
		f"{int(day):02d}/{int(month):02d}/{int(year):04d}", "%d/%m/%Y"
	).strftime("%d/%m/%Y")
	reading_time = datetime.strptime(
		f"{int(hour):02d}:{int(minute):02d}:00", "%H:%M:%S"
	).strftime("%H:%M:%S")

	return (
		reading_date,
		reading_time,
		rain_accumulated.replace(",", "."),
		rain_rate.replace(",", "."),
		temperature.replace(",", "."),
		humidity.replace(",", "."),
	)


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
	reading_date, reading_time, rain_accumulated, rain_rate, temperature, humidity = parse_sensor_reading(data)
	reading_datetime = datetime.strptime(f"{reading_date} {reading_time}", "%d/%m/%Y %H:%M:%S")
	ensure_csv_header(output_file)
	with output_file.open("a", newline="", encoding="utf-8") as csv_file:
		csv.writer(csv_file).writerow(
			[
				reading_date,
				reading_time,
				rain_accumulated,
				rain_rate,
				temperature,
				humidity,
			]
		)
	return reading_datetime


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
					"chuva_acumulada": float((row["chuva_acumulada"] or "").replace(",", ".")),
					"taxa_chuva": float((row["taxa_chuva"] or "").replace(",", ".")),
					"temperatura": float((row["temperatura"] or "").replace(",", ".")),
					"umidade": float((row["umidade"] or "").replace(",", ".")),
				}
				rows.append((reading_time, payload))
			except (KeyError, TypeError, ValueError) as error:
				raise ValueError(f"erro na linha {line_number}: {error}") from error
	return rows
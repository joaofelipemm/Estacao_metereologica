from datetime import datetime

from csv_storage import parse_sensor_reading, write_reading_to_csv


def test_parse_sensor_reading_new_format():
    payload = "16,9,2026,20,41,0.6,0.0,21.9,85.0"

    assert parse_sensor_reading(payload) == (
        "16/09/2026",
        "20:41:00",
        "0.6",
        "0.0",
        "21.9",
        "85.0",
    )


def test_write_reading_to_csv_uses_new_columns(tmp_path):
    csv_file = tmp_path / "leituras.csv"

    reading_time = write_reading_to_csv(csv_file, "16,9,2026,20,41,0.6,0.0,21.9,85.0")

    assert reading_time == datetime.strptime("16/09/2026 20:41:00", "%d/%m/%Y %H:%M:%S")
    lines = csv_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "data,hora,chuva_acumulada,taxa_chuva,temperatura,umidade"
    assert lines[1] == "16/09/2026,20:41:00,0.6,0.0,21.9,85.0"

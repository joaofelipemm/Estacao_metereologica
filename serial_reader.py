"""Funcoes responsaveis pela porta serial."""

from collections.abc import Callable

import serial
from serial.tools import list_ports


def find_available_port() -> str:
	"""Retorna a unica porta disponivel ou informa como escolher uma."""
	available_ports = list(list_ports.comports())
	if len(available_ports) == 1:
		return available_ports[0].device
	if not available_ports:
		raise serial.SerialException("nenhuma porta serial foi encontrada")

	port_names = ", ".join(port.device for port in available_ports)
	raise serial.SerialException(
		f"mais de uma porta foi encontrada ({port_names}); use --porta"
	)


def read_serial_messages(
	port_name: str,
	baudrate: int,
	timeout: float,
	on_message: Callable[[str], None],
	read_once: bool = False,
) -> None:
	"""Le mensagens da porta e envia cada linha para o callback."""
	with serial.Serial(port_name, baudrate=baudrate, timeout=timeout) as serial_port:
		print(f"Lendo {port_name} a {baudrate} baud.")
		while True:
			received_data = serial_port.readline().decode("utf-8", errors="replace").strip()
			if received_data:
				on_message(received_data)
			if read_once:
				break
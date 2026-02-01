import queue
import threading
import time
from typing import Callable, Optional, Tuple

import serial


class SerialWorker:
    def __init__(
        self,
        on_line: Callable[[str], None],
        on_status: Callable[[str], None],
    ) -> None:
        self.on_line = on_line
        self.on_status = on_status
        self._serial: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._out_queue: queue.Queue[str] = queue.Queue()

    def connect(self, port: str, baudrate: int, timeout: float = 0.1) -> None:
        self.disconnect()
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.on_status(f"Serial connected: {port}")

    def disconnect(self) -> None:
        self._running.clear()
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception as exc:  # pragma: no cover - best effort
                self.on_status(f"Serial close error: {exc}")
        self._serial = None

    def send(self, text: str) -> None:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Serial port is not connected.")
        self._out_queue.put(text)

    def _run(self) -> None:
        if not self._serial:
            return
        buffer = b""
        while self._running.is_set():
            self._flush_outgoing()
            try:
                data = self._serial.read(256)
            except Exception as exc:
                self.on_status(f"Serial read error: {exc}")
                time.sleep(0.2)
                continue

            if data:
                buffer += data
                line, buffer = self._extract_line(buffer)
                while line is not None:
                    if line:
                        self.on_line(line)
                    line, buffer = self._extract_line(buffer)
            else:
                time.sleep(0.01)

    def _flush_outgoing(self) -> None:
        if not self._serial:
            return
        while True:
            try:
                outgoing = self._out_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._serial.write(outgoing.encode("ascii", errors="replace"))
            except Exception as exc:
                self.on_status(f"Serial write error: {exc}")

    @staticmethod
    def _extract_line(buffer: bytes) -> Tuple[Optional[str], bytes]:
        for sep in (b"\n", b"\r"):
            index = buffer.find(sep)
            if index != -1:
                raw_line = buffer[:index]
                remainder = buffer[index + 1 :]
                while remainder.startswith(b"\n") or remainder.startswith(b"\r"):
                    remainder = remainder[1:]
                line = raw_line.decode("ascii", errors="replace").strip()
                return line, remainder
        return None, buffer
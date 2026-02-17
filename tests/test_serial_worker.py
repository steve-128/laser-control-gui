import queue
import threading
import time
import unittest

import serial_worker


class FakeSerial:
    def __init__(self, port: str, baudrate: int, timeout: float = 0.1) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self._read_queue: queue.Queue[bytes] = queue.Queue()
        self.writes: list[bytes] = []

    def read(self, size: int) -> bytes:
        try:
            return self._read_queue.get_nowait()
        except queue.Empty:
            return b""

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def close(self) -> None:
        self.is_open = False

    def push_read(self, data: bytes) -> None:
        self._read_queue.put(data)


class SerialWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines: list[str] = []
        self.status: list[str] = []
        self.worker = serial_worker.SerialWorker(self.lines.append, self.status.append)

        self._original_serial = serial_worker.serial.Serial
        serial_worker.serial.Serial = FakeSerial  # type: ignore[assignment]

    def tearDown(self) -> None:
        self.worker.disconnect()
        serial_worker.serial.Serial = self._original_serial  # type: ignore[assignment]

    def test_send_writes_to_serial(self) -> None:
        self.worker.connect("COM1", 9600)
        self.worker.send("opmode?\r\n")
        time.sleep(0.05)

        fake: FakeSerial = self.worker._serial  # type: ignore[assignment]
        self.assertTrue(fake.writes)
        self.assertEqual(fake.writes[-1], b"opmode?\r\n")

    def test_receives_lines(self) -> None:
        self.worker.connect("COM2", 115200)
        fake: FakeSerial = self.worker._serial  # type: ignore[assignment]
        fake.push_read(b"opmode=off\r\n")
        time.sleep(0.05)

        self.assertIn("opmode=off", self.lines)

    def test_extract_line(self) -> None:
        line, remainder = serial_worker.SerialWorker._extract_line(b"hello\r\nworld")
        self.assertEqual(line, "hello")
        self.assertEqual(remainder, b"world")


if __name__ == "__main__":
    unittest.main()

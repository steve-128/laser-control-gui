import queue
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

try:
    import serial
    import serial.tools.list_ports
except Exception:  # pragma: no cover - handled at runtime
    serial = None

from protocol import parse_key_value
from serial_worker import SerialWorker


class LaserGuiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Laser Control GUI")
        self.root.geometry("1200x750")

        self.incoming_queue: queue.Queue = queue.Queue()
        self.worker = SerialWorker(self._enqueue_line, self._enqueue_status)

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="9600")
        self.append_crlf_var = tk.BooleanVar(value=True)

        self.state_vars = {
            "opmode": tk.StringVar(value="unknown"),
            "last_response": tk.StringVar(value="-"),
            "status": tk.StringVar(value="disconnected"),
        }

        self._build_ui()
        self._refresh_ports()
        self._poll_incoming()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.BOTH, expand=True)

        sections_frame = ttk.Frame(top_frame)
        sections_frame.pack(fill=tk.BOTH, expand=True)

        energy_frame = self._build_energy_control(sections_frame)
        trigger_frame = self._build_trigger_control(sections_frame)
        counter_frame = self._build_counter(sections_frame)

        energy_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        trigger_frame.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        counter_frame.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")

        tube_frame = self._build_tube(sections_frame)
        com_frame = self._build_coms(sections_frame)
        status_frame = self._build_status(sections_frame)

        tube_frame.grid(row=1, column=2, padx=6, pady=6, sticky="nsew")
        com_frame.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        status_frame.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

        for col in range(3):
            sections_frame.columnconfigure(col, weight=1)
        sections_frame.rowconfigure(0, weight=1)
        sections_frame.rowconfigure(1, weight=1)

        info_frame = ttk.LabelFrame(top_frame, text="Info / Interlock / Warning List")
        info_frame.pack(fill=tk.X, padx=6, pady=6)
        self.info_text = ScrolledText(info_frame, height=4, state="disabled")
        self.info_text.pack(fill=tk.X, padx=6, pady=6)

        manual_frame = ttk.LabelFrame(top_frame, text="Manual Send / Receive")
        manual_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        manual_row = ttk.Frame(manual_frame)
        manual_row.pack(fill=tk.X, padx=6, pady=6)
        self.manual_entry = ttk.Entry(manual_row)
        self.manual_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.manual_entry.bind("<Return>", self._on_send)
        ttk.Button(manual_row, text="Send", command=self._on_send).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(
            manual_row,
            text="Append CRLF",
            variable=self.append_crlf_var,
        ).pack(side=tk.LEFT)

        self.log_text = ScrolledText(manual_frame, height=12, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar, text="Status:").pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(status_bar, textvariable=self.state_vars["status"]).pack(side=tk.LEFT)

    def _build_energy_control(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Energy Control")
        self._labeled_combobox(frame, "Mode", ["HV PGR", "HV PRF", "HV PRR"], "HV PGR", row=0)
        self._labeled_entry(frame, "HV (kV)", "", row=1)
        self._labeled_entry(frame, "Energy (mJ)", "", row=2)
        self._labeled_entry(frame, "Power (W)", "", row=3)
        self._labeled_entry(frame, "Sigma (%)", "", row=4)
        return frame

    def _build_trigger_control(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Trigger Control")
        self._labeled_combobox(frame, "Trigger", ["INT", "EXT", "GATE"], "INT", row=0)
        self._labeled_entry(frame, "Rep. Rate (Hz)", "", row=1)
        self._labeled_entry(frame, "Counts", "", row=2)
        self._labeled_entry(frame, "Burst Pulses", "", row=3)
        self._labeled_entry(frame, "Burst Pause (ms)", "", row=4)
        self._labeled_entry(frame, "Sequence Bursts", "", row=5)
        self._labeled_entry(frame, "Sequence Pause (ms)", "", row=6)
        self._labeled_combobox(frame, "High Energy Mode", ["ON", "OFF"], "ON", row=7)
        return frame

    def _build_counter(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Counter")
        self._labeled_entry(frame, "Total", "", row=0)
        self._labeled_entry(frame, "User", "", row=1)
        self._labeled_entry(frame, "RF Counter", "", row=2)
        return frame

    def _build_tube(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Tube")
        self._labeled_entry(frame, "Temperature (C)", "", row=0)
        self._labeled_entry(frame, "Pressure (mbar)", "", row=1)
        self._labeled_entry(frame, "Manifold Pressure (mbar)", "", row=2)
        return frame

    def _build_coms(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Laser COM Ports / Protocol")

        ttk.Label(frame, text="Port").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, state="readonly", width=18)
        self.port_combo.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(frame, text="Refresh", command=self._refresh_ports).grid(
            row=0, column=2, sticky="w", padx=6, pady=4
        )

        ttk.Label(frame, text="Baud").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.baud_var, width=10).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Button(frame, text="Connect", command=self._on_connect).grid(
            row=2, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Button(frame, text="Disconnect", command=self._on_disconnect).grid(
            row=2, column=1, sticky="w", padx=6, pady=6
        )
        return frame

    def _build_status(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Device Status")
        ttk.Label(frame, text="OP Mode").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(frame, textvariable=self.state_vars["opmode"]).grid(
            row=0, column=1, sticky="w", padx=6, pady=4
        )
        ttk.Label(frame, text="Last Response").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(frame, textvariable=self.state_vars["last_response"]).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )
        return frame

    def _labeled_entry(self, parent: ttk.Frame, label: str, default: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        entry = ttk.Entry(parent, width=12)
        entry.grid(row=row, column=1, sticky="w", padx=6, pady=4)
        if default:
            entry.insert(0, default)

    def _labeled_combobox(
        self,
        parent: ttk.Frame,
        label: str,
        values: list,
        default: str,
        row: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        combo = ttk.Combobox(parent, values=values, state="readonly", width=10)
        combo.grid(row=row, column=1, sticky="w", padx=6, pady=4)
        if default in values:
            combo.set(default)
        elif values:
            combo.set(values[0])

    def _refresh_ports(self) -> None:
        if serial is None:
            ports = []
        else:
            ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _on_connect(self) -> None:
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Connect", "Select a COM port first.")
            return
        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showwarning("Connect", "Baud rate must be a number.")
            return
        try:
            self.worker.connect(port, baud)
            self.state_vars["status"].set(f"connected to {port}")
            self._append_info(f"Connected to {port} @ {baud}")
        except Exception as exc:
            messagebox.showerror("Connect failed", str(exc))

    def _on_disconnect(self) -> None:
        self.worker.disconnect()
        self.state_vars["status"].set("disconnected")
        self._append_info("Disconnected")

    def _on_send(self, event=None) -> None:
        text = self.manual_entry.get().strip()
        if not text:
            return
        outgoing = text + ("\r\n" if self.append_crlf_var.get() else "")
        try:
            self.worker.send(outgoing)
            self._append_log(f">> {text}")
        except Exception as exc:
            messagebox.showerror("Send failed", str(exc))
        self.manual_entry.delete(0, tk.END)

    def _poll_incoming(self) -> None:
        while True:
            try:
                item_type, payload = self.incoming_queue.get_nowait()
            except queue.Empty:
                break
            if item_type == "line":
                self._handle_line(payload)
            elif item_type == "status":
                self._append_info(payload)
        self.root.after(100, self._poll_incoming)

    def _handle_line(self, line: str) -> None:
        self._append_log(f"<< {line}")
        self.state_vars["last_response"].set(line)
        parsed = parse_key_value(line)
        if parsed:
            key, value = parsed
            if key == "opmode":
                self.state_vars["opmode"].set(value)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)

    def _append_info(self, message: str) -> None:
        self.info_text.configure(state="normal")
        self.info_text.insert(tk.END, message + "\n")
        self.info_text.configure(state="disabled")
        self.info_text.see(tk.END)

    def _enqueue_line(self, line: str) -> None:
        self.incoming_queue.put(("line", line))

    def _enqueue_status(self, message: str) -> None:
        self.incoming_queue.put(("status", message))

    def on_close(self) -> None:
        self._on_disconnect()
        self.root.destroy()

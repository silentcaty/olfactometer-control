"""Reusable serial controller for the 12-channel olfactometer."""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


# Command bytes confirmed with the supplied command table and hardware test.
OPEN_COMMANDS = {
    1: 0x01,
    2: 0x02,
    3: 0x03,
    4: 0x04,
    5: 0x05,
    6: 0x06,
    7: 0x07,
    8: 0x08,
    9: 0x09,
    10: 0x10,
    11: 0x11,
    12: 0x12,
}

CLOSE_COMMANDS = {
    1: 0x21,
    2: 0x22,
    3: 0x23,
    4: 0x24,
    5: 0x25,
    6: 0x26,
    7: 0x27,
    8: 0x28,
    9: 0x29,
    10: 0x30,
    11: 0x31,
    12: 0x32,
}

ALL_CLOSE = 0x6F
TARGET_VID = 0x1A86
TARGET_PID = 0x55D3


@dataclass
class EventRecord:
    """One command-write record for the CSV log."""

    event: str
    channel: Optional[int]
    command_hex: str
    elapsed_s: float
    write_duration_ms: float
    executed: bool


def list_serial_ports() -> None:
    """Print serial ports visible to pySerial."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("缺少pySerial：python3 -m pip install pyserial") from exc

    ports = list(list_ports.comports())
    if not ports:
        print("没有发现串口。")
        return

    for port in ports:
        vid_pid = (
            f"{port.vid:04X}:{port.pid:04X}"
            if port.vid is not None and port.pid is not None
            else "unknown"
        )
        marker = (
            "  <-- 嗅觉仪候选"
            if port.vid == TARGET_VID and port.pid == TARGET_PID
            else ""
        )
        print(f"{port.device} | {port.description} | VID:PID={vid_pid}{marker}")


def find_olfactometer_port() -> str:
    """Find the single serial port matching the tested USB VID/PID."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("缺少pySerial：python3 -m pip install pyserial") from exc

    matches = [
        port.device
        for port in list_ports.comports()
        if port.vid == TARGET_VID and port.pid == TARGET_PID
    ]
    if not matches:
        raise RuntimeError("未发现VID:PID=1A86:55D3的嗅觉仪串口。")
    if len(matches) > 1:
        raise RuntimeError(f"发现多个候选串口，请手动指定：{', '.join(matches)}")
    return matches[0]


class Olfactometer:
    """Control the tested olfactometer with one-byte binary commands.

    Use as a context manager so that normal exit and errors both trigger an
    all-close command. ``execute=False`` is a dry run and never opens a port.
    """

    def __init__(
        self,
        *,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        break_interval_s: float = 0.020,
        execute: bool = False,
    ) -> None:
        if baud_rate <= 0:
            raise ValueError("baud_rate必须大于0。")
        if break_interval_s < 0.020:
            raise ValueError("break_interval_s不能小于0.020秒。")

        self.port = port
        self.baud_rate = baud_rate
        self.break_interval_s = break_interval_s
        self.execute = execute
        self.events: list[EventRecord] = []
        self._device = None
        self._origin_ns = time.perf_counter_ns()

    def __enter__(self) -> "Olfactometer":
        self.connect()
        self.close_all()
        self.wait(0.100)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            self.close_all()
        except Exception as close_error:
            print(f"警告：退出时全关失败：{close_error}")
        finally:
            self.disconnect()

    def connect(self) -> None:
        """Open the tested 115200/8-N-1 serial connection."""
        if not self.execute:
            print("模式：DRY RUN（不会打开串口或控制阀门）")
            return
        if self._device is not None:
            return

        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("缺少pySerial：python3 -m pip install pyserial") from exc

        resolved_port = self.port or find_olfactometer_port()
        self.port = resolved_port
        self._device = serial.Serial(
            port=resolved_port,
            baudrate=self.baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self._device.reset_input_buffer()
        self._device.reset_output_buffer()
        print(f"已连接：{resolved_port}, {self.baud_rate} baud, 8-N-1")

    def disconnect(self) -> None:
        """Close the serial connection."""
        if self._device is not None:
            self._device.close()
            self._device = None
            print("串口已断开。")

    def wait(self, seconds: float) -> None:
        """Wait in real mode; print the planned wait in dry-run mode."""
        if seconds < 0:
            raise ValueError("等待时间不能为负数。")
        if self.execute:
            time.sleep(seconds)
        else:
            print(f"[DRY RUN] wait {seconds:.3f} s")

    def open_channel(self, channel: int) -> None:
        """Open one channel; it remains open until a close command."""
        self._validate_channel(channel)
        self._send("open", OPEN_COMMANDS[channel], channel)

    def close_channel(self, channel: int) -> None:
        """Close one channel."""
        self._validate_channel(channel)
        self._send("close", CLOSE_COMMANDS[channel], channel)

    def close_all(self) -> None:
        """Close all channels with command 0x6F."""
        self._send("all-close", ALL_CLOSE, None)

    def switch_channel(self, old_channel: int, new_channel: int) -> None:
        """Close the old channel, wait at least 20 ms, then open the new one."""
        self.close_channel(old_channel)
        self.wait(self.break_interval_s)
        self.open_channel(new_channel)

    def pulse(self, channel: int, duration_s: float) -> None:
        """Safely open one channel for a fixed duration, then close it."""
        self._validate_channel(channel)
        if duration_s <= 0:
            raise ValueError("duration_s必须大于0。")

        self.close_all()
        self.wait(0.100)
        self.open_channel(channel)
        self.wait(duration_s)
        self.close_channel(channel)
        self.wait(self.break_interval_s)
        self.close_all()

    def save_log(self, path: str | Path) -> None:
        """Save all command records as UTF-8 CSV."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=EventRecord.__annotations__)
            writer.writeheader()
            writer.writerows(asdict(event) for event in self.events)
        print(f"日志已保存：{destination}")

    def _send(self, event: str, command: int, channel: Optional[int]) -> None:
        payload = bytes([command])
        before_ns = time.perf_counter_ns()

        if self.execute:
            if self._device is None:
                raise RuntimeError("串口尚未连接。请使用with Olfactometer(...)。")
            self._device.write(payload)
            self._device.flush()

        after_ns = time.perf_counter_ns()
        record = EventRecord(
            event=event,
            channel=channel,
            command_hex=f"0x{command:02X}",
            elapsed_s=(before_ns - self._origin_ns) / 1_000_000_000,
            write_duration_ms=(after_ns - before_ns) / 1_000_000,
            executed=self.execute,
        )
        self.events.append(record)

        mode = "SEND" if self.execute else "DRY RUN"
        channel_text = f" CH{channel}" if channel is not None else ""
        print(f"[{mode}] {event}{channel_text}: 0x{command:02X}")

    @staticmethod
    def _validate_channel(channel: int) -> None:
        if channel not in OPEN_COMMANDS:
            raise ValueError("通道编号必须是1到12的整数。")


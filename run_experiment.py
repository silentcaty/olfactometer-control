#!/usr/bin/env python3
"""Edit the configuration below, then preview or run the valve sequence."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from olfactometer import Olfactometer, list_serial_ports


# ======================== 只需要修改这一部分 ========================

# None表示根据已确认的VID:PID自动寻找嗅觉仪。
# 如果自动寻找失败，可填写完整端口，如"/dev/cu.usbmodem5ABA1307981"。
PORT = None

# 已在当前仪器上验证成功，通常不需要修改。
BAUD_RATE = 115200

# 关闭旧通道到下一次开启之间的最短空档，不能小于0.020秒。
BREAK_INTERVAL_S = 0.020

# 每项格式：(通道编号, 开启时长秒, 该试次结束后的等待秒)
# 按实验设计增删或调整顺序即可。
TRIALS = [
    (8, 3, 2.0),
    (2, 2, 5.0),
    (11, 5, 1.0),
    (5, 3, 2)
]

# ==================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行嗅觉仪阀门试次序列")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="真实控制阀门；不加此参数时只打印演练",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="列出Mac当前串口并退出",
    )
    parser.add_argument(
        "--test-channel",
        type=int,
        choices=range(1, 13),
        metavar="1..12",
        help="忽略TRIALS，只测试指定的一个通道",
    )
    parser.add_argument(
        "--test-duration",
        type=float,
        default=0.5,
        help="单通道测试时的开启秒数（默认0.5）",
    )
    parser.add_argument("--log", type=Path, help="自定义CSV日志路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_ports:
        list_serial_ports()
        return 0
    if args.test_duration <= 0:
        raise SystemExit("--test-duration必须大于0。")

    trials = (
        [(args.test_channel, args.test_duration, 0.0)]
        if args.test_channel is not None
        else TRIALS
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log or Path("logs") / f"experiment_{timestamp}.csv"

    controller = Olfactometer(
        port=PORT,
        baud_rate=BAUD_RATE,
        break_interval_s=BREAK_INTERVAL_S,
        execute=args.execute,
    )

    mode = "真实控制" if args.execute else "DRY RUN"
    print(f"模式：{mode}；共{len(trials)}个试次")

    try:
        with controller:
            for trial_number, (channel, duration_s, interval_s) in enumerate(
                trials, start=1
            ):
                print(
                    f"\n试次{trial_number}/{len(trials)}："
                    f"CH{channel}开启{duration_s:.3f}秒"
                )
                controller.pulse(channel, duration_s)
                controller.wait(interval_s)
    finally:
        controller.save_log(log_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

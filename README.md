# 嗅觉仪 MATLAB / Python 控制框架

本项目通过USB虚拟串口控制12通道嗅觉仪，支持macOS和Windows。当前仪器已经实测确认：

- USB串口设备：`VID:PID=1A86:55D3`
- 波特率：`115200`
- 串口格式：`8-N-1`，无流控
- 协议：单字节二进制命令
- 全部关闭：`0x6F`
- 通道切换空档：至少20 ms

代码同时支持macOS和Windows。Windows首次使用请阅读`WINDOWS_SETUP.md`。

## 文件说明

- `olfactometer.py`：可复用的底层控制类。
- `run_experiment.py`：实验序列示例，主要修改这个文件顶部的配置区。
- `runOlfactometerMatlab.m`：MATLAB控制和实验序列示例。
- `WINDOWS_SETUP.md`：Windows迁移与首次连接指南。
- `requirements.txt`：Python依赖。
- `控制通道指令集.png`：设备命令表原图。

## 1. 准备Python环境

在Mac“终端”中进入项目：

```bash
cd /Users/shiz/Documents/OlfacMac
```

首次使用时创建并启用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

以后再次打开终端，只需要：

```bash
cd /Users/shiz/Documents/OlfacMac
source .venv/bin/activate
```

也可以不激活环境，直接使用`.venv/bin/python`运行命令。

## 2. 查看串口

连接并开启嗅觉仪后运行：

```bash
python run_experiment.py --list-ports
```

正常情况下会看到类似：

```text
/dev/cu.usbmodem5ABA1307981 ... VID:PID=1A86:55D3 <-- 嗅觉仪候选
```

程序默认根据VID和PID自动寻找设备，因此端口名称发生小幅变化时通常不需要改代码。

## 3. 编辑实验序列

打开`run_experiment.py`，修改顶部配置区：

```python
PORT = None
BAUD_RATE = 115200
BREAK_INTERVAL_S = 0.020

TRIALS = [
    (1, 0.5, 1.0),
    (2, 0.5, 1.0),
    (3, 0.5, 1.0),
]
```

每个试次包含三个值：

```text
(通道编号, 阀门开启时长, 试次结束后的等待时间)
```

例如：

```python
TRIALS = [
    (3, 2.0, 5.0),  # CH3开启2秒，然后等待5秒
    (1, 1.5, 3.0),  # CH1开启1.5秒，然后等待3秒
    (6, 2.0, 5.0),  # CH6开启2秒，然后等待5秒
]
```

## 4. 先做安全演练

不加`--execute`时，程序只打印命令，不连接仪器，也不会真的等待：

```bash
python run_experiment.py
```

检查通道、顺序、时长和命令全部正确后，再进行真实测试。

## 5. 真实运行

确认没有被试连接，并优先使用空气或空瓶测试：

```bash
python run_experiment.py --execute
```

只测试一个通道而不运行整个`TRIALS`：

```bash
python run_experiment.py --execute --test-channel 1 --test-duration 0.5
```

程序会在每个试次执行：

```text
全部关闭 → 等待100 ms → 打开目标通道 → 等待设定时长
→ 关闭目标通道 → 等待20 ms → 再次全部关闭
```

正常退出、报错或按`Ctrl+C`时，上下文管理器都会尽力再次发送`0x6F`。

## 6. 在自己的Python程序中调用

```python
from olfactometer import Olfactometer

with Olfactometer(execute=True) as device:
    device.pulse(channel=1, duration_s=0.5)
    device.wait(1.0)
    device.pulse(channel=2, duration_s=0.5)
```

也可以手动控制：

```python
with Olfactometer(execute=True) as device:
    device.open_channel(1)
    device.wait(0.5)
    device.close_channel(1)

    device.wait(0.020)
    device.open_channel(2)
```

推荐优先使用`pulse()`和`switch_channel()`，避免漏掉关闭命令或20 ms空档。

## 7. 日志

每次运行都会在`logs/`目录生成CSV日志，包括：

- 事件类型；
- 通道；
- 十六进制命令；
- 程序计时；
- 串口写入调用时长；
- 是否为真实发送。

自定义日志路径：

```bash
python run_experiment.py --execute --log logs/my_test.csv
```

日志中的时间代表电脑调用串口写入的时间，不等于阀门机械动作或气味到达鼻前的时刻。正式实验需要用压力、流量或其他传感器测量实际延迟。

## 命令表

| 通道 | 打开 | 关闭 |
|---|---:|---:|
| CH1 | `0x01` | `0x21` |
| CH2 | `0x02` | `0x22` |
| CH3 | `0x03` | `0x23` |
| CH4 | `0x04` | `0x24` |
| CH5 | `0x05` | `0x25` |
| CH6 | `0x06` | `0x26` |
| CH7 | `0x07` | `0x27` |
| CH8 | `0x08` | `0x28` |
| CH9 | `0x09` | `0x29` |
| CH10 | `0x10` | `0x30` |
| CH11 | `0x11` | `0x31` |
| CH12 | `0x12` | `0x32` |

`0x69`是打开所有通道，框架没有暴露该操作，以降低误操作风险；`0x6F`用于关闭所有通道。

## MATLAB版本

MATLAB框架位于`runOlfactometerMatlab.m`，使用当前推荐的`serialport`接口。

在MATLAB中进入项目目录：

```matlab
cd('/Users/shiz/Documents/OlfacMac')
```

先做DRY RUN：

```matlab
runOlfactometerMatlab
```

确认输出无误后真实运行：

```matlab
timingLog = runOlfactometerMatlab(true);
```

只测试CH1并开启0.5秒：

```matlab
timingLog = runOlfactometerMatlab(true, 1, 0.5);
```

实验顺序在文件顶部修改：

```matlab
% 每行：[通道编号, 开启秒数, 试次后等待秒数]
trials = [
    1, 0.5, 1.0;
    2, 0.5, 1.0;
    3, 0.5, 1.0
];
```

师兄示例中的`serial`、`fopen`、`fwrite`和`fclose`是MATLAB旧接口。新版对应关系是：

| 旧接口 | 当前接口 |
|---|---|
| `serial(port,...)` + `fopen` | `serialport(port,baud)` |
| `fwrite(s,value)` | `write(s,uint8(value),"uint8")` |
| `fclose(s)` | `clear s`或让对象离开作用域 |
| `instrfindall` | 通常不需要；必要时使用`serialportfind` |

不要照搬旧代码中的`COM3`：它是Windows端口名。当前Mac使用`/dev/cu.usbmodem...`，示例框架会自动寻找唯一的该类端口。

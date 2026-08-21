# Windows迁移与首次测试

## 1. 准备环境

1. 将GitHub仓库下载或克隆到Windows电脑。
2. 连接并开启嗅觉仪。
3. 打开“设备管理器 → 端口（COM和LPT）”。
4. 记下嗅觉仪对应的端口，例如`COM5`。

如果设备管理器没有出现新的COM口，需要先安装WCH USB串口驱动。

## 2. MATLAB控制

在MATLAB中进入项目目录，例如：

```matlab
cd('D:\olfactometer-control')
```

查看端口：

```matlab
serialportlist("available")
```

如果电脑只连接了一个COM串口，程序可以自动选择。如果存在多个串口，在`runOlfactometerMatlab.m`顶部填写：

```matlab
portName = "COM5";
```

先做DRY RUN：

```matlab
runOlfactometerMatlab
```

只测试CH1、开启0.5秒：

```matlab
runOlfactometerMatlab(true, 1, 0.5)
```

运行文件中配置的完整试次列表：

```matlab
timingLog = runOlfactometerMatlab(true);
```

## 3. Python控制（可选）

在PowerShell中进入项目目录并创建Windows自己的虚拟环境：

```powershell
cd D:\olfactometer-control
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

不要从Mac复制`.venv`目录。虚拟环境必须在Windows上重新创建。

查看端口：

```powershell
python run_experiment.py --list-ports
```

先演练，再真实运行：

```powershell
python run_experiment.py
python run_experiment.py --execute --test-channel 1 --test-duration 0.5
```

## 4. 已确认的通信参数

- 波特率：`115200`
- 数据格式：`8-N-1`
- 流控：无
- 指令编码：单字节二进制
- 全部关闭：`0x6F`
- 通道切换空档：至少20 ms

Windows上的COM编号可能随电脑、USB插孔或驱动重新安装而变化。每次更换电脑后都应先检查端口，不要默认沿用`COM3`或`COM4`。


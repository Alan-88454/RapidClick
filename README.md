# RapidClick

基于 CustomTkinter + pynput 的 Windows 鼠标/键盘连点器。A Windows auto-clicker for mouse buttons and keyboard keys, built with Python.

简体中文 | [English](#english)

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![License](https://img.shields.io/badge/License-Unlicense-green)

## 功能特性

- **鼠标 / 键盘都能连点**：左键、右键，或任意键盘按键（点击捕获框后按下任意键即可设置）
- **全局热键**：F7 随时启停，无需切换到主窗口
- **精确间隔**：`perf_counter` 绝对时刻调度 + 运行期提升系统定时器分辨率到 1ms，10ms 就是 10ms
- **实时速率显示**：状态栏每秒显示「实际发送 X.X 次/秒」，方便与目标程序对比
- **现代化界面**：CustomTkinter 深色主题、圆角卡片、间隔滑块与输入框双向联动
- **线程安全**：热键经主线程轮询处理，点击线程不触碰任何 Tkinter 对象
- **干净退出**：关闭窗口自动停止点击线程与键盘监听

## 环境要求

- Windows 10/11
- Python 3.8+

## 安装与运行

```bash
pip install pynput customtkinter
python main.py
```

## 使用说明

1. 填写点击间隔（毫秒），最小 1ms，默认 100ms；也可拖动滑块
2. 分段选择连点对象：**鼠标左键** / **鼠标右键** / **键盘按键**
3. 选「键盘按键」时：点击「点击设置按键」捕获框（变绿），按下任意键（变蓝显示按键名）；Esc 或 F7 可取消；再次点击捕获框可换键
4. 点击「开始」或按 **F7** 启动连点；再次点击或按 F7 停止（按钮变红表示运行中）
5. 连点中切换其他窗口，F7 热键依然有效；运行中也可直接更换连点对象，立即生效

## 间隔精度

点击循环采用绝对时间点调度：第 n 次点击的目标时刻为 `起始时刻 + n × 间隔`，
消除 `sleep` 抖动与点击本身耗时的累积漂移。连点期间程序调用
`timeBeginPeriod(1)` 将 Windows 系统定时器分辨率提升到 1ms（否则
`Event.wait` 在 15.6ms 粒度下会整体超时），结束时恢复。实测（各持续 1 秒）：

| 设定间隔 | 实测均值 | 标准差 | 点击次数 |
|---------|---------|--------|---------|
| 10ms    | 10.000ms | 0.002ms | 101 |
| 20ms    | 20.000ms | 0.001ms | 51  |
| 50ms    | 50.000ms | 0.043ms | 21  |

> 实际点击速率还受系统输入事件处理能力限制：当单次点击耗时超过设定间隔时，
> 程序会自动对齐到当前时刻继续，不会出现补偿式爆发连点。

## 项目结构

```
RapidClick/
├── main.py       # 全部实现（GUI + 点击线程 + 热键监听 + 按键捕获）
└── .gitignore
```

## 声明

本工具仅供自动化测试、重复性操作辅助等合法用途，请勿用于违反游戏用户协议或法律法规的场景。

---

## English

[简体中文](#rapidclick) | English

A Windows auto-clicker for mouse buttons and keyboard keys, built with CustomTkinter + pynput.

### Features

- **Mouse and keyboard**: Click the left/right mouse button, or any keyboard key (click the capture box, then press any key to set it)
- **Global hotkey**: Start/stop anytime with F7, no need to focus the main window
- **Accurate intervals**: Absolute `perf_counter` deadline scheduling + raising the system timer resolution to 1ms while running — 10ms means 10ms
- **Live rate display**: The status bar shows the actual send rate every second for easy comparison
- **Modern UI**: CustomTkinter dark theme, rounded cards, slider <-> entry interval sync
- **Thread-safe**: Hotkey events are handled via main-thread polling; the click thread never touches Tkinter
- **Clean shutdown**: Closing the window automatically stops the click thread and keyboard listener

### Requirements

- Windows 10/11
- Python 3.8+

### Install & Run

```bash
pip install pynput customtkinter
python main.py
```

### Usage

1. Enter the click interval in milliseconds (min 1ms, default 100ms), or drag the slider
2. Pick the click target in the segmented control: **left button** / **right button** / **keyboard key**
3. For keyboard mode: click the capture button (turns green), then press any key (turns blue showing the key name); Esc or F7 cancels; click again to change the key
4. Click "开 始" (Start) or press **F7** to start clicking; click again or press F7 to stop (the button turns red while running)
5. The F7 hotkey keeps working even when other windows are focused; switching the click target while running takes effect immediately

### Click Interval Accuracy

The click loop is scheduled on absolute deadlines: the target time of the n-th click is
`start time + n × interval`, eliminating cumulative drift caused by `sleep` jitter and
the click itself. While clicking, the app calls `timeBeginPeriod(1)` to raise the Windows
timer resolution to 1ms (otherwise `Event.wait` overshoots under the 15.6ms default
granularity) and restores it afterwards. Measured (1 second per run):

| Set interval | Measured mean | Std dev | Clicks |
|--------------|---------------|---------|--------|
| 10ms         | 10.000ms      | 0.002ms | 101    |
| 20ms         | 20.000ms      | 0.001ms | 51     |
| 50ms         | 50.000ms      | 0.043ms | 21     |

> The actual click rate is also limited by how fast the system processes input events.
> When a single click takes longer than the set interval, the program realigns to the
> current time and continues — no compensating burst of clicks.

### Project Structure

```
RapidClick/
├── main.py       # Entire implementation (GUI + click thread + hotkey listener + key capture)
└── .gitignore
```

### Disclaimer

This tool is intended for legitimate purposes such as automated testing and reducing
repetitive strain. Do not use it in ways that violate game terms of service or applicable
laws and regulations.

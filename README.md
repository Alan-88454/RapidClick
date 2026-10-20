# RapidClick

基于 tkinter + pynput 的 Windows 鼠标连点器。A Windows auto-clicker built with Python.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![License](https://img.shields.io/badge/License-Unlicense-green)

## 功能特性

- **全局热键**：F7 随时启停，无需切换到主窗口
- **左/右键可选**：单选切换点击的鼠标按键
- **精确间隔**：`perf_counter` 绝对时刻调度，间隔不随运行时间漂移
- **线程安全**：热键经主线程轮询处理，避免跨线程操作 GUI
- **干净退出**：关闭窗口自动停止点击线程与键盘监听

## 环境要求

- Windows
- Python 3.8+

## 安装与运行

```bash
pip install pynput
python main.py
```

## 使用说明

1. 在输入框填写点击间隔（毫秒），最小 1ms，默认 100ms
2. 选择左键或右键
3. 点击「开始」或按 **F7** 启动连点；再次点击或按 F7 停止
4. 点击过程中可切换到其他窗口，F7 热键依然有效

## 间隔精度

点击循环采用绝对时间点调度：第 n 次点击的目标时刻为 `起始时刻 + n × 间隔`，
消除 `sleep` 抖动与点击本身耗时的累积漂移。实测（各持续 1 秒）：

| 设定间隔 | 实测均值 | 标准差 | 点击次数 |
|---------|---------|--------|---------|
| 10ms    | 10.000ms | 0.002ms | 101 |
| 20ms    | 20.000ms | 0.001ms | 51  |
| 50ms    | 50.000ms | 0.043ms | 21  |

> 实际点击速率还受系统鼠标事件处理能力限制：当单次点击耗时超过设定间隔时，
> 程序会自动对齐到当前时刻继续，不会出现补偿式爆发连点。

## 项目结构

```
RapidClick/
├── main.py       # 全部实现（GUI + 点击线程 + 热键监听）
└── .gitignore
```

## 声明

本工具仅供自动化测试、重复性操作辅助等合法用途，请勿用于违反游戏用户协议或法律法规的场景。

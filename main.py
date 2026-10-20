import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk  # 确保导入 messagebox

from pynput import keyboard
from pynput.mouse import Button, Controller


class MouseClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("鼠标连点器")
        self.root.geometry("400x250")  # 调整窗口大小

        self.mouse = Controller()
        self.clicking = False

        # 主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 点击间隔时间（毫秒）
        self.interval_label = ttk.Label(self.main_frame, text="点击间隔时间（毫秒）:")
        self.interval_label.pack(pady=5)

        self.interval_entry = ttk.Entry(self.main_frame)
        self.interval_entry.insert(0, "100")  # 默认100毫秒
        self.interval_entry.pack(pady=5)

        # 选择点击按钮（左键/右键）
        self.button_label = ttk.Label(self.main_frame, text="选择点击按钮:")
        self.button_label.pack(pady=5)

        self.button_var = tk.StringVar(value="left")  # 默认左键
        self.left_button = ttk.Radiobutton(self.main_frame, text="左键", variable=self.button_var, value="left")
        self.left_button.pack()
        self.right_button = ttk.Radiobutton(self.main_frame, text="右键", variable=self.button_var, value="right")
        self.right_button.pack()

        # 开始/停止按钮
        self.start_button = ttk.Button(self.main_frame, text="开始", command=self.toggle_clicking)
        self.start_button.pack(pady=10)

        # 提示信息
        self.hint_label = ttk.Label(self.main_frame, text="按下 F7 键开始或停止点击")
        self.hint_label.pack(pady=5)

        # 点击线程的停止信号（用 Event 而不是布尔标志，可被立即打断）
        self.stop_event = threading.Event()
        self.click_thread = None

        # 热键：监听线程只置标志，由主线程轮询后执行 UI 操作，避免跨线程操作 Tkinter
        self.hotkey_event = threading.Event()
        self.f7_pressed = False

        # 监听键盘事件
        self.listener = keyboard.Listener(
            on_press=self.on_key_press, on_release=self.on_key_release
        )
        self.listener.start()

        # 主线程轮询热键请求
        self.root.after(30, self.poll_hotkey)
        # 关闭窗口时清理监听器与点击线程
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_clicking(self):
        """切换点击状态：开始或停止（只允许在主线程调用）"""
        if self.clicking:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        """校验参数并启动点击线程"""
        try:
            interval_ms = float(self.interval_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return
        if interval_ms < 1:
            messagebox.showerror("错误", "间隔时间必须大于或等于1毫秒")
            return

        # 先确保上一个线程已完全退出，否则快速“停-开”会导致两个线程同时点击
        self.stop_clicking()

        self.clicking = True
        self.start_button.config(text="停止")
        self.stop_event.clear()
        self.click_thread = threading.Thread(
            target=self.click_loop, args=(interval_ms / 1000.0,), daemon=True
        )
        self.click_thread.start()

    def stop_clicking(self):
        """停止连点并等待线程退出（Event 可被立即打断，无需等满一个间隔）"""
        self.clicking = False
        self.stop_event.set()
        if self.click_thread is not None and self.click_thread.is_alive():
            self.click_thread.join(timeout=1.0)
        self.click_thread = None
        self.start_button.config(text="开始")

    def click_loop(self, interval):
        """执行点击循环。

        以 perf_counter 的绝对时间点调度：第 n 次点击的目标时刻为
        起始时刻 + n * interval，因此平均间隔精确等于设定值，
        不会因为点击本身耗时和 sleep 抖动而累积漂移（10ms 就是 10ms）。
        """
        button = Button.left if self.button_var.get() == "left" else Button.right
        next_deadline = time.perf_counter()

        while not self.stop_event.is_set():
            self.mouse.click(button)

            next_deadline += interval
            now = time.perf_counter()
            if next_deadline < now:
                # 单次点击耗时已超过间隔，说明本机跟不上该速率，
                # 重新对齐到当前时刻，避免后续补偿式连点
                next_deadline = now
                continue
            self.precise_wait(next_deadline)

    def precise_wait(self, deadline):
        """等待到指定时刻：长间隔用可中断休眠，最后 2ms 忙等，保证高精度。"""
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return
            if remaining > 0.002:
                # 可被停止信号立刻唤醒
                if self.stop_event.wait(remaining - 0.001):
                    return
            else:
                while time.perf_counter() < deadline:
                    pass
                return

    def on_key_press(self, key):
        """键盘监听线程：只置标志，不直接触碰 Tkinter"""
        if key == keyboard.Key.f7 and not self.f7_pressed:  # 按下F7键
            self.f7_pressed = True
            self.hotkey_event.set()

    def on_key_release(self, key):
        """松开 F7,避免长按时的自动重复把状态反复切换"""
        if key == keyboard.Key.f7:
            self.f7_pressed = False

    def poll_hotkey(self):
        """在主线程中响应热键请求"""
        if self.hotkey_event.is_set():
            self.hotkey_event.clear()
            self.toggle_clicking()
        self.root.after(30, self.poll_hotkey)

    def on_close(self):
        """关闭窗口：停止连点并停止键盘监听"""
        self.stop_clicking()
        if self.listener is not None:
            self.listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseClickerApp(root)
    root.mainloop()
# 1.7.6 o
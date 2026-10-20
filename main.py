import ctypes
import sys
import threading
import time
import tkinter as tk  # 仅用于 StringVar
from tkinter import messagebox

import customtkinter as ctk
from pynput import keyboard
from pynput.mouse import Button, Controller


def _set_high_resolution_timer(enable):
    """Windows 下把系统定时器分辨率提升到 1ms (连点期间).

    threading.Event.wait 的精度受系统定时器粒度影响: 默认 15.6ms 粒度时
    Event.wait(9ms) 实际会等约 15.5ms, 导致连点间隔严重超时.
    运行期间调用 timeBeginPeriod(1) 可恢复毫秒级精度, 结束时恢复原状.
    非 Windows 平台或调用失败时静默忽略.
    """
    if sys.platform == "win32":
        try:
            if enable:
                ctypes.windll.winmm.timeBeginPeriod(1)
            else:
                ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass


# ---- 主题色 ----
FONT_FAMILY = "Microsoft YaHei UI"
ACCENT = "#2FA572"        # 开始 (绿)
ACCENT_HOVER = "#27915F"
DANGER = "#D64541"        # 运行中 (红)
DANGER_HOVER = "#B83A37"
BLUE = "#2E7DD1"          # 已选中按键 (蓝)
BLUE_HOVER = "#256AB5"
CAPTURE_GREEN = "#3BA55D"  # 捕获中 (绿)
CAPTURE_GREEN_HOVER = "#2F8B4E"
IDLE_BTN = ("gray72", "gray28")
IDLE_BTN_HOVER = ("gray66", "gray35")


class MouseClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RapidClick - 鼠标/键盘连点器")
        self.root.geometry("440x560")
        self.root.resizable(False, False)

        self.mouse = Controller()
        self.kb = keyboard.Controller()  # 用于连按键盘按键
        self.clicking = False

        # ---- 主布局 ----
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        main = ctk.CTkFrame(root, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew", padx=20, pady=16)
        main.grid_columnconfigure(0, weight=1)

        # 标题区
        ctk.CTkLabel(
            main, text="RapidClick", anchor="w",
            font=ctk.CTkFont(FONT_FAMILY, 26, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            main, text="鼠标 / 键盘自动连点", anchor="w",
            font=ctk.CTkFont(FONT_FAMILY, 12),
            text_color=("gray40", "gray60"),
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        # ---- 点击间隔卡片 ----
        card_interval = ctk.CTkFrame(main, corner_radius=14)
        card_interval.grid(row=2, column=0, sticky="ew", pady=6)
        card_interval.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card_interval, text="点击间隔(毫秒)", anchor="w",
            font=ctk.CTkFont(FONT_FAMILY, 13),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        self.interval_entry = ctk.CTkEntry(
            card_interval, height=34, width=140, justify="center",
            font=ctk.CTkFont(FONT_FAMILY, 14),
        )
        self.interval_entry.insert(0, "100")  # 默认100毫秒
        self.interval_entry.grid(row=1, column=0, sticky="w", padx=16)
        ctk.CTkLabel(
            card_interval, text="ms", font=ctk.CTkFont(FONT_FAMILY, 12),
            text_color=("gray40", "gray60"),
        ).grid(row=1, column=0, sticky="e", padx=20)

        self.interval_slider = ctk.CTkSlider(
            card_interval, from_=1, to=500, number_of_steps=499,
            command=self._on_slider, height=24,
        )
        self.interval_slider.set(100)
        self.interval_slider.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 12))
        # 输入框 <-> 滑块 双向同步 (_syncing 防止递归触发)
        self._syncing = False
        self.interval_entry.bind("<KeyRelease>", self._on_interval_text)

        # ---- 连点对象卡片 ----
        card_target = ctk.CTkFrame(main, corner_radius=14)
        card_target.grid(row=3, column=0, sticky="ew", pady=6)
        card_target.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card_target, text="连点对象", anchor="w",
            font=ctk.CTkFont(FONT_FAMILY, 13),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        self.button_var = tk.StringVar(value="left")  # 默认左键
        # 点击线程热路径禁止触碰 Tkinter (跨线程 Tcl 调用会被封送回主线程,
        # 阻塞点击线程导致间隔误差). 用普通变量镜像 UI 状态, GIL 下读写安全.
        self._target_mode = "left"
        self.button_var.trace_add("write", self._on_mode_change)

        self.segmented = ctk.CTkSegmentedButton(
            card_target, values=["鼠标左键", "鼠标右键", "键盘按键"],
            command=self._on_segment, height=34,
            font=ctk.CTkFont(FONT_FAMILY, 13),
        )
        self.segmented.set("鼠标左键")
        self.segmented.grid(row=1, column=0, sticky="ew", padx=16, pady=4)

        # 键盘按键捕获按钮: 点击进入捕获态, 按下任意键即设为连点键
        self.key_capture_button = ctk.CTkButton(
            card_target, text="点击设置按键", command=self.toggle_capture,
            height=36, corner_radius=10, font=ctk.CTkFont(FONT_FAMILY, 13),
            fg_color=IDLE_BTN, hover_color=IDLE_BTN_HOVER,
            text_color=("gray10", "gray85"),
        )
        self.key_capture_button.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 12))

        # ---- 开始按钮 ----
        self.start_button = ctk.CTkButton(
            main, text="开始", command=self.toggle_clicking,
            height=46, corner_radius=12,
            font=ctk.CTkFont(FONT_FAMILY, 16, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        )
        self.start_button.grid(row=4, column=0, sticky="ew", pady=(10, 6))

        # ---- 状态栏 ----
        self.status_label = ctk.CTkLabel(
            main, text="空闲", font=ctk.CTkFont(FONT_FAMILY, 12),
            text_color=("gray40", "gray60"),
        )
        self.status_label.grid(row=5, column=0, sticky="ew", pady=(0, 4))

        # ---- 提示信息 ----
        ctk.CTkLabel(
            main,
            text="F7 全局启停连点 - 选\"键盘按键\"后点击捕获框, 再按下任意键设置",
            font=ctk.CTkFont(FONT_FAMILY, 12),
            text_color=("gray40", "gray60"), wraplength=380, justify="center",
        ).grid(row=6, column=0, sticky="ew", pady=(0, 4))

        # 点击线程的停止信号 (用 Event 而不是布尔标志, 可被立即打断)
        self.stop_event = threading.Event()
        self.click_thread = None
        self._hr_timer = False  # 是否已提升系统定时器分辨率

        # 热键: 监听线程只置标志, 由主线程轮询后执行 UI 操作, 避免跨线程操作 Tkinter
        self.hotkey_event = threading.Event()
        self.f7_pressed = False

        # 键盘按键捕获状态: capture_mode 由主线程写, 监听线程读 (GIL 下布尔读写安全)
        self.capture_mode = False
        self.target_key = None          # 当前选中的连点键 (pynput Key/KeyCode)
        self.pending_key = None         # 监听线程捕获到的候选键
        self.capture_done = threading.Event()

        # 发送速率统计: 点击线程只做 +=1, 主线程轮询计算并显示在状态栏
        self._sent_count = 0
        self._stat_count = 0
        self._stat_time = time.perf_counter()

        # 监听键盘事件
        self.listener = keyboard.Listener(
            on_press=self.on_key_press, on_release=self.on_key_release
        )
        self.listener.start()

        # 主线程轮询热键请求
        self.root.after(30, self.poll_hotkey)
        # 关闭窗口时清理监听器与点击线程
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- UI 辅助 ----

    def _on_slider(self, value):
        """滑块拖动 -> 同步到输入框"""
        if self._syncing:
            return
        self._syncing = True
        self.interval_entry.delete(0, "end")
        self.interval_entry.insert(0, str(int(round(value))))
        self._syncing = False

    def _on_interval_text(self, *_):
        """输入框编辑 -> 同步到滑块 (非法输入忽略, 超范围钳制显示)"""
        if self._syncing:
            return
        try:
            value = float(self.interval_entry.get())
        except ValueError:
            return
        self._syncing = True
        self.interval_slider.set(min(max(value, 1), 500))
        self._syncing = False

    def _on_segment(self, value):
        """分段按钮 (中文标签) -> 映射回内部模式值"""
        self.button_var.set({"鼠标左键": "left", "鼠标右键": "right", "键盘按键": "key"}[value])

    def toggle_clicking(self):
        """切换点击状态: 开始或停止 (只允许在主线程调用)"""
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
        if self.button_var.get() == "key" and self.target_key is None:
            messagebox.showerror("错误", "请先点击\"点击设置按键\", 按下要连点的键")
            return

        # 先确保上一个线程已完全退出, 否则快速"停-开"会导致两个线程同时点击
        self.stop_clicking()

        self.clicking = True
        self.start_button.configure(text="停止", fg_color=DANGER, hover_color=DANGER_HOVER)
        self.stop_event.clear()
        # 提升定时器分辨率, 保证 Event.wait 的毫秒级精度
        if not self._hr_timer:
            _set_high_resolution_timer(True)
            self._hr_timer = True
        self.click_thread = threading.Thread(
            target=self.click_loop, args=(interval_ms / 1000.0,), daemon=True
        )
        self.click_thread.start()

    def stop_clicking(self):
        """停止连点并等待线程退出 (Event 可被立即打断, 无需等满一个间隔)"""
        self.clicking = False
        self.stop_event.set()
        if self.click_thread is not None and self.click_thread.is_alive():
            self.click_thread.join(timeout=1.0)
        self.click_thread = None
        self.start_button.configure(text="开始", fg_color=ACCENT, hover_color=ACCENT_HOVER)
        # 恢复系统定时器分辨率
        if self._hr_timer:
            _set_high_resolution_timer(False)
            self._hr_timer = False

    def _on_mode_change(self, *_):
        """主线程 trace 回调: UI 单选变化时同步到普通变量供点击线程读取"""
        self._target_mode = self.button_var.get()

    def get_click_target(self):
        """读取当前连点对象: ('mouse', Button) 或 ('key', pynput键对象).

        每次循环都重新读取, 因此运行中切换目标立即生效.
        不触碰任何 Tkinter 对象, 避免跨线程 Tcl 调用.
        """
        mode = self._target_mode
        if mode == "left":
            return "mouse", Button.left
        if mode == "right":
            return "mouse", Button.right
        return "key", self.target_key

    def click_loop(self, interval):
        """执行点击循环.

        以 perf_counter 的绝对时间点调度: 第 n 次点击的目标时刻为
        起始时刻 + n * interval, 因此平均间隔精确等于设定值,
        不会因为点击本身耗时和 sleep 抖动而累积漂移 (10ms 就是 10ms).
        """
        next_deadline = time.perf_counter()

        while not self.stop_event.is_set():
            kind, target = self.get_click_target()
            if kind == "mouse":
                self.mouse.click(target)
            else:
                self.kb.press(target)
                self.kb.release(target)
            self._sent_count += 1

            next_deadline += interval
            now = time.perf_counter()
            if next_deadline < now:
                # 单次点击耗时已超过间隔, 说明本机跟不上该速率,
                # 重新对齐到当前时刻, 避免后续补偿式连点
                next_deadline = now
                continue
            self.precise_wait(next_deadline)

    def precise_wait(self, deadline):
        """等待到指定时刻: 长间隔用可中断休眠, 最后 2ms 忙等, 保证高精度."""
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
        """键盘监听线程: 只置标志/记录按键, 不直接触碰 Tkinter"""
        if self.capture_mode:
            # 捕获态: Esc 或 F7 取消设置, 其余任意键作为候选连点键
            self.pending_key = None if key in (keyboard.Key.esc, keyboard.Key.f7) else key
            self.capture_done.set()
            return
        if key == keyboard.Key.f7 and not self.f7_pressed:  # 按下F7键
            self.f7_pressed = True
            self.hotkey_event.set()

    def on_key_release(self, key):
        """松开 F7, 避免长按时的自动重复把状态反复切换"""
        if key == keyboard.Key.f7:
            self.f7_pressed = False

    def poll_hotkey(self):
        """在主线程中响应热键请求, 处理按键捕获并刷新发送速率显示"""
        if self.hotkey_event.is_set():
            self.hotkey_event.clear()
            self.toggle_clicking()
        if self.capture_done.is_set():
            self.capture_done.clear()
            self.finish_capture()
        self.update_rate_display()
        self.root.after(30, self.poll_hotkey)

    def update_rate_display(self):
        """每秒把实际发送速率刷新到状态栏, 便于和测量工具对比"""
        now = time.perf_counter()
        if self.clicking and now - self._stat_time >= 1.0:
            rate = (self._sent_count - self._stat_count) / (now - self._stat_time)
            self._stat_count = self._sent_count
            self._stat_time = now
            self.status_label.configure(
                text=f"● 运行中 - 实际发送 {rate:.1f} 次/秒", text_color=ACCENT
            )
        elif not self.clicking:
            self._stat_count = self._sent_count
            self._stat_time = now
            if self.status_label.cget("text") != "空闲":
                self.status_label.configure(text="空闲", text_color=("gray40", "gray60"))

    # ---- 键盘按键捕获 ----

    @staticmethod
    def key_display_name(key):
        """把 pynput 的 Key/KeyCode 转成可读名称"""
        if isinstance(key, keyboard.Key):
            return key.name.upper()
        if isinstance(key, keyboard.KeyCode) and key.char:
            return key.char.upper()
        if isinstance(key, keyboard.KeyCode) and key.vk is not None:
            return f"VK{key.vk}"
        return str(key)

    def toggle_capture(self):
        """点击捕获框: 进入或退出捕获态 (只允许主线程调用)"""
        if self.capture_mode:
            self.exit_capture(cancel=True)
        else:
            self.capture_mode = True
            self.pending_key = None
            self.capture_done.clear()
            self.key_capture_button.configure(
                text="按下任意键... (Esc 取消)",
                fg_color=CAPTURE_GREEN, hover_color=CAPTURE_GREEN_HOVER,
                text_color="white",
            )
            self.root.focus_set()  # 移走按钮焦点, 防止空格/回车误触按钮

    def exit_capture(self, cancel):
        """退出捕获态并恢复按钮外观 (主线程调用)"""
        self.capture_mode = False
        if cancel or self.target_key is None:
            if self.target_key is not None:
                self.key_capture_button.configure(
                    text=f"连点按键: {self.key_display_name(self.target_key)}",
                    fg_color=IDLE_BTN, hover_color=IDLE_BTN_HOVER,
                    text_color=("gray10", "gray85"),
                )
            else:
                self.key_capture_button.configure(
                    text="点击设置按键",
                    fg_color=IDLE_BTN, hover_color=IDLE_BTN_HOVER,
                    text_color=("gray10", "gray85"),
                )
        else:
            self.key_capture_button.configure(
                text=f"连点按键: {self.key_display_name(self.target_key)}",
                fg_color=BLUE, hover_color=BLUE_HOVER,
                text_color="white",
            )

    def finish_capture(self):
        """捕获完成: pending_key 非 None 则设为新的连点键, 否则视为取消"""
        if self.pending_key is not None:
            self.target_key = self.pending_key
            self.exit_capture(cancel=False)
        else:
            self.exit_capture(cancel=True)

    def on_close(self):
        """关闭窗口: 停止连点并停止键盘监听"""
        self.stop_clicking()
        if self.listener is not None:
            self.listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    app = MouseClickerApp(root)
    # 窗口屏幕居中
    root.update_idletasks()
    w, h = 440, 560
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 2}")
    root.mainloop()

"""Small local setup window. Browser and MCP runtimes are imported only when used."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from .core import Canvas, data_dir, load_config, save_config, logout
from .__main__ import mcp_config
from . import __version__


class Window:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CanvasLink — 本地 Canvas · " + __version__)
        self.root.geometry("840x620")
        self.root.minsize(780, 600)
        self.events = queue.Queue()
        self.buttons = []
        self.busy = False
        style = ttk.Style(self.root)
        style.theme_use("vista")
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=7)
        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="CanvasLink", font=("Segoe UI", 24, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="在自己的电脑登录 Canvas，让支持本地 MCP 的 AI 读取你授权的课程内容。", wraplength=750).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3,18))
        self.origin = tk.StringVar()
        self.path = tk.StringVar(value="/login")
        self.browser = tk.StringVar(value="auto")
        self.compat = tk.BooleanVar(value=False)
        self.writes = tk.BooleanVar(value=False)
        for row, label, variable in [(2,"学校 Canvas 地址",self.origin),(3,"登录路径（通常不改）",self.path)]:
            ttk.Label(frame,text=label).grid(row=row,column=0,sticky="w",pady=7,padx=(0,16))
            ttk.Entry(frame,textvariable=variable).grid(row=row,column=1,sticky="ew",pady=7)
        ttk.Label(frame,text="填写学校提供的 HTTPS 域名，例如 https://school.instructure.com",foreground="#555").grid(row=4,column=1,sticky="w")
        ttk.Label(frame,text="登录浏览器").grid(row=5,column=0,sticky="w",pady=10)
        ttk.Combobox(frame,textvariable=self.browser,values=["auto","msedge","chrome"],state="readonly").grid(row=5,column=1,sticky="w")
        ttk.Checkbutton(frame,text="连接兼容模式（登录页面连接重置时再开启）",variable=self.compat).grid(row=6,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Checkbutton(frame,text="允许修改请求：每次仍需在本机弹窗单独确认",variable=self.writes).grid(row=7,column=0,columnspan=2,sticky="w",pady=4)
        row = ttk.Frame(frame);row.grid(row=8,column=0,columnspan=2,sticky="ew",pady=(18,8))
        for text, action in [("1 保存设置",self.save),("2 登录 Canvas",self.login),("3 检查连接",self.check),("4 复制 MCP 配置",self.copy)]:
            button=ttk.Button(row,text=text,command=action);button.pack(side="left",padx=(0,8));self.buttons.append(button)
        row2=ttk.Frame(frame);row2.grid(row=9,column=0,columnspan=2,sticky="w",pady=(0,12))
        for text,action in [("清除本机登录",self.clear),("打开本地数据目录",self.open_data)]:
            button=ttk.Button(row2,text=text,command=action);button.pack(side="left",padx=(0,8));self.buttons.append(button)
        self.status=tk.StringVar(value="首次使用：填写自己的学校地址，然后保存并登录。")
        ttk.Label(frame,textvariable=self.status,wraplength=750,foreground="#164b70").grid(row=10,column=0,columnspan=2,sticky="w",pady=(6,10))
        ttk.Label(frame,text="无共享账号、无作者服务器、无统计上报。登录密码由你在学校网页输入。\n连接 AI 后，所请求的课程内容会提供给该 AI 客户端及其模型服务。\n此版本：Windows 10/11 x64；需要本机已有 Edge 或 Chrome。",wraplength=750,foreground="#555").grid(row=11,column=0,columnspan=2,sticky="w")
        try:
            cfg=load_config();self.origin.set(cfg["origin"]);self.path.set(cfg["login_path"])
            self.browser.set(cfg.get("browser","auto"));self.compat.set(cfg.get("compat",False));self.writes.set(cfg.get("allow_writes",False))
        except RuntimeError:
            pass
        self.root.protocol("WM_DELETE_WINDOW",self.close)
        self.root.after(150,self.poll)

    def save(self):
        try:
            save_config(self.origin.get().strip(),self.path.get().strip(),self.browser.get(),self.compat.get(),self.writes.get())
            self.status.set("已保存到你的 Windows 用户目录。分发目录中不会保存个人配置。")
            return True
        except Exception as e:
            messagebox.showerror("设置未保存",str(e),parent=self.root)
            return False

    def task(self, action):
        if self.busy:return
        self.busy=True
        for b in self.buttons:b.state(["disabled"])
        def work():
            try:
                result=action()
                if result:self.events.put(str(result))
            except Exception as e:self.events.put("操作失败："+str(e))
            finally:self.events.put(None)
        threading.Thread(target=work,daemon=True).start()

    def login(self):
        if not self.save():return
        def action():
            from .login import login
            login(self.events.put)
            return "登录成功：Canvas 身份已实际验证。现在可复制 MCP 配置。"
        self.status.set("正在打开独立登录窗口，请在网页完成学校 SSO／MFA。")
        self.task(action)

    def check(self):
        def action():
            result=Canvas().status()
            if result.get("authenticated"):return "连接成功：Canvas 上游身份验证通过。"
            if result.get("needs_setup"):return "请先保存学校地址。"
            if result.get("needs_login"):return "登录失效或尚未登录。请点击“登录 Canvas”。"
            return "Canvas 尚未通过验证，上游状态："+str(result.get("upstream_status"))
        self.status.set("正在验证 Canvas 上游连接…")
        self.task(action)

    def copy(self):
        text=json.dumps(mcp_config(),ensure_ascii=False,indent=2)
        self.root.clipboard_clear();self.root.clipboard_append(text);self.root.update()
        self.status.set("已复制 MCP 配置。粘贴到支持本地 stdio MCP 的 AI 客户端，再启用该服务。")

    def clear(self):
        logout();self.status.set("已清除本机 Canvas 会话。此操作不会向学校发送注销请求。")

    def open_data(self):
        folder=data_dir();folder.mkdir(parents=True,exist_ok=True);os.startfile(folder)

    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event is None:
                    self.busy=False
                    for b in self.buttons:b.state(["!disabled"])
                else:self.status.set(event)
        except queue.Empty:pass
        self.root.after(150,self.poll)

    def close(self):
        if self.busy:
            self.status.set("操作进行中。请先关闭登录浏览器或等待操作结束，再关闭此窗口。")
            return
        self.root.destroy()


def run():
    Window().root.mainloop()

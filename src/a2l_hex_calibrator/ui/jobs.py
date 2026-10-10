"""后台任务与 Tk 主线程之间的队列通信。不在模块导入时创建窗口。"""

from __future__ import annotations

import queue
import threading
from tkinter import messagebox


class JobMixin:
    """后台任务与 Tk 主线程之间的队列通信。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def run_job(self, message, work, done):
        """工作线程只处理数据，把结果/异常投递队列，禁止在线程内更新 Tk。"""
        if self.busy:
            return
        self.busy = True
        self.status.set(message)
        for b in self.buttons:
            b.configure(state="disabled")

        def background():
            try:
                self.jobs.put((True, work(), done))
            except Exception as exc:
                self.jobs.put((False, str(exc), done))

        threading.Thread(target=background, daemon=True).start()

    def poll(self):
        """由 Tk 定时器读取队列，恢复按钮并执行完成回调。"""
        try:
            ok, result, done = self.jobs.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for b in self.buttons:
                b.configure(state="normal")
            if ok:
                done(result)
            else:
                self.status.set(
                    self.tr("jobs.operation_failed_existing_files_and_editing_state_were_")
                )
                messagebox.showerror(self.tr("jobs.operation_failed"), result, parent=self)
        self.after(80, self.poll)

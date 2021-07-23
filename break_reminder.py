import os, sys
from PySide6 import QtCore, QtWidgets, QtGui

def _format_time_str(seconds):
    minutes, seconds = seconds//60, seconds%60
    if minutes == 0:
        return str(seconds)
    return '{} : {:02}'.format(minutes, seconds)

class BreakDiag(QtWidgets.QWidget):
    # auto close break dialog if break seconds <= auto_close
    auto_close = 60
    def __init__(self, seconds, win_wh=(400,300)):
        super().__init__()
        self.setWindowTitle('休息时间')
        win_w, win_h = win_wh
        self.resize(win_w, win_h)
        screen_size = self.screen().size()
        screen_w, screen_h = screen_size.width(), screen_size.height()
        self.move(QtCore.QPoint(screen_w/2-win_w/2, screen_h/2-win_h/2))
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
    
        self.text = QtWidgets.QLabel(
            _format_time_str(seconds), alignment=QtCore.Qt.AlignCenter)
        font = self.text.font()
        font.setPointSize(64)
        self.text.setFont(font)
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_left_seconds)
        self.timer.setInterval(1000)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.text)
        
        self.timer.start()
        self.seconds = seconds
        self.is_auto_close = self.seconds <= self.auto_close

    @QtCore.Slot()
    def update_left_seconds(self):
        self.seconds -= 1
        self.text.setText(_format_time_str(self.seconds))
        if self.seconds <= 0:
            if self.is_auto_close:
                self.close()
            else:
                
                self.timer.stop()
                self.text.setText("Go")
                self.text.mouseDoubleClickEvent = self.mouse_dc_on_label
            
    @QtCore.Slot()
    def mouse_dc_on_label(self, event):
        self.close()
            
class WorkBreakStage:
    def __init__(self, work_sec, break_sec):
        self._work_sec, self._break_sec = work_sec, break_sec
        self._remain_sec = work_sec
        
    def step_and_check_break(self):
        self._remain_sec -= 1
        return self._remain_sec <= 0
        
    def reset(self):
        self._remain_sec = self._work_sec
        
    @property
    def remain_sec(self):
        return self._remain_sec
    
    @property
    def break_sec(self):
        return self._break_sec
            
class StageManager:
    def __init__(self, work_break_pair_list):
        self._build_stages(work_break_pair_list)
        self.cur_stage_idx = 0
        
    def _build_stages(self, work_break_pair_list):
        self.stages = []
        for (work_sec, break_sec) in work_break_pair_list:
            self.stages.append(WorkBreakStage(work_sec, break_sec))
            
    def _next_stage(self):
        self.cur_stage_idx += 1
        if self.cur_stage_idx == len(self.stages):
            self.cur_stage_idx = 0
        
    def step_and_check_break(self):
        cur_stage = self.stages[self.cur_stage_idx]
        if cur_stage.step_and_check_break():
            break_sec = cur_stage.break_sec
            cur_stage.reset()
            self._next_stage()
            return True, break_sec
        return False, -1
    
    def reset(self):
        self.cur_stage_idx = 0
        for stage in self.stages:
            stage.reset()
    
    @property
    def max_break_sec(self):
        return max(0, *[x.break_sec for x in self.stages])
    
    @property
    def remain_sec(self):
        return self.stages[self.cur_stage_idx].remain_sec
            
class BreakApp(QtWidgets.QWidget):
    def __init__(self, work_break_pair_list):
        super().__init__()
        self.manager = StageManager(work_break_pair_list)
        
        self.tray = QtWidgets.QSystemTrayIcon()
        
        icon = QtGui.QIcon(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),"icon.png"))
        self.tray.setIcon(icon)
        self.tray.setVisible(True)  
        self._add_menu()        
        self.tray.show()
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.step_second)
        self.timer.setInterval(1000)
        self.timer.start()
        
    def _add_menu(self):
        self.menu = QtWidgets.QMenu()
        
        self.open = QtGui.QAction('立即休息')
        self.open.triggered.connect(self.take_break_manual)
        self.menu.addAction(self.open)
        
        self.reset = QtGui.QAction('重置')
        self.reset.triggered.connect(self.reset_break)
        self.menu.addAction(self.reset)
        
        self.quit = QtGui.QAction("退出")
        self.quit.triggered.connect(app.quit)
        self.menu.addAction(self.quit)
        
        self.tray.setContextMenu(self.menu) 
        
    @QtCore.Slot()
    def step_second(self):
        if hasattr(self, 'diag') and self.diag.isVisible():
            self.tray.setToolTip('休息中')
            return
        
        self.tray.setToolTip(_format_time_str(self.manager.remain_sec))
        
        take_break, break_sec = self.manager.step_and_check_break()
        if take_break:
            self.diag = BreakDiag(break_sec)
            self.diag.show()
            
    @QtCore.Slot()
    def take_break_manual(self):
        if hasattr(self, 'diag') and self.diag.isVisible():
            self.diag.close()
            
        self.diag = BreakDiag(self.manager.max_break_sec)
        self.diag.show()
        self.manager.reset()
        
    @QtCore.Slot()
    def reset_break(self):
        if hasattr(self, 'diag') and self.diag.isVisible():
            self.diag.close()
            
        self.manager.reset()
        

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'schedual', nargs='*', type=int,
        default=[1200,20,1200,480],
        help='''
        时间设置,单位为秒,
        默认为工作20分钟,短休（远眺）20秒,
        然后工作20分钟,长休8分钟,
        如此循环
        ''')
    args = parser.parse_args()

    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    bapp = BreakApp(list(zip(args.schedual[::2], args.schedual[1::2])))
    sys.exit(app.exec_())           

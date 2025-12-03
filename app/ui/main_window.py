from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon, InfoBar

from app.ui.views.patient_manager import PatientManagerInterface
from app.ui.views.nystagmus_module import SpontaneousNystagmusModule

class MainWindow(FluentWindow):
    """ 主窗口框架 """
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("VestibularScoper - 前庭功能检查系统")
        self.resize(1200, 800)
        
        # 1. 创建子界面
        self.home_interface = PatientManagerInterface(self)
        self.nystagmus_module = SpontaneousNystagmusModule(self)
        
        # 2. 初始化导航栏
        self.init_navigation()
        
        # 3. 信号连接
        self.home_interface.patient_selected.connect(self.on_patient_selected)

    def init_navigation(self):
        # 患者管理
        self.addSubInterface(
            self.home_interface,
            FluentIcon.PEOPLE,
            "患者管理",
            NavigationItemPosition.TOP
        )
        
        # 自发眼震模块 (包含检查+分析)
        self.addSubInterface(
            self.nystagmus_module,
            FluentIcon.VIDEO,
            "自发眼震",
            NavigationItemPosition.TOP
        )

    def on_patient_selected(self, patient_id, patient_name):
        """ 选中患者后，同步更新相关页面 """
        self.nystagmus_module.set_current_patient(patient_id, patient_name)
        
        # 跳转到眼震模块
        self.switchTo(self.nystagmus_module)
        
        InfoBar.info(
            title='就绪',
            content=f"当前患者: {patient_name}",
            parent=self
        )

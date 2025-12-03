from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon, InfoBar

from app.ui.views.patient_manager import PatientManagerInterface
from app.ui.views.spontaneous_test_interface import SpontaneousTestInterface

class MainWindow(FluentWindow):
    """ 主窗口框架 """
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("VestibularScoper - 前庭功能检查系统")
        self.resize(1200, 800)
        
        # 1. 创建子界面
        self.home_interface = PatientManagerInterface(self)
        self.test_interface = SpontaneousTestInterface(self)
        
        # 2. 初始化导航栏
        self.init_navigation()
        
        # 3. 信号连接
        self.home_interface.patient_selected.connect(self.start_examination)

    def init_navigation(self):
        # 首页 - 患者管理
        self.addSubInterface(
            self.home_interface,
            FluentIcon.PEOPLE,
            "患者管理",
            NavigationItemPosition.TOP
        )
        
        # 检查页面
        self.test_interface_pos = self.addSubInterface(
            self.test_interface,
            FluentIcon.VIDEO,
            "自发眼震检查",
            NavigationItemPosition.TOP
        )

    def start_examination(self, patient_id, patient_name):
        """ 选中患者后跳转到检查页面 """
        # 通知检查页面当前是哪个患者
        self.test_interface.set_current_patient(patient_id, patient_name)
        
        # 切换到检查页面
        self.switchTo(self.test_interface)
        
        InfoBar.info(
            title='就绪',
            content=f"当前患者: {patient_name}",
            parent=self
        )

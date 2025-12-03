from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Qt
from qfluentwidgets import Pivot

from app.ui.views.spontaneous_test_interface import SpontaneousTestInterface
from app.ui.views.analysis_interface import AnalysisInterface

class SpontaneousNystagmusModule(QWidget):
    """ 自发性眼震模块：检查 + 分析 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SpontaneousNystagmusModule")
        
        # 主布局
        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        
        # 顶部 Tab 切换栏
        self.pivot = Pivot(self)
        self.pivot.addItem(routeKey='exam', text='实时检查')
        self.pivot.addItem(routeKey='analysis', text='数据分析')
        self.pivot.setCurrentItem('exam')
        
        # 使用 QStackedWidget 管理多个页面 (无缝切换)
        self.stacked_widget = QStackedWidget(self)
        
        # 创建子页面
        self.exam_interface = SpontaneousTestInterface(self)
        self.analysis_interface = AnalysisInterface(self)
        
        self.stacked_widget.addWidget(self.exam_interface)
        self.stacked_widget.addWidget(self.analysis_interface)
        
        # 布局
        v_layout.addWidget(self.pivot, 0, Qt.AlignLeft)
        v_layout.addWidget(self.stacked_widget, 1)
        
        # 连接切换事件
        self.pivot.currentItemChanged.connect(self.on_tab_changed)
        
        self.current_patient = None

    def on_tab_changed(self, key):
        """ Tab 切换 """
        if key == 'exam':
            self.stacked_widget.setCurrentWidget(self.exam_interface)
        elif key == 'analysis':
            self.stacked_widget.setCurrentWidget(self.analysis_interface)
            # 刷新记录列表
            self.analysis_interface.load_records()

    def set_current_patient(self, p_id, p_name):
        self.current_patient = (p_id, p_name)
        self.exam_interface.set_current_patient(p_id, p_name)
        self.analysis_interface.set_current_patient(p_id, p_name)

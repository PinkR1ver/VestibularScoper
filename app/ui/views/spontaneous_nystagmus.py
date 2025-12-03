import os
import time
from datetime import datetime
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from qfluentwidgets import SubtitleLabel, PushButton, FluentIcon, CardWidget, InfoBar

from app.core.camera import CameraThread

class GazePlotWidget(pg.PlotWidget):
    """ 实时眼动波形图组件 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self.setBackground('w') # 白色背景
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel('left', 'Angle (deg)')
        self.setLabel('bottom', 'Time (s)')
        self.setYRange(-45, 45)
        
        # 初始化曲线
        self.pitch_curve = self.plot(pen=pg.mkPen(color='#FF5252', width=2), name='Pitch') # 红色
        self.yaw_curve = self.plot(pen=pg.mkPen(color='#448AFF', width=2), name='Yaw')   # 蓝色
        
        # 数据缓冲区
        self.buffer_size = 300 # 显示最近300个点 (约5秒 @ 60fps)
        self.times = np.zeros(self.buffer_size)
        self.pitch_data = np.zeros(self.buffer_size)
        self.yaw_data = np.zeros(self.buffer_size)

    def update_data(self, t, p, y):
        # 滚动更新数据
        self.times[:-1] = self.times[1:]
        self.pitch_data[:-1] = self.pitch_data[1:]
        self.yaw_data[:-1] = self.yaw_data[1:]
        
        self.times[-1] = t
        self.pitch_data[-1] = p
        self.yaw_data[-1] = y
        
        self.pitch_curve.setData(self.times, self.pitch_data)
        self.yaw_curve.setData(self.times, self.yaw_data)

class EyeRoiWidget(CardWidget):
    """ 眼部特写显示组件 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.v_layout = QVBoxLayout(self)
        
        self.title = QLabel("眼部特写 (Eye ROI)", self)
        self.img_label = QLabel("等待数据...", self)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setMinimumSize(120, 80)
        self.img_label.setStyleSheet("background-color: #000; border-radius: 4px; color: gray;")
        
        self.v_layout.addWidget(self.title)
        self.v_layout.addWidget(self.img_label, 1)

    def update_image(self, qt_image):
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.img_label.setPixmap(pixmap)

class CameraInterface(QWidget):
    """ 仪表盘式检查界面 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("CameraInterface")
        
        # 主布局
        self.main_layout = QGridLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # 1. 左上: 主视频区域
        self.video_frame = CardWidget(self)
        self.video_layout = QVBoxLayout(self.video_frame)
        
        self.header_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("实时监控", self.video_frame)
        self.btn_start = PushButton(FluentIcon.CAMERA, "启动检查", self.video_frame)
        self.btn_start.clicked.connect(self.toggle_camera)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch(1)
        self.header_layout.addWidget(self.btn_start)
        
        self.video_label = QLabel("请先选择患者，然后点击启动", self.video_frame)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; color: white;")
        self.video_label.setMinimumSize(640, 360)
        
        self.video_layout.addLayout(self.header_layout)
        self.video_layout.addWidget(self.video_label, 1)
        
        # 2. 右上: 眼部 ROI
        self.roi_widget = EyeRoiWidget(self)
        
        # 3. 右中: 数值显示
        self.data_card = CardWidget(self)
        self.data_layout = QVBoxLayout(self.data_card)
        self.lbl_pitch = SubtitleLabel("Pitch: 0.0°", self.data_card)
        self.lbl_yaw = SubtitleLabel("Yaw: 0.0°", self.data_card)
        self.lbl_rec_status = QLabel("未录制", self.data_card) # 录制状态
        self.lbl_rec_status.setStyleSheet("color: gray;")
        
        self.data_layout.addWidget(self.lbl_pitch)
        self.data_layout.addWidget(self.lbl_yaw)
        self.data_layout.addSpacing(10)
        self.data_layout.addWidget(self.lbl_rec_status)
        self.data_layout.addStretch(1)

        # 4. 底部: 波形图
        self.plot_widget = GazePlotWidget(self)
        self.plot_widget.setMinimumHeight(200)
        
        # 布局组装
        self.main_layout.addWidget(self.video_frame, 0, 0, 2, 2)
        self.main_layout.addWidget(self.roi_widget, 0, 2, 1, 1)
        self.main_layout.addWidget(self.data_card, 1, 2, 1, 1)
        self.main_layout.addWidget(self.plot_widget, 2, 0, 1, 3)
        
        # 摄像头线程
        self.camera_thread = CameraThread(camera_id=0)
        self.camera_thread.frame_received.connect(self.update_main_frame)
        self.camera_thread.eye_roi_received.connect(self.roi_widget.update_image)
        self.camera_thread.gaze_data_received.connect(self.update_gaze_data)
        
        self.is_camera_on = False
        self.current_patient = None # (id, name, patient_id_str)

    def set_current_patient(self, p_id, p_name):
        # 这里假设传入的是 database ID 和 Name
        # 实际上最好能传入 Patient 对象或由上一层传入 Patient_ID 字符串
        # 暂时简单处理，假设 name 里可能包含 id 信息或者我们只用 name
        self.current_patient = (p_id, p_name)
        self.title_label.setText(f"检查中: {p_name}")
        self.video_label.setText("准备就绪")

    def toggle_camera(self):
        if self.is_camera_on:
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self):
        if not self.current_patient:
            InfoBar.warning(title='警告', content="请先在患者列表选择一位患者", parent=self)
            return

        # 1. 生成存储路径
        # 格式: Data/{PatientName}_{ID}/{Timestamp}.mkv
        p_id, p_name = self.current_patient
        # 清理文件名非法字符
        safe_name = "".join([c for c in p_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        folder_name = f"{p_id}_{safe_name}"
        
        save_dir = os.path.join("Data", folder_name)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(save_dir, f"{timestamp}.mkv")
        
        # 2. 启动线程
        self.camera_thread.start(save_path=save_path)
        
        # 3. 更新 UI
        self.btn_start.setText("停止检查")
        self.lbl_rec_status.setText(f"REC: {os.path.basename(save_path)}")
        self.lbl_rec_status.setStyleSheet("color: red; font-weight: bold;")
        self.is_camera_on = True
        
        InfoBar.success(title='开始录制', content=f"文件保存至: {save_path}", parent=self)

    def stop_capture(self):
        self.camera_thread.stop()
        self.btn_start.setText("启动检查")
        self.video_label.setText("检查已结束")
        self.lbl_rec_status.setText("未录制")
        self.lbl_rec_status.setStyleSheet("color: gray;")
        self.is_camera_on = False

    @Slot(QPixmap)
    def update_main_frame(self, qt_image):
        scaled = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled)

    @Slot(float, float, float)
    def update_gaze_data(self, t, p, y):
        self.lbl_pitch.setText(f"Pitch: {p:.1f}°")
        self.lbl_yaw.setText(f"Yaw: {y:.1f}°")
        self.plot_widget.update_data(t, p, y)

    def closeEvent(self, event):
        self.camera_thread.stop()
        super().closeEvent(event)

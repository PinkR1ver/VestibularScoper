import os
from datetime import datetime
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from qfluentwidgets import SubtitleLabel, PushButton, FluentIcon, CardWidget, InfoBar, ComboBox

from app.core.camera import CameraThread
from app.core.preview import PreviewThread, enumerate_cameras

class GazePlotWidget(pg.PlotWidget):
    """ 实时眼动波形图组件 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self.setBackground('w')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel('left', 'Angle (deg)')
        self.setLabel('bottom', 'Time (s)')
        self.setYRange(-45, 45)
        
        self.pitch_curve = self.plot(pen=pg.mkPen(color='#FF5252', width=2), name='Pitch')
        self.yaw_curve = self.plot(pen=pg.mkPen(color='#448AFF', width=2), name='Yaw')
        
        self.buffer_size = 300
        self.times = np.zeros(self.buffer_size)
        self.pitch_data = np.zeros(self.buffer_size)
        self.yaw_data = np.zeros(self.buffer_size)

    def update_data(self, t, p, y):
        self.times[:-1] = self.times[1:]
        self.pitch_data[:-1] = self.pitch_data[1:]
        self.yaw_data[:-1] = self.yaw_data[1:]
        
        self.times[-1] = t
        self.pitch_data[-1] = p
        self.yaw_data[-1] = y
        
        self.pitch_curve.setData(self.times, self.pitch_data)
        self.yaw_curve.setData(self.times, self.yaw_data)

class EyeRoiWidget(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.v_layout = QVBoxLayout(self)
        self.title = QLabel("眼部特写 (ROI)", self)
        self.img_label = QLabel("Waiting...", self)
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

class SpontaneousTestInterface(QWidget):
    """ 自发性眼震检查界面 (Spontaneous Nystagmus Test) """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SpontaneousTestInterface")
        
        self.main_layout = QGridLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # 1. 左上: 主视频
        self.video_frame = CardWidget(self)
        self.video_layout = QVBoxLayout(self.video_frame)
        
        # Header: 标题 + 摄像头选择 + 预览 + 启动
        self.header_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("自发性眼震检查", self.video_frame)
        
        # 摄像头选择器
        self.camera_selector = ComboBox(self.video_frame)
        self.camera_selector.setPlaceholderText("选择摄像头")
        self._populate_cameras()
        
        # 预览按钮
        self.btn_preview = PushButton(FluentIcon.VIEW, "预览", self.video_frame)
        self.btn_preview.clicked.connect(self.toggle_preview)
        
        # 正式检查按钮
        self.btn_start = PushButton(FluentIcon.CAMERA, "启动检查", self.video_frame)
        self.btn_start.clicked.connect(self.toggle_recording)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch(1)
        self.header_layout.addWidget(self.camera_selector)
        self.header_layout.addWidget(self.btn_preview)
        self.header_layout.addWidget(self.btn_start)
        
        self.video_label = QLabel("请先选择患者...", self.video_frame)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; color: white;")
        self.video_label.setMinimumSize(640, 360)
        
        self.video_layout.addLayout(self.header_layout)
        self.video_layout.addWidget(self.video_label, 1)
        
        # 2. 右上: ROI
        self.roi_widget = EyeRoiWidget(self)
        
        # 3. 右中: 数值
        self.data_card = CardWidget(self)
        self.data_layout = QVBoxLayout(self.data_card)
        self.lbl_pitch = SubtitleLabel("Pitch: 0.0°", self.data_card)
        self.lbl_yaw = SubtitleLabel("Yaw: 0.0°", self.data_card)
        self.lbl_rec_status = QLabel("就绪", self.data_card)
        self.lbl_rec_status.setStyleSheet("color: gray;")
        self.lbl_fps = QLabel("FPS: --", self.data_card)
        self.lbl_fps.setStyleSheet("color: #0099ff; font-weight: bold;")
        
        self.data_layout.addWidget(self.lbl_pitch)
        self.data_layout.addWidget(self.lbl_yaw)
        self.data_layout.addSpacing(10)
        self.data_layout.addWidget(self.lbl_rec_status)
        self.data_layout.addWidget(self.lbl_fps)
        self.data_layout.addStretch(1)

        # 4. 底部: 波形图
        self.plot_widget = GazePlotWidget(self)
        self.plot_widget.setMinimumHeight(250)
        
        self.main_layout.addWidget(self.video_frame, 0, 0, 2, 2)
        self.main_layout.addWidget(self.roi_widget, 0, 2, 1, 1)
        self.main_layout.addWidget(self.data_card, 1, 2, 1, 1)
        self.main_layout.addWidget(self.plot_widget, 2, 0, 1, 3)
        
        # 相机线程 (用于正式检查+录制)
        self.camera_thread = CameraThread(camera_id=0)
        self.camera_thread.frame_received.connect(self.update_main_frame)
        self.camera_thread.eye_roi_received.connect(self.roi_widget.update_image)
        self.camera_thread.gaze_data_received.connect(self.update_gaze_data)
        self.camera_thread.fps_received.connect(self.update_fps)
        
        # 预览线程 (仅用于预览，不录制)
        self.preview_thread = None
        
        self.is_previewing = False
        self.is_recording = False
        self.current_patient = None

    def _populate_cameras(self):
        """ 扫描可用摄像头并填充到下拉框 """
        cameras = enumerate_cameras(max_check=5)
        if not cameras:
            self.camera_selector.addItem("无可用摄像头")
            self.camera_selector.setEnabled(False)
        else:
            for cam_id in cameras:
                self.camera_selector.addItem(f"摄像头 {cam_id}", userData=cam_id)
            self.camera_selector.setCurrentIndex(0)

    def _get_selected_camera_id(self):
        """ 获取当前选中的摄像头 ID """
        current_data = self.camera_selector.currentData()
        return current_data if current_data is not None else 0

    def set_current_patient(self, p_id, p_name):
        self.current_patient = (p_id, p_name)
        self.title_label.setText(f"检查中: {p_name} (自发性眼震)")
        self.video_label.setText("请先点击「预览」调整画面")

    def toggle_preview(self):
        """ 切换预览模式 """
        if self.is_previewing:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        """ 启动预览 (不录制) """
        cam_id = self._get_selected_camera_id()
        
        self.preview_thread = PreviewThread(camera_id=cam_id)
        self.preview_thread.frame_received.connect(self.update_main_frame)
        self.preview_thread.fps_updated.connect(self.update_fps)
        self.preview_thread.start()
        
        self.btn_preview.setText("停止预览")
        self.lbl_rec_status.setText("预览模式 (未录制)")
        self.lbl_rec_status.setStyleSheet("color: orange;")
        self.is_previewing = True
        
        # 预览时禁用摄像头切换
        self.camera_selector.setEnabled(False)

    def stop_preview(self):
        if self.preview_thread:
            self.preview_thread.stop()
            self.preview_thread = None
        
        self.btn_preview.setText("预览")
        self.lbl_rec_status.setText("就绪")
        self.lbl_rec_status.setStyleSheet("color: gray;")
        self.lbl_fps.setText("FPS: --")
        self.is_previewing = False
        
        self.camera_selector.setEnabled(True)

    def toggle_recording(self):
        """ 切换正式检查录制模式 """
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """ 启动正式检查 (录制视频+数据) """
        if not self.current_patient:
            InfoBar.warning(title='警告', content="请先在患者列表选择一位患者", parent=self)
            return

        # 如果正在预览，先停止
        if self.is_previewing:
            self.stop_preview()

        p_id, p_name = self.current_patient
        safe_name = "".join([c for c in p_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        folder_name = f"{p_id}_{safe_name}"
        
        save_dir = os.path.join("Data", folder_name, "Spontaneous")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = os.path.join(save_dir, f"{timestamp}.mkv")
        
        # 获取选中的摄像头ID并设置到camera_thread
        cam_id = self._get_selected_camera_id()
        self.camera_thread.camera_id = cam_id
        self.camera_thread.start(save_path=video_path)
        
        self.btn_start.setText("停止检查")
        try:
            self.btn_start.setIcon(FluentIcon.PAUSE)
        except AttributeError:
            self.btn_start.setIcon(FluentIcon.CLOSE)
            
        self.lbl_rec_status.setText(f"REC: {os.path.basename(video_path)}")
        self.lbl_rec_status.setStyleSheet("color: red; font-weight: bold;")
        self.is_recording = True
        
        # 录制时禁用预览和摄像头切换
        self.btn_preview.setEnabled(False)
        self.camera_selector.setEnabled(False)
        
        InfoBar.success(title='开始录制', content=f"数据保存至: {save_dir}", parent=self)

    def stop_recording(self):
        self.camera_thread.stop()
        self.btn_start.setText("启动检查")
        self.btn_start.setIcon(FluentIcon.CAMERA)
        self.video_label.setText("检查已结束")
        self.lbl_rec_status.setText("已停止")
        self.lbl_rec_status.setStyleSheet("color: gray;")
        self.lbl_fps.setText("FPS: --")
        self.is_recording = False
        
        # 恢复控件
        self.btn_preview.setEnabled(True)
        self.camera_selector.setEnabled(True)

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

    @Slot(float)
    def update_fps(self, fps):
        self.lbl_fps.setText(f"FPS: {fps:.1f}")

    def closeEvent(self, event):
        if self.is_previewing:
            self.stop_preview()
        if self.is_recording:
            self.stop_recording()
        super().closeEvent(event)

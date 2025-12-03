import os
import glob
import pandas as pd
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSplitter, QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize
from qfluentwidgets import (SubtitleLabel, PushButton, FluentIcon, CardWidget, 
                            InfoBar, ComboBox, MessageBox, TransparentToolButton, 
                            BodyLabel, StrongBodyLabel)
import pyqtgraph as pg

from app.core.algorithm.signal import (signal_preprocess, find_turning_points, 
                                       calculate_slopes, identify_nystagmus_patterns)

class RecordCard(CardWidget):
    """ 记录卡片组件 """
    clicked = Signal(str)
    delete_requested = Signal(str)
    
    def __init__(self, csv_path, test_type, filename, parent=None):
        super().__init__(parent)
        self.csv_path = csv_path
        
        # 设置合理的尺寸
        self.setMinimumHeight(100)
        self.setMaximumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 顶部：类型标签
        self.type_label = BodyLabel(f"[{test_type}]", self)
        self.type_label.setStyleSheet("color: #0078D4; font-weight: bold;")
        
        # 文件名（截断过长文件名）
        display_name = filename if len(filename) < 25 else filename[:22] + "..."
        self.name_label = StrongBodyLabel(display_name, self)
        self.name_label.setToolTip(filename)
        
        # 底部：操作按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        
        self.btn_view = PushButton("查看", self)
        self.btn_view.setFixedHeight(32)
        self.btn_view.clicked.connect(lambda: self.clicked.emit(self.csv_path))
        
        self.btn_delete = TransparentToolButton(FluentIcon.DELETE, self)
        self.btn_delete.setToolTip("删除")
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.csv_path))
        
        bottom_layout.addWidget(self.btn_view, 1)
        bottom_layout.addWidget(self.btn_delete)
        
        layout.addWidget(self.type_label)
        layout.addWidget(self.name_label)
        layout.addStretch(1)
        layout.addLayout(bottom_layout)
        
        # 鼠标悬停效果
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.csv_path)
        super().mousePressEvent(event)

class AnalysisWorker(QThread):
    """ 离线分析线程 """
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, csv_path, axis='horizontal'):
        super().__init__()
        self.csv_path = csv_path
        self.axis = axis
    
    def run(self):
        try:
            df = pd.read_csv(self.csv_path)
            timestamps = df['Timestamp'].values
            pitch_data = df['Pitch'].values
            yaw_data = df['Yaw'].values
            
            eye_angles = yaw_data if self.axis == 'horizontal' else pitch_data
            
            filtered_signal, time = signal_preprocess(
                timestamps, eye_angles,
                highpass_parameter={'cutoff': 0.1, 'fs': 60, 'order': 5},
                lowpass_parameter={'cutoff': 6.0, 'fs': 60, 'order': 5},
                interpolate_ratio=10
            )
            
            turning_points = find_turning_points(filtered_signal, prominence=0.1, distance=150)
            slope_times, slopes = calculate_slopes(time, filtered_signal, turning_points)
            patterns, _, direction, pattern_spv, cv = identify_nystagmus_patterns(
                filtered_signal, time,
                min_time=0.3, max_time=0.8,
                min_ratio=1.4, max_ratio=8.0,
                direction_axis=self.axis
            )
            
            result = {
                'timestamps': timestamps,
                'eye_angles': eye_angles,
                'filtered_signal': filtered_signal,
                'time': time,
                'turning_points': turning_points,
                'patterns': patterns,
                'direction': direction,
                'spv': pattern_spv,
                'cv': cv,
                'axis': self.axis
            }
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))

class AnalysisInterface(QWidget):
    """ 数据管理与分析界面 """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("AnalysisInterface")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Horizontal, self)
        
        # === 左侧：记录列表 ===
        left_panel = QWidget(self)
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(400)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)
        
        title_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("检查记录", left_panel)
        self.btn_refresh = PushButton(FluentIcon.SYNC, "刷新", left_panel)
        self.btn_refresh.clicked.connect(self.load_records)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.btn_refresh)
        
        # 滚动区域
        scroll_area = QScrollArea(left_panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        scroll_widget = QWidget()
        self.card_layout = QVBoxLayout(scroll_widget)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(scroll_widget)
        
        left_layout.addLayout(title_layout)
        left_layout.addWidget(scroll_area, 1)
        
        # === 右侧：分析结果 ===
        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(12)
        
        control_layout = QHBoxLayout()
        self.result_title = SubtitleLabel("分析结果", right_panel)
        
        self.axis_selector = ComboBox(right_panel)
        self.axis_selector.addItems(["水平 (Yaw)", "垂直 (Pitch)"])
        self.axis_selector.setFixedWidth(150)
        
        self.btn_analyze = PushButton(FluentIcon.PLAY, "分析", right_panel)
        self.btn_analyze.clicked.connect(self.start_analysis)
        self.btn_analyze.setEnabled(False)
        
        control_layout.addWidget(self.result_title)
        control_layout.addStretch(1)
        control_layout.addWidget(self.axis_selector)
        control_layout.addWidget(self.btn_analyze)
        
        self.result_label = BodyLabel("请选择左侧的检查记录", right_panel)
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("color: gray; padding: 15px;")
        
        self.plot_widget = pg.GraphicsLayoutWidget(right_panel)
        self.plot_widget.setBackground('w')
        self.plot_widget.setMinimumSize(600, 400)
        
        right_layout.addLayout(control_layout)
        right_layout.addWidget(self.result_label)
        right_layout.addWidget(self.plot_widget, 1)
        
        # 添加到 Splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        
        main_layout.addWidget(splitter)
        
        self.current_patient = None
        self.current_csv_path = None
        self.analysis_worker = None

    def set_current_patient(self, p_id, p_name):
        self.current_patient = (p_id, p_name)

    def load_records(self):
        """ 加载记录卡片 """
        # 清空
        for i in reversed(range(self.card_layout.count())):
            item = self.card_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        
        if not self.current_patient:
            placeholder = BodyLabel("请先选择患者", self)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: gray; padding: 30px;")
            self.card_layout.addWidget(placeholder)
            return
        
        p_id, p_name = self.current_patient
        safe_name = "".join([c for c in p_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        folder_name = f"{p_id}_{safe_name}"
        
        pattern = os.path.join("Data", folder_name, "**", "*.csv")
        csv_files = glob.glob(pattern, recursive=True)
        
        if not csv_files:
            placeholder = BodyLabel("暂无检查记录\n请前往「实时检查」录制数据", self)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: gray; padding: 30px;")
            self.card_layout.addWidget(placeholder)
            return
        
        # 添加卡片
        for csv_path in sorted(csv_files, reverse=True):
            rel_path = os.path.relpath(csv_path, "Data")
            parts = rel_path.split(os.sep)
            test_type = parts[1] if len(parts) > 1 else "Unknown"
            filename = os.path.splitext(os.path.basename(csv_path))[0]
            
            card = RecordCard(csv_path, test_type, filename, self)
            card.clicked.connect(self.on_record_selected)
            card.delete_requested.connect(self.delete_record)
            
            self.card_layout.addWidget(card)
        
        self.card_layout.addStretch(1)

    def delete_record(self, csv_path):
        filename = os.path.basename(csv_path)
        w = MessageBox('确认删除', f'确定要删除 "{filename}" 吗？\n此操作不可恢复。', self)
        
        if w.exec():
            try:
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                
                video_path = os.path.splitext(csv_path)[0] + ".mkv"
                if os.path.exists(video_path):
                    os.remove(video_path)
                
                InfoBar.success(title='已删除', content="记录删除成功", parent=self)
                self.load_records()
                
                if csv_path == self.current_csv_path:
                    self.current_csv_path = None
                    self.result_label.setText("记录已删除，请选择其他记录")
                    self.plot_widget.clear()
                    self.btn_analyze.setEnabled(False)
                    
            except Exception as e:
                InfoBar.error(title='删除失败', content=str(e), parent=self)

    @Slot(str)
    def on_record_selected(self, csv_path):
        self.current_csv_path = csv_path
        self.result_label.setText(f"已选择: {os.path.basename(csv_path)}")
        self.btn_analyze.setEnabled(True)

    def start_analysis(self):
        if not self.current_csv_path:
            return
        
        axis = 'horizontal' if self.axis_selector.currentIndex() == 0 else 'vertical'
        
        self.result_label.setText("分析中...")
        self.btn_analyze.setEnabled(False)
        
        self.analysis_worker = AnalysisWorker(self.current_csv_path, axis)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    @Slot(dict)
    def on_analysis_finished(self, result):
        self.btn_analyze.setEnabled(True)
        
        direction_str = result['direction'].upper()
        axis_str = "水平" if result['axis'] == 'horizontal' else "垂直"
        self.result_label.setText(
            f"✓ {axis_str}眼震 | 方向: {direction_str} | SPV: {result['spv']:.1f}°/s | "
            f"CV: {result['cv']:.1f}% | 模式数: {len(result['patterns'])}"
        )
        
        self.plot_results(result)

    @Slot(str)
    def on_analysis_error(self, error_msg):
        self.btn_analyze.setEnabled(True)
        self.result_label.setText(f"❌ 分析失败: {error_msg}")

    def plot_results(self, result):
        self.plot_widget.clear()
        
        p1 = self.plot_widget.addPlot(row=0, col=0, title="1. 原始信号 vs 滤波后")
        p2 = self.plot_widget.addPlot(row=1, col=0, title="2. 转折点检测")
        p3 = self.plot_widget.addPlot(row=2, col=0, title="3. 眼震模式 (红=快相, 蓝=慢相)")
        
        # Plot 1
        p1.plot(result['timestamps'], result['eye_angles'], 
               pen=pg.mkPen(color=(200, 200, 200), width=1), name='原始')
        p1.plot(result['time'], result['filtered_signal'], 
               pen=pg.mkPen(color='#FF5252', width=2), name='滤波后')
        p1.setLabel('left', 'Angle', units='°')
        p1.addLegend()
        p1.showGrid(x=True, y=True, alpha=0.3)
        
        # Plot 2
        p2.plot(result['time'], result['filtered_signal'], 
               pen=pg.mkPen(color=(150, 150, 150), width=1, style=Qt.DotLine))
        
        if len(result['turning_points']) > 0:
            p2.plot(result['time'][result['turning_points']], 
                   result['filtered_signal'][result['turning_points']], 
                   pen=None, symbol='o', symbolBrush='r', symbolSize=8)
        
        p2.setLabel('left', 'Angle', units='°')
        p2.showGrid(x=True, y=True, alpha=0.3)
        
        # Plot 3
        p3.plot(result['time'], result['filtered_signal'], 
               pen=pg.mkPen(color=(180, 180, 180), width=1, style=Qt.DashLine))
        
        for pattern in result['patterns']:
            idx = pattern['index']
            if idx > 0 and idx + 1 < len(result['turning_points']):
                tp = result['turning_points']
                idx1, idx2, idx3 = tp[idx-1], tp[idx], tp[idx+1]
                
                if pattern['fast_phase_first']:
                    fast_t = result['time'][idx1:idx2+1]
                    fast_s = result['filtered_signal'][idx1:idx2+1]
                    slow_t = result['time'][idx2:idx3+1]
                    slow_s = result['filtered_signal'][idx2:idx3+1]
                else:
                    slow_t = result['time'][idx1:idx2+1]
                    slow_s = result['filtered_signal'][idx1:idx2+1]
                    fast_t = result['time'][idx2:idx3+1]
                    fast_s = result['filtered_signal'][idx2:idx3+1]
                
                p3.plot(fast_t, fast_s, pen=pg.mkPen(color='#FF5252', width=4))
                p3.plot(slow_t, slow_s, pen=pg.mkPen(color='#448AFF', width=4))
        
        p3.setLabel('left', 'Angle', units='°')
        p3.setLabel('bottom', 'Time', units='s')
        p3.showGrid(x=True, y=True, alpha=0.3)

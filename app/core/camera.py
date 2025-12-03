import cv2
import time
import queue
import threading
import os
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage

from app.core.algorithm.segmentor import MediaPipeEyeExtractor
from app.core.algorithm.estimator import GazeEstimator
from app.core.recorder import DataRecorder

class VideoRecorder:
    """ 独立的视频写入类 """
    def __init__(self, filename, width, height, fps):
        self.filename = filename
        self.fourcc = cv2.VideoWriter_fourcc(*'MJPG') 
        self.writer = cv2.VideoWriter(filename, self.fourcc, fps, (width, height))
        
    def write(self, frame):
        if self.writer.isOpened():
            self.writer.write(frame)
            
    def release(self):
        if self.writer:
            self.writer.release()

class CaptureWorker(QThread):
    """
    采集线程：专注于从摄像头读取与写入磁盘 (Producer)
    目标：1080p @ 120fps
    """
    frame_captured = Signal(object)
    fps_updated = Signal(float) # 新增 FPS 信号
    
    def __init__(self, camera_id=0, save_path=None):
        super().__init__()
        self.camera_id = camera_id
        self.save_path = save_path
        self.is_running = False
        self.recorder = None
        self.fps_real = 0

    def run(self):
        cap = cv2.VideoCapture(self.camera_id)
        # 强制 MJPEG 以支持高帧率
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 120)
        
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"[Camera] Init: {w}x{h} @ {fps}fps")
        
        if self.save_path:
            self.recorder = VideoRecorder(self.save_path, w, h, fps)
            print(f"[Camera] Recording video to {self.save_path}")

        self.is_running = True
        frame_count = 0
        start_time = time.time()
        last_fps_time = start_time

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break
            
            if self.recorder:
                self.recorder.write(frame)
            
            self.frame_captured.emit(frame)
            
            frame_count += 1
            
            # 每 30 帧计算一次 FPS
            if frame_count % 30 == 0:
                now = time.time()
                duration = now - last_fps_time
                if duration > 0:
                    self.fps_real = 30 / duration
                    self.fps_updated.emit(self.fps_real)
                last_fps_time = now

        if self.recorder:
            self.recorder.release()
        cap.release()
        print(f"[Camera] Stopped. Final FPS: {self.fps_real:.1f}")

    def stop(self):
        self.is_running = False
        self.wait()

class CameraThread(QObject):
    """
    主控制器：协调采集与 AI 处理
    """
    frame_received = Signal(QImage)
    eye_roi_received = Signal(QImage)
    gaze_data_received = Signal(float, float, float)
    fps_received = Signal(float) # 转发 FPS 信号
    
    def __init__(self, camera_id=0):
        super().__init__()
        self.camera_id = camera_id
        self.capture_worker = None
        
        self.extractor = MediaPipeEyeExtractor()
        self.estimator = GazeEstimator()
        self.estimator.load_model()
        
        self.latest_frame = None
        self.processing_lock = threading.Lock()
        self.is_processing = False
        
        self.ai_thread = threading.Thread(target=self._ai_loop, daemon=True)
        self.ai_running = False
        
        self.data_recorder = None

    def start(self, save_path=None):
        # 1. 启动视频采集
        self.capture_worker = CaptureWorker(self.camera_id, save_path)
        self.capture_worker.frame_captured.connect(self._on_frame_captured)
        self.capture_worker.fps_updated.connect(self.fps_received) # 连接信号
        self.capture_worker.start()
        
        # 2. 启动数据记录 (如果有视频路径，则同名保存 csv)
        if save_path:
            csv_path = os.path.splitext(save_path)[0] + ".csv"
            self.data_recorder = DataRecorder(csv_path)
            self.data_recorder.start()
        
        # 3. 启动 AI 线程
        self.ai_running = True
        if not self.ai_thread.is_alive():
            self.ai_thread = threading.Thread(target=self._ai_loop, daemon=True)
            self.ai_thread.start()

    def stop(self):
        self.ai_running = False
        
        if self.capture_worker:
            self.capture_worker.stop()
            self.capture_worker = None
            
        if self.data_recorder:
            self.data_recorder.stop()
            self.data_recorder = None
        
        # AI 线程可能还在阻塞等待，这里不需要强制join，让它自然结束即可
        # if self.ai_thread.is_alive():
        #     self.ai_thread.join(timeout=1.0)

    def _on_frame_captured(self, frame):
        with self.processing_lock:
            self.latest_frame = frame

    def _ai_loop(self):
        start_time = time.time()
        
        while self.ai_running:
            frame = None
            with self.processing_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                    self.latest_frame = None
            
            if frame is None:
                time.sleep(0.001)
                continue
                
            timestamp = time.time() - start_time
            
            # AI Pipeline
            results, eye_roi = self.extractor.process(frame)
            
            pitch, yaw = 0.0, 0.0
            if eye_roi is not None:
                pitch, yaw = self.estimator.predict(eye_roi)
                
                rgb_roi = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_roi.shape
                qt_roi = QImage(rgb_roi.data, w, h, ch * w, QImage.Format_RGB888)
                self.eye_roi_received.emit(qt_roi.copy())
            
            # 记录数据
            if self.data_recorder:
                self.data_recorder.write(timestamp, pitch, yaw)
            
            self.gaze_data_received.emit(timestamp, pitch, yaw)
            
            # UI Display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            qt_image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
            self.frame_received.emit(qt_image.copy())

import cv2
import time
import threading
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

class PreviewThread(QThread):
    """
    预览线程：只显示画面，不录制，不推理
    用于在检查前调整摄像头位置
    """
    frame_received = Signal(QImage)
    fps_updated = Signal(float)
    
    def __init__(self, camera_id=0):
        super().__init__()
        self.camera_id = camera_id
        self.is_running = False

    def run(self):
        cap = cv2.VideoCapture(self.camera_id)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 120)
        
        if not cap.isOpened():
            print(f"[Preview] Cannot open camera {self.camera_id}")
            return
            
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"[Preview] Camera {self.camera_id}: {w}x{h} @ {fps}fps")
        
        self.is_running = True
        frame_count = 0
        start_time = time.time()
        last_fps_time = start_time

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 只发送画面，不做其他处理
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h_frame, w_frame, ch = rgb_frame.shape
            qt_image = QImage(rgb_frame.data, w_frame, h_frame, ch * w_frame, QImage.Format_RGB888)
            self.frame_received.emit(qt_image.copy())
            
            frame_count += 1
            if frame_count % 30 == 0:
                now = time.time()
                duration = now - last_fps_time
                if duration > 0:
                    fps_real = 30 / duration
                    self.fps_updated.emit(fps_real)
                last_fps_time = now

        cap.release()
        print(f"[Preview] Stopped")

    def stop(self):
        self.is_running = False
        self.wait()

def enumerate_cameras(max_check=5):
    """
    扫描系统中所有可用的摄像头
    返回可用的摄像头 ID 列表
    """
    available = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available


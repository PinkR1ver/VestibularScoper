import torch
import numpy as np
import cv2
import os
import scipy.signal
from collections import deque
from PySide6.QtCore import QObject

# 尝试导入真实模型定义
try:
    from app.core.algorithm.model import SwinUNet
except ImportError:
    print("[Warning] Could not import SwinUNet from app.core.algorithm.model")
    SwinUNet = None

class SignalProcessor:
    """
    Applies filtering to smooth gaze data (Median + Low-pass).
    Ported from gui_visualizer.py
    """
    def __init__(self, fps=60.0, low_pass_cutoff=8.0, buffer_size=15):
        self.fps = fps
        self.nyquist = fps / 2.0
        self.low_pass_cutoff = low_pass_cutoff
        self.buffer_size = buffer_size
        
        # 我们需要保持一个滑动窗口来实时滤波
        # 注意：scipy.signal.filtfilt 是双向滤波，需要未来数据，这在离线处理时很好，
        # 但在实时处理时会有延迟。这里我们使用 lfilter 或仅对当前窗口做简单平滑。
        # 为了实时性，我们使用一个简单的滑动平均或指数平滑，或者小窗口的中值滤波。
        
        # 存储最近 N 个预测值 (Pitch, Yaw)
        self.history = deque(maxlen=buffer_size)
        
        # 滤波器状态 (如果使用 lfilter)
        self.b, self.a = scipy.signal.butter(2, min(low_pass_cutoff, self.nyquist - 0.1) / self.nyquist, btype='low')
        self.zi = scipy.signal.lfilter_zi(self.b, self.a) * 0
        self.zi = np.array([self.zi]*2).T # 为两个通道 (Pitch, Yaw) 准备状态

    def process_realtime(self, pitch, yaw):
        """ 实时滤波处理单帧数据 """
        self.history.append([pitch, yaw])
        
        if len(self.history) < 3:
            return pitch, yaw
            
        data = np.array(self.history)
        
        # 1. 简单的中值滤波去除尖峰 (Median Filter)
        # 取最近3帧的中值
        med_pitch = np.median(data[-3:, 0])
        med_yaw = np.median(data[-3:, 1])
        
        # 2. 低通滤波 (Low-pass)
        # 为了避免 lfilter 的状态管理复杂性，这里简化为加权移动平均 (EMA)
        # 或者使用简单的 Alpha 滤波: y[n] = α * x[n] + (1-α) * y[n-1]
        alpha = 0.3
        if not hasattr(self, 'last_smooth'):
            self.last_smooth = np.array([med_pitch, med_yaw])
        
        smoothed = alpha * np.array([med_pitch, med_yaw]) + (1 - alpha) * self.last_smooth
        self.last_smooth = smoothed
        
        return smoothed[0], smoothed[1]

class GazeEstimator(QObject):
    """
    视线估计器：负责加载模型并进行推理
    支持 Apple Silicon (MPS) / NVIDIA (CUDA) / CPU 自动切换
    """
    def __init__(self, model_path="model/checkpoint_best.pth"):
        super().__init__()
        self.device = self._select_device()
        self.model = None
        self.model_path = model_path
        self.is_loaded = False
        
        # 初始化滤波器
        self.processor = SignalProcessor(fps=30.0) # AI 处理帧率可能只有30fps
        
    def _select_device(self):
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            print("[GazeEstimator] Using Apple MPS (Metal Performance Shaders) acceleration.")
            return torch.device("mps")
        elif torch.cuda.is_available():
            print(f"[GazeEstimator] Using NVIDIA CUDA acceleration: {torch.cuda.get_device_name(0)}")
            return torch.device("cuda")
        else:
            print("[GazeEstimator] Using CPU fallback.")
            return torch.device("cpu")

    def load_model(self):
        """ 加载模型权重 """
        if not os.path.exists(self.model_path):
            print(f"[Error] Model checkpoint not found at {self.model_path}")
            return False
            
        if SwinUNet is None:
            print("[Error] SwinUNet class is missing.")
            return False

        try:
            print(f"[GazeEstimator] Loading model from {self.model_path}...")
            # 初始化模型结构
            self.model = SwinUNet(
                img_size=(36, 60),
                in_chans=3,
                embed_dim=96,
                depths=[2, 2, 2],
                num_heads=[3, 6, 12],
                window_size=7,
                drop_rate=0.1
            )
            
            # 加载权重
            checkpoint = torch.load(self.model_path, map_location=self.device)
            
            state_dict = checkpoint
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            
            # 移除 DDP 前缀
            new_state_dict = {}
            for k, v in state_dict.items():
                if k.startswith('module.'):
                    new_state_dict[k[7:]] = v
                else:
                    new_state_dict[k] = v
                    
            self.model.load_state_dict(new_state_dict, strict=False)
            self.model.to(self.device)
            self.model.eval()
            
            self.is_loaded = True
            print(f"[GazeEstimator] Model loaded successfully on {self.device}")
            return True
        except Exception as e:
            print(f"[Error] Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def predict(self, eye_roi):
        """
        推理单帧眼部图像
        Args:
            eye_roi: np.array (H, W, 3) RGB image
        Returns:
            pitch, yaw (degrees)
        """
        if not self.is_loaded or eye_roi is None:
            return 0.0, 0.0

        try:
            # 预处理: Resize 36x60 -> Normalize -> Tensor
            input_img = cv2.resize(eye_roi, (60, 36)) 
            input_img = input_img.astype(np.float32) / 255.0
            input_img = (input_img - 0.5) / 0.5 # Normalize [-1, 1]
            
            # HWC -> CHW -> Batch
            input_tensor = torch.from_numpy(input_img).permute(2, 0, 1).unsqueeze(0).to(self.device)

            # 推理
            with torch.no_grad():
                output = self.model(input_tensor)
                vec = output.cpu().numpy()[0]
            
            # 坐标系转换 (参考 gui_visualizer.py 的 vector_to_pitch_yaw)
            # Gaze Vector (x, y, z) -> Pitch/Yaw
            if len(vec) == 3:
                x, y, z = vec
                # pitch = arcsin(-y)
                # yaw = arctan2(-x, -z)
                pitch = np.arcsin(np.clip(-y, -1.0, 1.0))
                yaw = np.arctan2(-x, -z)
                
                raw_pitch_deg = np.degrees(pitch)
                raw_yaw_deg = np.degrees(yaw)
                
                # 实时滤波
                smooth_p, smooth_y = self.processor.process_realtime(raw_pitch_deg, raw_yaw_deg)
                return smooth_p, smooth_y
                
            return 0.0, 0.0
            
        except Exception as e:
            print(f"Inference error: {e}")
            return 0.0, 0.0

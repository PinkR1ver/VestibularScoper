import cv2
import mediapipe as mp
import numpy as np

class MediaPipeEyeExtractor:
    """ 使用 MediaPipe FaceMesh 提取眼部 ROI """
    
    # 左眼关键点索引 (FaceMesh)
    LEFT_EYE_IDX = [33, 133, 160, 159, 158, 144, 145, 153] # 简化的轮廓
    # 更精确的左眼角点用于裁剪
    LEFT_EYE_OUTER = 33
    LEFT_EYE_INNER = 133
    LEFT_EYE_UPPER = 159
    LEFT_EYE_LOWER = 145

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def process(self, frame):
        """
        处理帧，返回关键点和眼部 ROI
        Args:
            frame: BGR image
        Returns:
            results: MediaPipe results
            eye_roi: Cropped eye image (BGR) or None
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        eye_roi = None
        
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            h, w, _ = frame.shape
            
            # 提取左眼坐标 (归一化 -> 像素坐标)
            p_out = landmarks[self.LEFT_EYE_OUTER]
            p_in = landmarks[self.LEFT_EYE_INNER]
            p_up = landmarks[self.LEFT_EYE_UPPER]
            p_low = landmarks[self.LEFT_EYE_LOWER]
            
            # 计算包围盒
            x_min = min(p_out.x, p_in.x) * w
            x_max = max(p_out.x, p_in.x) * w
            y_min = min(p_up.y, p_low.y) * h
            y_max = max(p_up.y, p_low.y) * h
            
            # 添加 padding
            pad_w = (x_max - x_min) * 0.5
            pad_h = (y_max - y_min) * 0.8
            
            x1 = int(max(0, x_min - pad_w))
            x2 = int(min(w, x_max + pad_w))
            y1 = int(max(0, y_min - pad_h))
            y2 = int(min(h, y_max + pad_h))
            
            if x2 > x1 and y2 > y1:
                eye_roi = frame[y1:y2, x1:x2].copy()
                
        return results, eye_roi


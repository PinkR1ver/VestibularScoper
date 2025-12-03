import csv
import time
import os

class DataRecorder:
    """ 
    实时数据记录器 
    格式: timestamp(s), pitch(deg), yaw(deg)
    """
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = None
        self.writer = None
        self.is_running = False
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    def start(self):
        # 打开文件并写入表头
        self.file = open(self.filepath, 'w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(["Timestamp", "Pitch", "Yaw"])
        self.file.flush()
        self.is_running = True

    def write(self, timestamp, pitch, yaw):
        if self.is_running and self.writer:
            self.writer.writerow([f"{timestamp:.4f}", f"{pitch:.2f}", f"{yaw:.2f}"])
            self.file.flush()

    def stop(self):
        self.is_running = False
        if self.file:
            self.file.close()
            self.file = None

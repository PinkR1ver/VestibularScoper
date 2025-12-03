"""
Nystagmus Signal Processing & Analysis Module
基于 pvestibular.py 和 hit_utils.py 的核心算法
"""

import numpy as np
import scipy.signal as signal

def butter_highpass_filter(data, cutoff, fs, order=5):
    """
    零相位高通巴特沃斯滤波器
    用于去除低频漂移
    """
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    
    if normal_cutoff >= 1:
        return data
    
    b, a = signal.butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = signal.filtfilt(b, a, data, padlen=min(len(data)-1, 3*(max(len(b), len(a))-1)))
    return filtered_data

def butter_lowpass_filter(data, cutoff, fs, order=5):
    """
    零相位低通巴特沃斯滤波器
    用于平滑信号
    """
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    
    if normal_cutoff >= 1:
        return data
    
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    filtered_data = signal.filtfilt(b, a, data, padlen=min(len(data)-1, 3*(max(len(b), len(a))-1)))
    return filtered_data

def signal_preprocess(timestamps, eye_angles,
                     highpass_parameter={'cutoff': 0.1, 'fs': 60, 'order': 5},
                     lowpass_parameter={'cutoff': 6.0, 'fs': 60, 'order': 5},
                     window_size=0, interpolate_ratio=10):
    """
    信号预处理流程：高通 -> 低通 -> 插值
    
    Args:
        timestamps: 时间序列
        eye_angles: 眼动角度数据 (Pitch 或 Yaw)
        highpass_parameter: 高通滤波参数
        lowpass_parameter: 低通滤波参数
        window_size: 移动平均窗口 (可选)
        interpolate_ratio: 插值倍率
    
    Returns:
        filtered_signal: 处理后的信号
        time: 对应的时间序列
    """
    if len(eye_angles) == 0 or len(timestamps) == 0:
        return np.array([]), np.array([])
    
    min_len = min(len(timestamps), len(eye_angles))
    timestamps = timestamps[:min_len]
    eye_angles = eye_angles[:min_len]
    
    # 1. 高通滤波 (去直流漂移)
    signal_filtered = butter_highpass_filter(eye_angles, **highpass_parameter)
    
    # 2. 低通滤波 (去噪)
    signal_filtered = butter_lowpass_filter(signal_filtered, **lowpass_parameter)
    
    # 3. 插值 (提高分辨率)
    signal_filtered = signal.resample(signal_filtered, int(len(eye_angles) * interpolate_ratio))
    
    # 4. 生成新的时间序列
    time = np.linspace(timestamps[0], timestamps[-1], len(signal_filtered))
    
    return signal_filtered, time

def find_turning_points(signal_data, prominence=0.1, distance=150):
    """
    检测信号的转折点 (peaks & valleys)
    
    Args:
        signal_data: 信号数据
        prominence: 峰值显著性
        distance: 峰值间最小距离
    
    Returns:
        turning_points: 转折点索引数组
    """
    peaks, _ = signal.find_peaks(signal_data, prominence=prominence, distance=distance)
    valleys, _ = signal.find_peaks(-signal_data, prominence=prominence, distance=distance)
    
    turning_points = np.sort(np.concatenate([peaks, valleys]))
    return turning_points

def calculate_slopes(time, signal_data, turning_points):
    """
    计算相邻转折点之间的斜率 (速度)
    
    Args:
        time: 时间序列
        signal_data: 信号数据
        turning_points: 转折点索引
    
    Returns:
        slope_times: 斜率对应的时间点
        slopes: 斜率数组 (°/s)
    """
    slopes = []
    slope_times = []
    
    for i in range(len(turning_points) - 1):
        idx1 = turning_points[i]
        idx2 = turning_points[i + 1]
        
        delta_pos = signal_data[idx2] - signal_data[idx1]
        delta_time = time[idx2] - time[idx1]
        
        if delta_time > 0:
            slope = delta_pos / delta_time
            slopes.append(slope)
            slope_times.append((time[idx1] + time[idx2]) / 2)
    
    return np.array(slope_times), np.array(slopes)

def identify_nystagmus_patterns(signal_data, time, min_time=0.3, max_time=0.8,
                                min_ratio=1.4, max_ratio=8.0, direction_axis='horizontal'):
    """
    识别眼震模式 (快相 + 慢相)
    
    Args:
        signal_data: 滤波后的信号
        time: 时间序列
        min_time, max_time: 快/慢相时长阈值
        min_ratio, max_ratio: 快相/慢相速度比阈值
        direction_axis: 分析轴向 ('horizontal' or 'vertical')
    
    Returns:
        patterns: 识别出的眼震模式列表
        filtered_patterns: 经过筛选的模式
        direction: 眼震方向 ('left', 'right', 'up', 'down')
        pattern_spv: 慢相平均速度 (°/s)
        cv: 变异系数 (%)
    """
    # 检测转折点
    turning_points = find_turning_points(signal_data, prominence=0.1, distance=150)
    
    if len(turning_points) < 3:
        return [], [], "unknown", 0.0, 0.0
    
    # 计算斜率
    slope_times, slopes = calculate_slopes(time, signal_data, turning_points)
    
    # 模式识别
    patterns = []
    for i in range(1, len(turning_points) - 1):
        idx_prev = turning_points[i-1]
        idx_curr = turning_points[i]
        idx_next = turning_points[i+1]
        
        time_seg1 = time[idx_curr] - time[idx_prev]
        time_seg2 = time[idx_next] - time[idx_curr]
        
        slope1 = slopes[i-1] if i-1 < len(slopes) else 0
        slope2 = slopes[i] if i < len(slopes) else 0
        
        # 避免除零
        if abs(slope1) < 1e-6 or abs(slope2) < 1e-6:
            continue
        
        ratio = abs(slope1 / slope2)
        
        # 判断快相在前还是慢相在前
        fast_phase_first = ratio > 1
        
        if fast_phase_first:
            fast_time, slow_time = time_seg1, time_seg2
            fast_slope, slow_slope = abs(slope1), abs(slope2)
        else:
            fast_time, slow_time = time_seg2, time_seg1
            fast_slope, slow_slope = abs(slope2), abs(slope1)
            ratio = 1 / ratio
        
        # 筛选条件
        time_valid = (min_time <= fast_time <= max_time) and (min_time <= slow_time <= max_time)
        ratio_valid = (min_ratio <= ratio <= max_ratio)
        
        if time_valid and ratio_valid:
            patterns.append({
                'index': i,
                'fast_phase_first': fast_phase_first,
                'fast_time': fast_time,
                'slow_time': slow_time,
                'ratio': ratio,
                'slow_slope': slow_slope,
                'fast_slope': fast_slope,
            })
    
    # 判断眼震方向 (基于慢相的方向)
    if patterns:
        slow_slopes = [p['slow_slope'] * (1 if p['fast_phase_first'] else -1) for p in patterns]
        avg_slow_slope = np.mean(slow_slopes)
        
        if direction_axis == 'horizontal':
            direction = 'right' if avg_slow_slope > 0 else 'left'
        else: # vertical
            direction = 'up' if avg_slow_slope > 0 else 'down'
        
        # 计算 SPV (Slow Phase Velocity) - 慢相平均速度
        pattern_spv = np.mean([abs(p['slow_slope']) for p in patterns])
        
        # 计算 CV (Coefficient of Variation) - 变异系数
        spv_values = [abs(p['slow_slope']) for p in patterns]
        cv = (np.std(spv_values) / np.mean(spv_values) * 100) if np.mean(spv_values) > 0 else 0
    else:
        direction = 'unknown'
        pattern_spv = 0.0
        cv = 0.0
    
    return patterns, patterns, direction, pattern_spv, cv


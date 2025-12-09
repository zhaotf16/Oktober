import numpy as np

def lowpass_fourier_3d(vol, cutoff_resolution_A, apix, smooth_edge=True):
    """
    对3D体积数据进行傅里叶空间低通滤波
    
    Args:
        vol: 3D numpy array - 输入体积数据
        cutoff_resolution_A: float - 截止分辨率 (Å)
        apix: float - 像素大小 (Å/像素)
        smooth_edge: bool - 是否使用平滑边缘过渡
    
    Returns:
        numpy array: 滤波后的体积数据
    """
    if cutoff_resolution_A <= 0:
        raise ValueError("Cutoff resolution must be positive")
    
    nz, ny, nx = vol.shape
    
    # 计算归一化截止频率
    cutoff_normalized = apix / cutoff_resolution_A
    
    # 创建频率网格
    freq_z = np.fft.fftfreq(nz).reshape(-1, 1, 1)
    freq_y = np.fft.fftfreq(ny).reshape(1, -1, 1)
    freq_x = np.fft.fftfreq(nx).reshape(1, 1, -1)
    
    # 计算径向频率
    radius = np.sqrt(freq_x**2 + freq_y**2 + freq_z**2)
    
    if smooth_edge:
        # 使用平滑过渡而不是硬截断
        sigma = 0.01  # 过渡宽度
        mask = np.exp(-((radius - cutoff_normalized)**2) / (2 * sigma**2))
        mask[radius <= cutoff_normalized] = 1.0
    else:
        # 硬截断
        mask = radius <= cutoff_normalized
    
    # 应用滤波
    fvol = np.fft.fftn(vol)
    fvol_filtered = fvol * mask
    filtered_vol = np.fft.ifftn(fvol_filtered).real
    
    return filtered_vol.astype(np.float32)


def lowpass_fourier_2d(image, cutoff_resolution_A, apix, smooth_edge=True):
    """
    对2D图像进行傅里叶空间低通滤波（用于显示优化）
    
    Args:
        image: 2D numpy array - 输入图像
        cutoff_resolution_A: float - 截止分辨率 (Å)
        apix: float - 像素大小 (Å/像素)
        smooth_edge: bool - 是否使用平滑边缘过渡
    
    Returns:
        numpy array: 滤波后的图像
    """
    if cutoff_resolution_A <= 0:
        raise ValueError("Cutoff resolution must be positive")
    
    ny, nx = image.shape
    
    # 计算归一化截止频率
    cutoff_normalized = apix / cutoff_resolution_A
    
    # 创建频率网格
    freq_y = np.fft.fftfreq(ny).reshape(-1, 1)
    freq_x = np.fft.fftfreq(nx).reshape(1, -1)
    
    # 计算径向频率
    radius = np.sqrt(freq_x**2 + freq_y**2)
    
    if smooth_edge:
        # 使用平滑过渡
        sigma = min(0.02, cutoff_normalized * 0.1)  # 自适应过渡宽度
        mask = np.exp(-((radius - cutoff_normalized)**2) / (2 * sigma**2))
        mask[radius <= cutoff_normalized] = 1.0
    else:
        # 硬截断
        mask = radius <= cutoff_normalized
    
    # 应用滤波
    fimage = np.fft.fftn(image)
    fimage_filtered = fimage * mask
    filtered_image = np.fft.ifftn(fimage_filtered).real
    
    return filtered_image.astype(np.float32)

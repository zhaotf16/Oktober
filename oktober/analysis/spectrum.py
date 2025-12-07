import numpy as np

def power_spectrum_2d(image_slice, apply_window=True):
    slice_2d = image_slice.copy()
    if apply_window:
        wx = np.hanning(slice_2d.shape[1])
        wy = np.hanning(slice_2d.shape[0])
        window = np.outer(wy, wx)
        slice_2d *= window
    F = np.fft.fft2(slice_2d)
    F_shifted = np.fft.fftshift(F)
    log_power = np.log(1 + np.abs(F_shifted)**2)
    return log_power

def radial_average_2d(power_spectrum, pixel_size_A=1.0):
    """
    对 2D 功率谱进行圆周平均，生成 1D 频谱曲线

    Args:
        power_spectrum (np.ndarray): 2D 对数功率谱
        pixel_size_A (float): 像素尺寸 (Å)

    Returns:
        tuple: (freqs_A, avg_intensity) —— 空间频率（单位 Å）和强度
    """
    ny, nx = power_spectrum.shape
    center_y, center_x = ny // 2, nx // 2

    # 创建坐标网格
    y = np.arange(ny).reshape(-1, 1) - center_y
    x = np.arange(nx).reshape(1, -1) - center_x
    radius = np.sqrt(y**2 + x**2)

    # 最大半径
    max_r = int(np.min([center_y, center_x]))

    # 归一化频率到 1/pixel
    freq_bins_px = np.linspace(0.5 / max_r, 0.5, max_r)  # 从低频到 Nyquist
    bin_edges = np.linspace(0, max_r, max_r + 1)

    # 按半径 bin 统计平均值
    avg_intensity = []
    freqs_px = []

    for i in range(max_r):
        mask = (radius >= bin_edges[i]) & (radius < bin_edges[i + 1])
        values = power_spectrum[mask]
        if len(values) > 0:
            avg_intensity.append(values.mean())
        else:
            avg_intensity.append(0)
        freqs_px.append((bin_edges[i] + bin_edges[i + 1]) / 2)

    # 转换为物理单位：Å
    freqs_A = 1.0 / (np.array(freqs_px) * pixel_size_A + 1e-8)  # 避免除零
    freqs_A = np.clip(freqs_A, 0, None)

    return freqs_A[::-1], np.array(avg_intensity)[::-1]  # 从高分辨率到低分辨率排序


def fsc_curve(vol1, vol2, apix, mask=None):
    """
    计算两个体积之间的 Fourier Shell Correlation (FSC)

    Args:
        vol1, vol2 (np.ndarray): 两个独立重构体积
        apix (float): 像素尺寸 (Å/pixel)
        mask (np.ndarray): 可选掩膜（形状同体积）

    Returns:
        tuple: (resolution_A, fsc_values) —— 分辨率列表和对应相关系数
    """
    assert vol1.shape == vol2.shape, "两个体积必须同尺寸"
    nz, ny, nx = vol1.shape

    # FFT
    F1 = np.fft.fftn(vol1)
    F2 = np.fft.fftn(vol2)

    if mask is not None:
        F1 *= mask
        F2 *= mask

    # 频率坐标
    freq_z = np.fft.fftfreq(nz).reshape(-1, 1, 1)
    freq_y = np.fft.fftfreq(ny).reshape(1, -1, 1)
    freq_x = np.fft.fftfreq(nx).reshape(1, 1, -1)
    radius = np.sqrt(freq_x**2 + freq_y**2 + freq_z**2)

    # 最大归一化频率
    max_freq = 0.5
    num_shells = min(50, int(max_freq * 2 * min(nx, ny, nz)))  # 自适应分壳
    shell_edges = np.linspace(0, max_freq, num_shells + 1)

    fsc_vals = []
    resolution_A = []

    for i in range(num_shells):
        low = shell_edges[i]
        high = shell_edges[i + 1]
        mask_shell = (radius >= low) & (radius < high)

        s11 = np.sum(F1.real[mask_shell] * F2.real[mask_shell] +
                    F1.imag[mask_shell] * F2.imag[mask_shell])
        s1 = np.sum(np.abs(F1[mask_shell])**2)
        s2 = np.sum(np.abs(F2[mask_shell])**2)

        if s1 > 1e-8 and s2 > 1e-8:
            fsc = s11 / np.sqrt(s1 * s2)
        else:
            fsc = 0
        fsc_vals.append(fsc)

        # 中心频率对应的分辨率
        mid_freq = (low + high) / 2
        res = apix / mid_freq if mid_freq > 1e-6 else np.inf
        resolution_A.append(res)

    return np.array(resolution_A), np.array(fsc_vals)

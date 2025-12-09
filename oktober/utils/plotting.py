# utils/plotting.py
import numpy as np

def auto_contrast(img, lower_percentile=1, upper_percentile=99):
    """
    计算自动对比度的 vmin 和 vmax 值
    
    Parameters:
    img: numpy array - 输入图像
    lower_percentile: float - 下百分位数 (默认: 1)
    upper_percentile: float - 上百分位数 (默认: 99)
    
    Returns:
    tuple: (vmin, vmax)
    """
    vmin = np.percentile(img, lower_percentile)
    vmax = np.percentile(img, upper_percentile)
    return vmin, vmax


def apply_contrast(img, vmin, vmax):
    img_normalized = np.clip(img, vmin, vmax)
    if vmax != vmin:
        img_normalized = (img_normalized - vmin) / (vmax - vmin) * 255
    else:
        img_normalized = img.copy()

    return img_normalized


def invert(img):
    if img.dtype == np.uint8:
        return 255 -img
    else:
        return img * -1.0

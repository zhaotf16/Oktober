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

import numpy as np

def lowpass_fourier_3d(vol, cutoff_resolution_A, apix):
    nz, ny, nx = vol.shape
    cutoff_normalized = apix / cutoff_resolution_A
    freq_z = np.fft.fftfreq(nz).reshape(-1, 1, 1)
    freq_y = np.fft.fftfreq(ny).reshape(1, -1, 1)
    freq_x = np.fft.fftfreq(nx).reshape(1, 1, -1)
    radius = np.sqrt(freq_x**2 + freq_y**2 + freq_z**2)
    mask = radius <= cutoff_normalized
    fvol = np.fft.fftn(vol)
    fvol_filtered = fvol * mask
    filtered_vol = np.fft.ifftn(fvol_filtered).real
    return filtered_vol.astype(np.float32)

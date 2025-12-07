import numpy as np

def auto_contrast(img, lower_percentile=1, upper_percentile=99):
    vmin = np.percentile(img, lower_percentile)
    vmax = np.percentile(img, upper_percentile)
    return vmin, vmax

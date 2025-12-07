import numpy as np

def load_mrc(filepath):
    try:
        with mrcfile.open(filepath) as mrc:
            data = mrc.data.astype(np.float32)
            apix = float(mrc.voxel_size.x)
            if apix <= 0:
                apix = 1.0
        return data, apix
    except Exception as e:
        raise IOError(f"Unable to load MRC file {filepath}: {e}")

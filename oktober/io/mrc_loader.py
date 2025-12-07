# oktober/io/mrc_loader.py
import mrcfile
import numpy as np

def load_mrc(filepath):
    """
    加载 MRC 文件，自动判断是否延迟加载
    """
    try:
        with mrcfile.open(filepath) as mrc:
            shape = mrc.data.shape
            if len(shape) != 3:
                raise ValueError("仅支持三维数据")
            apix = float(mrc.voxel_size.x)
            if apix <= 0:
                apix = 1.0

        # 判断大小
        file_size_gb = shape[0] * shape[1] * shape[2] * 4 / (1024**3)
        if file_size_gb > 1.0:
            return filepath, apix  # 返回路径 → 延迟加载
        else:
            with mrcfile.open(filepath) as mrc:
                data = mrc.data.astype(np.float32)
            return data, apix

    except Exception as e:
        raise IOError(f"无法读取 MRC 文件: {e}")

# oktober/io/star_parser.py
"""
读取 RELION .star 文件（支持 RELION 3.1+ 格式）
"""
import pandas as pd


def parse_star_file(star_path):
    """
    解析 RELION .star 文件，返回 DataFrame 表格

    Args:
        star_path (str): STAR 文件路径

    Returns:
        pd.DataFrame: 包含 _rln 开头字段的数据表
    """
    data_lines = []
    in_data_block = False
    headers = []

    with open(star_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('data_'):
                continue
            elif line.startswith('loop_'):
                in_data_block = True
                headers = []
                continue
            elif line.startswith('_rln'):
                if in_data_block:
                    headers.append(line.split()[0])
                continue
            elif line == '' or line.startswith('#'):
                continue
            else:
                if in_data_block and headers:
                    values = line.split()
                    if len(values) == len(headers):
                        data_lines.append(dict(zip(headers, values)))

    df = pd.DataFrame(data_lines)
    
    # 转换数值列
    for col in df.columns:
        if col in ['_rlnCoordinateX', '_rlnCoordinateY', '_rlnAngleRot', '_rlnAngleTilt', '_rlnAnglePsi']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    return df

# oktober/web_viewer.py
"""
Oktober - Web 风格 MRC 查看器（最终可运行版）
✅ 使用 mrcfile 读取 MRC
✅ 右键弹窗选择文件
✅ 自动更新三视图
"""

import os
import sys
import json
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout,
    QWidget, QPushButton, QLabel, QFileDialog
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, QTimer
from PyQt5.QtWebChannel import QWebChannel
import mrcfile
from oktober.utils.plotting import auto_contrast


class ViewerBridge(QObject):
    def __init__(self):
        super().__init__()
        self.data = None
        self.shape = None
        self.apix = 1.0
        self.z_idx = 0
        self.y_idx = 0
        self.x_idx = 0

    @pyqtSlot(result=str)
    def load_mrc_file(self):
        """在 Python 中弹出文件选择框并加载"""
        filepath, _ = QFileDialog.getOpenFileName(
            None, "选择 MRC 文件", "", "MRC Files (*.mrc)"
        )
        print("📄 选中文件:", filepath)
        if not filepath:
            return json.dumps({"success": False, "msg": "取消"})

        try:
            with mrcfile.open(filepath) as mrc:
                print("🔍 Header shape:", mrc.data.shape)
                self.data = mrc.data.astype(np.float32)
                self.shape = self.data.shape
                self.apix = float(mrc.header.cella.x / mrc.header.mx)
                if len(self.shape) != 3:
                    raise ValueError("仅支持三维数据")

            nz, ny, nx = self.shape
            self.z_idx = nz // 2
            self.y_idx = ny // 2
            self.x_idx = nx // 2
            

            print(f"✅ 成功加载: {self.shape}")
            return json.dumps({
                "success": True,
                "shape": list(self.shape),
                "apix": self.apix,
                "msg": f"加载成功: {self.shape}"
            })
        except Exception as e:
            print("❌ 加载失败:", str(e))
            return json.dumps({"success": False, "msg": str(e)})

    @pyqtSlot(int, int, int, result=str)
    def get_slices(self, z, y, x):
        if self.data is None:
            return json.dumps({})

        try:
            slice_xy = self.data[z, :, :]
            slice_yz = self.data[:, y, :]
            slice_zx = self.data[:, :, x]

            vmin, vmax = auto_contrast(slice_xy)
            print(vmin, vmax)
            def normalize(img):
                if vmax > vmin:
                    return ((np.clip(img, vmin, vmax) - vmin) / (vmax - vmin) * 255).astype(np.uint8)
                else:
                    return np.zeros_like(img, dtype=np.uint8)

            img_xy = normalize(slice_xy)
            img_yz = normalize(slice_yz)
            img_zx = normalize(slice_zx)

            import base64
            xy_b64 = base64.b64encode(img_xy.tobytes()).decode('utf-8')
            yz_b64 = base64.b64encode(img_yz.tobytes()).decode('utf-8')
            zx_b64 = base64.b64encode(img_zx.tobytes()).decode('utf-8')

            return json.dumps({
                "success": True,
                "xy": {"data": xy_b64, "width": img_xy.shape[1], "height": img_xy.shape[0]},
                "yz": {"data": yz_b64, "width": img_yz.shape[1], "height": img_yz.shape[0]},
                "zx": {"data": zx_b64, "width": img_zx.shape[1], "height": img_zx.shape[0]},
                "indices": {"z": z, "y": y, "x": x}
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
        print(f"📤 发送图像: xy={len(xy_b64)}, yz={len(yz_b64)}, zx={len(zx_b64)}")


class WebViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌐 Oktober - Web 风格 MRC 查看器")
        self.setGeometry(100, 100, 1600, 900)

        self.init_ui()

    def init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = ViewerBridge()

        self.channel.registerObject('viewer', self.bridge)
        self.view.page().setWebChannel(self.channel)

        # 加载本地网页
        html_path = os.path.join(os.path.dirname(__file__), 'web', 'index.html')
        self.view.load(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.view)
        self.setCentralWidget(container)

        test_btn = QPushButton("🧪 测试通信")
        test_btn.clicked.connect(self.test_bridge)
        layout.addWidget(test_btn)
    def test_bridge(self):
        try:
            # 直接调用 bridge 方法
            result = self.bridge.load_mrc_file()
            print("✅ Python 调用 load_mrc_file() 返回:", result)

            # 再试试 get_slices
            if hasattr(self.bridge, 'data') and self.bridge.data is not None:
                s = self.bridge.get_slices(0, 0, 0)
                print("✅ 获取切片成功，长度:", len(s))
            else:
                print("⚠️ 数据未加载，跳过 get_slices")
        except Exception as e:
            print("❌ 调用失败:", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebViewer()
    window.show()
    sys.exit(app.exec_())

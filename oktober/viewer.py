# oktober/viewer.py
"""
OktoberViewer - 最终稳定版 MRC 查看器
支持大/小文件自动切换模式 | 可视化专业 | 用户体验优秀
"""

from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QSlider, QDoubleSpinBox,
    QCheckBox, QFileDialog, QDialog, QVBoxLayout as QVBoxLayoutDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import mrcfile
import numpy as np

# 内部模块导入
from oktober.io.mrc_loader import load_mrc
from oktober.processing.filters import lowpass_fourier_3d
from oktober.analysis.spectrum import power_spectrum_2d, fsc_curve
from oktober.utils.plotting import auto_contrast
from oktober.io.star_parser import parse_star_file


class OktoberViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌤️ Oktober - MRC 可视化平台")
        self.setGeometry(100, 100, 1400, 900)

        # 应用柔和渐变风格
        self.setStyleSheet(self._get_light_gradient_style())

        self.data = None           # 全量数据（小文件）
        self.mrc_path = None       # 大文件路径（延迟加载）
        self.apix = 1.0
        self.star_data = None
        self.data_shape = None

        self.init_ui()

    def _get_light_gradient_style(self):
        """返回浅色渐变风格样式表 (QSS)"""
        return """
            QMainWindow, QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0,
                    x2: 0, y2: 1,
                    stop: 0 #f0f5ff,
                    stop: 1 #e6f2ff
                );
                color: #2c3e50;
                font-family: "Segoe UI", sans-serif;
            }

            QPushButton {
                background-color: #ffffff;
                border: 1px solid #bdc7d8;
                border-radius: 10px;
                padding: 8px 16px;
                min-height: 36px;
                color: #4a6fa5;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #edf4ff;
                border-color: #9ab8e0;
                color: #3a5a80;
            }
            QPushButton:pressed {
                background-color: #dde7f5;
            }

            QLabel {
                color: #34495e;
                font-size: 13px;
                font-weight: 500;
                padding: 2px;
            }

            QSlider::handle {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
                            stop:0 #ffffff, stop:1 #dce6f5);
                border: 1px solid #a0bae0;
                width: 18px;
                margin: -3px 0;
                border-radius: 9px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #d0ddee;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #7aa0e0, stop:1 #5a8ad8);
                border-radius: 3px;
            }

            QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #bdc7d8;
                border-radius: 6px;
                padding: 4px;
                min-height: 32px;
                color: #2c3e50;
            }

            QCheckBox {
                spacing: 8px;
                color: #34495e;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                background: #ffffff;
                border: 1px solid #a0bae0;
            }
            QCheckBox::indicator:checked {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
                            stop:0 #5a8ad8, stop:1 #3a6fb0);
            }

            QToolTip {
                background-color: #1f2937;
                color: #ffffff;
                border: none;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 12px;
            }

            QScrollBar:vertical {
                width: 10px;
                background: #f0f5ff;
            }
            QScrollBar::handle:vertical {
                background: #a0bae0;
                border-radius: 5px;
            }
        """

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # === 控制区顶部 ===
        top_layout = QHBoxLayout()

        self.open_btn = QPushButton("📂 打开 MRC 文件")
        self.open_btn.clicked.connect(self.load_mrc_file)

        self.load_star_btn = QPushButton("🟩 加载 STAR 文件")
        self.load_star_btn.clicked.connect(self.load_star_file)

        self.info_label = QLabel("未加载文件")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #d0ddee;
            border-radius: 6px;
            padding: 8px 12px;
            color: #2c3e50;
            font-weight: 500;
            font-size: 13px;
        """)

        top_layout.addWidget(self.open_btn)
        top_layout.addWidget(self.load_star_btn)
        top_layout.addWidget(self.info_label, stretch=1)
        main_layout.addLayout(top_layout)

        # === 参数设置行 ===
        param_layout = QHBoxLayout()

        self.apix_spinbox = QDoubleSpinBox()
        self.apix_spinbox.setRange(0.01, 10.0)
        self.apix_spinbox.setValue(1.0)
        self.apix_spinbox.valueChanged.connect(self.on_param_change)
        param_layout.addWidget(QLabel("📏 像素尺寸 (Å):"))
        param_layout.addWidget(self.apix_spinbox)

        self.resolution_spinbox = QDoubleSpinBox()
        self.resolution_spinbox.setRange(5.0, 50.0)
        self.resolution_spinbox.setValue(20.0)
        self.resolution_spinbox.valueChanged.connect(self.on_param_change)
        param_layout.addWidget(QLabel("⚡ 截止分辨率 (Å):"))
        param_layout.addWidget(self.resolution_spinbox)

        self.filter_checkbox = QCheckBox("🌀 启用低通滤波")
        self.filter_checkbox.setChecked(False)
        self.filter_checkbox.stateChanged.connect(self.on_param_change)
        param_layout.addWidget(self.filter_checkbox)

        self.btn_fsc = QPushButton("🔬 计算 FSC")
        self.btn_fsc.clicked.connect(self.compute_fsc)
        param_layout.addWidget(self.btn_fsc)

        param_layout.addStretch()
        main_layout.addLayout(param_layout)

        # === 图像画布 ===
        self.init_figure_canvas()
        main_layout.addWidget(self.canvas, stretch=1)

        # === 滑动条控制 ===
        slider_layout = QHBoxLayout()
        self.slider_z = QSlider(Qt.Horizontal)
        self.slider_y = QSlider(Qt.Horizontal)
        self.slider_x = QSlider(Qt.Horizontal)

        for label, slider in [("Z (XY):", self.slider_z),
                              ("Y (YZ):", self.slider_y),
                              ("X (ZX):", self.slider_x)]:
            slider_layout.addWidget(QLabel(label))
            slider_layout.addWidget(slider, 1)

        self.slider_z.valueChanged.connect(self.update_slices)
        self.slider_y.valueChanged.connect(self.update_slices)
        self.slider_x.valueChanged.connect(self.update_slices)

        main_layout.addLayout(slider_layout)

        self.hide_sliders()

    def init_figure_canvas(self):
        """初始化可伸缩画布"""
        self.figure = Figure(facecolor='white', dpi=100, constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()

    def create_subplot_layout(self):
        """
        - XY: 左上主图
        - ZX: 右侧竖直细长条（Z-X）
        - YZ: 下方水平细长条（Y-Z）
        """
        self.figure.clear()

        nz, ny, nx = self.data_shape  # 例如 (200, 2000, 2000)
        # =======================
        # 🔢 计算各视图宽高比
        # =======================

        aspect_xy = nx / ny           # XY: 正方形或矩形
        aspect_xz = nx / nz           # ZX: 细长竖条（X 长，Z 短）
        aspect_yz = ny / nz           # YZ: 细长横条（Y 长，Z 短）

        # =======================
        # 📐 GridSpec 网格划分
        # =======================

        gs = gridspec.GridSpec(
            nrows=2,
            ncols=2,
            figure=self.figure,
            width_ratios=[3, 1.0],      # 左列主导宽度
            height_ratios=[aspect_yz, 1.0],    # 上行主导高度
            wspace=0.00005,
            hspace=0.05,
            #left=0.08, right=0.96,
            #top=0.94, bottom=0.12
        )

        self.ax_xy = self.figure.add_subplot(gs[0, 0])
        self.ax_zx = self.figure.add_subplot(gs[0, 1])
        self.ax_yz = self.figure.add_subplot(gs[1, 0])

        #self.figure.tight_layout()
        # --- 移除 [1,1] 区域使用 ---
        
        # =======================
        # 🧼 清理所有坐标轴
        # =======================

        def clean(ax):
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            for spine in ax.spines.values():
                spine.set_visible(False)

        clean(self.ax_xy)
        clean(self.ax_zx)
        clean(self.ax_yz)

    def update_slices(self):
        if self.data is None and self.mrc_path is None:
            return

        z_idx = self.slider_z.value()
        y_idx = self.slider_y.value()
        x_idx = self.slider_x.value()

        try:
            # --- 重建精确布局 ---
            self.create_subplot_layout()

            # --- 读取三张切片 ---
            if self.mrc_path is not None:
                with mrcfile.open(self.mrc_path) as mrc:
                    slice_xy = mrc.data[z_idx, :, :].copy().astype(np.float32)
                    slice_yz = mrc.data[:, :, x_idx].copy().astype(np.float32)
                    slice_zx = mrc.data[:, y_idx, :].T.copy().astype(np.float32)
            else:
                slice_xy = self.data[z_idx, :, :].astype(np.float32)
                slice_yz = self.data[:, :, x_idx].astype(np.float32)
                slice_zx = self.data[:, y_idx, :].T.astype(np.float32)

            # === 绘图函数 ===
            def plot(ax, img, title, cmap='gray'):
                vmin, vmax = auto_contrast(img)
                im = ax.imshow(img, cmap=cmap, origin='lower', vmin=vmin, vmax=vmax)
                ax.set_title(title, fontsize=8, pad=2, color='#34495e')
                return im

            plot(self.ax_xy, slice_xy, f'XY (Z={z_idx})')
            plot(self.ax_yz, slice_yz, f'YZ (X={x_idx})')
            plot(self.ax_zx, slice_zx, f'ZX (Y={y_idx})')

            #ps = power_spectrum_2d(slice_xy)
            #plot(self.ax_fft, ps, '📊 功率谱', cmap='viridis')

            # === 十字线（仅在 XY 上显示）===
            self.ax_xy.axhline(y=y_idx, color='#4a9eff', alpha=0.6, linewidth=1, linestyle='--')
            self.ax_xy.axvline(x=x_idx, color='#4a9eff', alpha=0.6, linewidth=1, linestyle='--')

            # === 粒子点叠加（略）===

            self.canvas.draw()
            self.canvas.flush_events()

        except Exception as e:
            print(f"更新失败: {e}")


    def load_mrc_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,                        # ✅ 正确的 parent
            "选择 MRC 文件",
            "",
            "MRC Files (*.mrc);;All Files (*)"
        )
        if not filepath:
            return

        try:
            result, apix = load_mrc(filepath)
            short_name = filepath.split('/')[-1]

            if isinstance(result, np.ndarray):
                self.data = result
                self.mrc_path = None
                self.data_shape = self.data.shape
                self.info_label.setText(f"📄 {short_name} | 形状: {self.data_shape}")
            else:
                self.data = None
                self.mrc_path = result
                with mrcfile.open(self.mrc_path) as mrc:
                    self.data_shape = mrc.data.shape
                self.info_label.setText(f"📄 [延迟加载] {short_name} | 形状: {self.data_shape}")

            self.apix = apix
            self.apix_spinbox.setValue(apix)

            nz, ny, nx = self.data_shape
            self.slider_z.setRange(0, nz - 1)
            self.slider_y.setRange(0, ny - 1)
            self.slider_x.setRange(0, nx - 1)
            self.slider_z.setValue(nz // 2)
            self.slider_y.setValue(ny // 2)
            self.slider_x.setValue(nx // 2)

            self.show_sliders()
            self.apply_filter()
            self.update_slices()  # 🔥 关键：立即显示初始切片

        except Exception as e:
            self.info_label.setText(f"❌ 错误: {str(e)}")

    def load_star_file(self):
        if self.data_shape is None:
            self.info_label.setText("⚠️ 请先加载 MRC 文件")
            return

        star_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 STAR 文件",
            "",
            "STAR Files (*.star);;All Files (*)"
        )
        if not star_path:
            return

        try:
            df = parse_star_file(star_path)
            self.star_data = df
            self.info_label.setText(f"🟢 已加载 STAR: {len(df)} 个粒子")
            self.update_slices()
        except Exception as e:
            self.info_label.setText(f"❌ STAR 加载失败: {str(e)}")

    def apply_filter(self):
        if self.data is None or self.mrc_path is not None:
            self.filtered_data = None
            self.filter_checkbox.setEnabled(False)
            return

        if self.filter_checkbox.isChecked():
            cutoff_A = self.resolution_spinbox.value()
            apix = self.apix_spinbox.value()
            self.filtered_data = lowpass_fourier_3d(self.data, cutoff_A, apix)
        else:
            self.filtered_data = self.data.copy()

    def on_param_change(self):
        self.apix = self.apix_spinbox.value()
        self.apply_filter()
        self.update_slices()

    def show_sliders(self):
        self.slider_z.show()
        self.slider_y.show()
        self.slider_x.show()

    def hide_sliders(self):
        self.slider_z.hide()
        self.slider_y.hide()
        self.slider_x.hide()

    def compute_fsc(self):
        if self.data is None:
            self.info_label.setText("⚠️ 请先加载第一个体积")
            return

        filepath2, _ = QFileDialog.getOpenFileName(
            self, "选择第二个 MRC 文件（用于 FSC）", "", "MRC Files (*.mrc)"
        )
        if not filepath2:
            return

        try:
            data2, _ = load_mrc(filepath2)
            if data2.shape != self.data.shape:
                raise ValueError("两个体积必须具有相同尺寸")

            res_A, fsc_vals = fsc_curve(self.data, data2, apix=self.apix_spinbox.value())

            dialog = QDialog(self)
            dialog.setWindowTitle("📊 FSC 曲线")
            dialog.resize(800, 500)
            layout = QVBoxLayoutDialog(dialog)

            fig = Figure(figsize=(8, 4), dpi=100, facecolor='white')
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.plot(res_A, fsc_vals, 'b-', lw=2, label='FSC')
            ax.axhline(0.143, color='r', linestyle='--', label='0.143 标准')
            ax.axhline(0.5, color='g', linestyle='--', label='0.5 标准')
            ax.set_xlabel('分辨率 (Å)')
            ax.set_ylabel('FSC')
            ax.set_title('Fourier Shell Correlation')
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_xlim(right=0, left=max(res_A))

            layout.addWidget(canvas)
            dialog.setLayout(layout)
            dialog.show()

            self.fsc_dialog = dialog

        except Exception as e:
            self.info_label.setText(f"❌ FSC 计算失败: {str(e)}")

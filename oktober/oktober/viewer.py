from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QSlider, QDoubleSpinBox, QCheckBox, QFileDialog
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from oktober.io.mrc_loader import load_mrc
from oktober.processing.filters import lowpass_fourier_3d
from oktober.analysis.fft import power_spectrum_2d
from oktober.utils.plotting import auto_contrast


class OktoberViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MRC 文件查看器 - 模块化版本")
        self.setGeometry(100, 100, 1600, 800)

        self.data = None
        self.filtered_data = None
        self.apix = 1.0

        self.star_data = None

        self.init_ui()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        top_layout = QHBoxLayout()
        self.open_btn = QPushButton("打开 MRC 文件")
        self.open_btn.clicked.connect(self.load_mrc_file)
        self.info_label = QLabel("未加载文件")
        self.load_star_btn = QPushButton("📊 加载 STAR 文件")
        self.load_star_btn.clicked.connect(self.load_star_file)

        top_layout.addWidget(self.open_btn)
        top_layout.addWidget(self.info_label)
        top_layout.insertWidget(1, self.load_star_btn)  # 插入到 open_btn 后面
        main_layout.addLayout(top_layout)

        param_layout = QHBoxLayout()

        self.apix_spinbox = QDoubleSpinBox()
        self.apix_spinbox.setRange(0.01, 10.0)
        self.apix_spinbox.setValue(1.0)
        self.apix_spinbox.valueChanged.connect(self.on_param_change)
        apix_label = QLabel("像素尺寸 (Å):")

        self.resolution_spinbox = QDoubleSpinBox()
        self.resolution_spinbox.setRange(5.0, 50.0)
        self.resolution_spinbox.setValue(20.0)
        self.resolution_spinbox.valueChanged.connect(self.on_param_change)
        res_label = QLabel("低通截止 (Å):")

        self.filter_checkbox = QCheckBox("启用低通滤波")
        self.filter_checkbox.setChecked(False)
        self.filter_checkbox.stateChanged.connect(self.on_param_change)

        param_layout.addWidget(apix_label)
        param_layout.addWidget(self.apix_spinbox)
        param_layout.addWidget(res_label)
        param_layout.addWidget(self.resolution_spinbox)
        param_layout.addWidget(self.filter_checkbox)
        param_layout.addStretch()

        main_layout.addLayout(param_layout)

        self.figure = Figure(figsize=(16, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)
        self.axes = self.figure.subplots(1, 4)
        self.ax_xy, self.ax_yz, self.ax_zx, self.ax_fft = self.axes

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
        self.figure.subplots_adjust(wspace=0.4)

    def load_mrc_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择 MRC 文件", "", "MRC Files (*.mrc);;All Files (*)"
        )
        if not filepath:
            return

        try:
            data, apix = load_mrc(filepath)
            self.data = data
            self.apix = apix
            self.apix_spinbox.setValue(apix)

            shape = self.data.shape
            if len(shape) != 3:
                raise ValueError("仅支持三维数据")

            self.info_label.setText(f"文件: {filepath.split('/')[-1]} | 形状: {shape}")

            self.slider_z.setRange(0, shape[0] - 1)
            self.slider_y.setRange(0, shape[1] - 1)
            self.slider_x.setRange(0, shape[2] - 1)
            self.slider_z.setValue(shape[0] // 2)
            self.slider_y.setValue(shape[1] // 2)
            self.slider_x.setValue(shape[2] // 2)

            self.show_sliders()
            self.apply_filter()
            self.update_slices()

        except Exception as e:
            self.info_label.setText(f"错误: {str(e)}")

    def load_star_file(self):
        """加载 RELION .star 文件并显示粒子坐标"""
        if self.data is None:
            self.info_label.setText("⚠️ 请先加载 MRC 文件")
            return

        star_path, _ = QFileDialog.getOpenFileName(
            self, "选择 STAR 文件", "", "STAR Files (*.star);;All Files (*)"
        )
        if not star_path:
            return

        try:
            from oktober.io.star_parser import parse_star_file
            df = parse_star_file(star_path)
            self.star_data = df
            self.info_label.setText(f"📄 已加载 STAR: {len(df)} 个粒子")
            self.update_slices()  # 刷新视图以显示粒子点
        except Exception as e:
            self.info_label.setText(f"❌ STAR 加载失败: {str(e)}")

        def apply_filter(self):
            if self.data is None:
                return
            if self.filter_checkbox.isChecked():
                cutoff_A = self.resolution_spinbox.value()
                apix = self.apix_spinbox.value()
                self.filtered_data = lowpass_fourier_3d(self.data, cutoff_A, apix)
            else:
                self.filtered_data = self.data.copy()

    def update_slices(self):
        if self.filtered_data is None:
            return

        z_idx = self.slider_z.value()
        y_idx = self.slider_y.value()
        x_idx = self.slider_x.value()

        slice_xy = self.filtered_data[z_idx, :, :]
        slice_yz = self.filtered_data[:, y_idx, :]
        slice_zx = self.filtered_data[:, :, x_idx].T

        for ax in self.axes:
            ax.clear()

        def plot(ax, img, title, cmap='gray'):
            vmin, vmax = auto_contrast(img)
            ax.imshow(img, cmap=cmap, origin='lower', vmin=vmin, vmax=vmax)
            ax.set_title(title, fontsize=12)
            ax.axis('off')

        plot(self.ax_xy, slice_xy, f'XY 平面 (Z={z_idx})')
        plot(self.ax_yz, slice_yz, f'YZ 平面 (Y={y_idx})')
        plot(self.ax_zx, slice_zx, f'ZX 平面 (X={x_idx})')

        if self.star_data is not None and '_rlnCoordinateX' in self.star_data.columns:
        # draw particles if coordniates are given
        coords_df = self.star_data[['_rlnCoordinateX', '_rlnCoordinateY', '_rlnCoordinateZ']].dropna()
        if not coords_df.empty:
            xs = coords_df['_rlnCoordinateX'].values
            ys = coords_df['_rlnCoordinateY'].values
            zs = coords_df['_rlnCoordinateZ'].values

            # 当前切片索引
            z_idx = self.slider_z.value()
            y_idx = self.slider_y.value()
            x_idx = self.slider_x.value()

            # 容差：±2 层以内显示
            TOLERANCE = 2

            # --- XY 平面：显示 Z ≈ z_idx 的点 ---
            mask_xy = np.abs(zs - z_idx) <= TOLERANCE
            if np.any(mask_xy):
                self.ax_xy.scatter(xs[mask_xy], ys[mask_xy], c='red', s=8, alpha=0.7, edgecolors='none')

            # --- YZ 平面：显示 X ≈ x_idx 的点 ---
            mask_yz = np.abs(xs - x_idx) <= TOLERANCE
            if np.any(mask_yz):
                self.ax_yz.scatter(ys[mask_yz], zs[mask_yz], c='cyan', s=8, alpha=0.7, edgecolors='none')

            # --- ZX 平面：显示 Y ≈ y_idx 的点 ---
            mask_zx = np.abs(ys - y_idx) <= TOLERANCE
            if np.any(mask_zx):
                self.ax_zx.scatter(xs[mask_zx], zs[mask_zx], c='magenta', s=8, alpha=0.7, edgecolors='none')

        # draw spectrum
        ps = power_spectrum_2d(slice_xy)
        plot(self.ax_fft, ps, '功率谱 (对数尺度)', cmap='viridis')

        self.figure.suptitle("MRC 正交切片与傅里叶分析", fontsize=14)
        self.canvas.draw()

    def on_param_change(self):
        self.apix = self.apix_spinbox.value()
        self.apply_filter()
        self.update_slices()

    def show_sliders(self):
        self.slider_z.show(); self.slider_y.show(); self.slider_x.show()

    def hide_sliders(self):
        self.slider_z.hide(); self.slider_y.hide(); self.slider_x.hide()

# main.py
import sys
import cv2
import numpy as np
import mrcfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QSizePolicy, QTabWidget,
                            QVBoxLayout, QHBoxLayout, QWidget, QLabel, QStackedWidget, QMessageBox,
                            QSlider, QStatusBar, QSplitter, QAction, QGridLayout, QComboBox,
                            QGroupBox, QSpinBox, QPushButton, QProgressDialog, QCheckBox, QLineEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from oktober.utils.plotting import auto_contrast, apply_contrast
from oktober.processing.filters import lowpass_fourier_2d


# MRCS工作线程类
class MRCSWorker(QThread):
    finished_loading = pyqtSignal(object, object)  # (data, header)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        
    def run(self):
        try:
            with mrcfile.open(self.filename, mode='r') as mrc:
                data = mrc.data.copy()
                header = mrc.header
            self.finished_loading.emit(data, header)
        except Exception as e:
            self.error_occurred.emit(str(e))

class MRCWorker(QThread):
    """MRC文件加载工作线程"""
    progress_updated = pyqtSignal(int)
    finished_loading = pyqtSignal(object, object)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        
    def run(self):
        try:
            self.progress_updated.emit(0)
            
            # 使用 mmap 方式读取大文件
            with mrcfile.open(self.filename, mode='r') as mrc:
                header = mrc.header
                data_shape = mrc.data.shape
                
                # 对于大3D数据，分块读取
                if len(data_shape) == 3 and data_shape[0] > 50:
                    data = self.load_large_volume(mrc, data_shape)
                else:
                    data = mrc.data.copy()
                    self.progress_updated.emit(100)
                
            self.finished_loading.emit(data, header)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def load_large_volume(self, mrc_file, shape):
        """分块加载大体积数据"""
        import numpy as np
        
        nz, ny, nx = shape
        data = np.empty(shape, dtype=mrc_file.data.dtype)
        
        # 分批读取切片
        batch_size = max(1, nz // 100)  # 至少每1%进度更新一次
        for start_z in range(0, nz, batch_size):
            end_z = min(start_z + batch_size, nz)
            
            # 读取一批切片
            data[start_z:end_z] = mrc_file.data[start_z:end_z]
            
            # 更新进度
            progress = int((end_z / nz) * 100)
            self.progress_updated.emit(min(100, progress))  # 留一些给最后处理
        #self.progress_updated.emit(100)
        return data


class MRCViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Oktober")
        self.setGeometry(100, 100, 1000, 700)

        # 数据属性
        self.current_data = None
        self.current_slice = 0
        self.vmin = 0
        self.vmax = 255
        self.invert_contrast = False  # 反转衬度标志
        self.star_data = None  # 存储STAR数据
        self.show_particles = False  # 是否显示粒子
        self.display_filter_enabled = False
        self.display_cutoff = 10.0
        self.selected_particle = None
        self.particle_positions = []  # 缓存粒子位置
        self.mrcs_data = None  # 存储MRCS数据
        self.current_projection_page = 0  # 当前投影页面
        self.projections_per_page = 100  # 每页显示的投影数

        self.display_mode = "tomogram"
        self.edit_mode = False  # 编辑模式开关
        self.pending_new_particle = None  # 待添加的新粒子
        self.has_unsaved_changes = False  # 跟踪是否有未保存的更改

        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.create_menu_bar()
        self.create_central_widget()
        self.create_status_bar()
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('File')
        
        open_action = QAction('Open MRC', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        open_star_action = QAction('Open STAR Coordinates', self)
        open_star_action.setShortcut('Ctrl+Shift+O')
        open_star_action.triggered.connect(self.open_star_file)
        file_menu.addAction(open_star_action)

        # 添加MRCS菜单项
        open_mrcs_action = QAction('Open MRCS Stack', self)
        open_mrcs_action.setShortcut('Ctrl+Shift+M')
        open_mrcs_action.triggered.connect(self.open_mrcs_file)
        file_menu.addAction(open_mrcs_action)


        # 添加numpy标注文件菜单项
        open_numpy_action = QAction('Open Numpy Annotation', self)
        open_numpy_action.setShortcut('Ctrl+Shift+N')
        open_numpy_action.triggered.connect(self.open_numpy_annotation)
        file_menu.addAction(open_numpy_action)
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
    def create_central_widget(self):
        """创建中央部件（带标签页）"""
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧控制面板
        control_panel = self.create_control_panel()
        control_panel.setMinimumWidth(400)
        control_panel.setMaximumWidth(500)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        
        # 创建MRC Tomogram标签页
        self.tomogram_tab = self.create_tomogram_tab()
        self.tab_widget.addTab(self.tomogram_tab, "Tomogram")
        
        # 创建MRCs Projection标签页
        self.projection_tab = self.create_projection_tab()
        self.tab_widget.addTab(self.projection_tab, "Projections")
        
        # 连接标签页切换信号
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # 主分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([250, 750])
        
        main_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)


    def setup_projection_display(self):
        """设置投影显示区域"""
        self.projection_layout = QVBoxLayout(self.projection_display_area)
        self.projection_layout.setContentsMargins(5, 5, 5, 5)
        self.projection_layout.setSpacing(5)
        # 投影网格
        self.projection_grid = QGridLayout()
        self.projection_labels = []
        # 创建投影标签（3x3网格，9个）
        rows, cols = 10, 10
        for i in range(rows * cols):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(120, 120)
            label.setStyleSheet("")
            self.projection_labels.append(label)
            row = i // cols
            col = i % cols
            self.projection_grid.addWidget(label, row, col)
        
        self.projection_layout.addLayout(self.projection_grid)
        
        # 分页控件
        self.pagination_widget = self.create_pagination_controls()
        self.projection_layout.addWidget(self.pagination_widget)

    def create_tomogram_tab(self):
        """创建Tomogram标签页"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # 主显示区域
        self.tomogram_display = QLabel()
        self.tomogram_display.setAlignment(Qt.AlignCenter)
        self.tomogram_display.setText("No tomogram loaded")
        self.tomogram_display.setMinimumSize(512, 512)
        self.tomogram_display.mousePressEvent = self.on_image_click
        
        # Advanced Area
        self.advanced_area = self.create_advanced_area()
        self.advanced_area.setMinimumWidth(300)
        self.advanced_area.setMaximumWidth(300)
        
        # 水平布局
        display_layout = QHBoxLayout()
        display_layout.addWidget(self.tomogram_display, stretch=1)
        display_layout.addWidget(self.advanced_area, stretch=0)
        
        layout.addLayout(display_layout)
        
        return tab

    def create_projection_tab(self):
        """创建Projection标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 投影显示区域
        self.projection_display_area = QWidget()
        self.setup_projection_display()
        
        layout.addWidget(self.projection_display_area)
        
        return tab

    def on_tab_changed(self, index):
        """标签页切换回调"""
        if index == 0:  # Tomogram标签页
            self.display_mode = "tomogram"
            if self.current_data is not None:
                self.update_display()
        elif index == 1:  # Projection标签页
            self.display_mode = "projection"
            if self.mrcs_data is not None:
                self.update_projection_display()

    def switch_to_tomogram_tab(self):
        """切换到Tomogram标签页"""
        self.tab_widget.setCurrentIndex(0)

    def switch_to_projection_tab(self):
        """切换到Projection标签页"""
        self.tab_widget.setCurrentIndex(1)


    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        panel.setMaximumWidth(500)
        layout = QVBoxLayout(panel)
        
        # 文件信息组
        info_group = QGroupBox("File Information")
        info_layout = QVBoxLayout(info_group)
        self.file_info_label = QLabel('No file loaded')
        info_layout.addWidget(self.file_info_label)
        layout.addWidget(info_group)
        
        # 切片控制组
        slice_group = QGroupBox("Slice Control")
        slice_layout = QVBoxLayout(slice_group)
        
        # 滑动条
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.valueChanged.connect(self.slice_changed)
        slice_layout.addWidget(self.slice_slider)
        
        # 数值输入框
        self.slice_spinbox = QSpinBox()
        self.slice_spinbox.setMinimum(0)
        self.slice_spinbox.setMaximum(0)
        self.slice_spinbox.valueChanged.connect(self.slice_spinbox_changed)
        slice_layout.addWidget(self.slice_spinbox)
        
        self.slice_label = QLabel('Slice: 0/0')
        slice_layout.addWidget(self.slice_label)
        
        layout.addWidget(slice_group)
        
        # 对比度控制组
        contrast_group = QGroupBox("Contrast Control")
        contrast_layout = QVBoxLayout(contrast_group)
        # 反转衬度按钮
        self.invert_button = QPushButton("Invert Contrast")
        self.invert_button.setCheckable(True)
        self.invert_button.clicked.connect(self.toggle_invert_contrast)
        contrast_layout.addWidget(self.invert_button)
        
        # 下百分位数
        lower_label = QLabel('Lower Percentile:')
        self.lower_slider = QSlider(Qt.Horizontal)
        self.lower_slider.setMinimum(0)
        self.lower_slider.setMaximum(100)
        self.lower_slider.setValue(1)
        self.lower_slider.valueChanged.connect(self.contrast_changed)
        contrast_layout.addWidget(lower_label)
        contrast_layout.addWidget(self.lower_slider)
        
        # 上百分位数
        upper_label = QLabel('Upper Percentile:')
        self.upper_slider = QSlider(Qt.Horizontal)
        self.upper_slider.setMinimum(0)
        self.upper_slider.setMaximum(100)
        self.upper_slider.setValue(99)
        self.upper_slider.valueChanged.connect(self.contrast_changed)
        contrast_layout.addWidget(upper_label)
        contrast_layout.addWidget(self.upper_slider)
        
        layout.addWidget(contrast_group)
        
        # 刷新按钮
        refresh_btn = QPushButton("Refresh Display")
        refresh_btn.clicked.connect(self.update_display)
        layout.addWidget(refresh_btn)
        
        # 滤波控制组
        filter_group = self.create_filter_controls()
        layout.addWidget(filter_group)

        # 颗粒显示
        particle_group = self.create_particle_controls()
        layout.addWidget(particle_group)

        # 添加弹簧
        layout.addStretch()
        
        return panel


    def create_display_areas(self):
        """创建显示区域容器"""
        self.display_container = QWidget()
        self.display_layout = QVBoxLayout(self.display_container)
        
        # 3D Tomogram显示区域（原有）
        self.tomogram_display = QLabel()
        self.tomogram_display.setAlignment(Qt.AlignCenter)
        self.tomogram_display.setText("No tomogram loaded")
        self.tomogram_display.setMinimumSize(512, 512)
        self.tomogram_display.mousePressEvent = self.on_image_click
        
        # MRCS投影显示区域
        self.projection_display = QWidget()
        self.projection_layout = QVBoxLayout(self.projection_display)
        
        # 投影网格
        self.projection_grid = QGridLayout()
        self.projection_labels = []  # 存储投影显示标签
        
        # 创建投影标签
        rows, cols = 10, 10
        for i in range(rows * cols):  # 最多9个投影
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(150, 150)
            label.setStyleSheet("border: 1px solid gray;")
            self.projection_labels.append(label)
            row = i // cols
            col = i % cols
            self.projection_grid.addWidget(label, row, col)
        
        self.projection_layout.addLayout(self.projection_grid)
        
        # 分页控件
        self.pagination_widget = self.create_pagination_controls()
        self.projection_layout.addWidget(self.pagination_widget)
        
        # 默认隐藏投影显示
        self.projection_display.setVisible(False)

    def create_pagination_controls(self):
        """创建分页控件"""
        pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(pagination_widget)
        
        self.prev_page_btn = QPushButton("Previous")
        self.prev_page_btn.clicked.connect(self.previous_projection_page)
        
        self.page_label = QLabel("Page 1/1")
        
        self.next_page_btn = QPushButton("Next")
        self.next_page_btn.clicked.connect(self.next_projection_page)
        
        self.per_page_combo = QComboBox()
        self.per_page_combo.addItems(["4", "9", "16", "25", "50", "100"])
        self.per_page_combo.setCurrentText("100")
        self.per_page_combo.currentTextChanged.connect(self.change_projections_per_page)
        
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(QLabel("Per page:"))
        pagination_layout.addWidget(self.per_page_combo)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_btn)
        
        return pagination_widget


    def create_advanced_area(self):
        """创建Advanced Area"""
        area = QWidget()
        area.setMinimumWidth(200)
        layout = QVBoxLayout(area)
        
        # 粒子信息显示
        info_group = QGroupBox("Particle Info")
        info_layout = QVBoxLayout(info_group)
        self.particle_info_label = QLabel("Click on a particle to select")
        self.particle_info_label.setWordWrap(True)
        info_layout.addWidget(self.particle_info_label)
        layout.addWidget(info_group)
        
        # 三个截面显示
        sections_group = QGroupBox("Particle Sections")
        sections_layout = QVBoxLayout(sections_group)
        
        # X-Y截面
        self.xy_section_label = QLabel("X-Y Section")
        self.xy_section_display = QLabel()
        self.xy_section_display.setMinimumSize(150, 150)
        self.xy_section_display.setAlignment(Qt.AlignCenter)
        self.xy_section_display.setStyleSheet("")
        self.xy_section_display.mousePressEvent = self.on_xy_section_click
        # X-Z截面  
        self.xz_section_label = QLabel("X-Z Section")
        self.xz_section_display = QLabel()
        self.xz_section_display.setMinimumSize(150, 150)
        self.xz_section_display.setAlignment(Qt.AlignCenter)
        self.xz_section_display.setStyleSheet("")
        self.xz_section_display.mousePressEvent = self.on_xz_section_click
        # Y-Z截面
        self.yz_section_label = QLabel("Y-Z Section")
        self.yz_section_display = QLabel()
        self.yz_section_display.setMinimumSize(150, 150)
        self.yz_section_display.setAlignment(Qt.AlignCenter)
        self.yz_section_display.setStyleSheet("")
        self.yz_section_display.mousePressEvent = self.on_yz_section_click
        sections_layout.addWidget(self.xy_section_label)
        sections_layout.addWidget(self.xy_section_display)
        sections_layout.addWidget(self.xz_section_label)
        sections_layout.addWidget(self.xz_section_display)
        sections_layout.addWidget(self.yz_section_label)
        sections_layout.addWidget(self.yz_section_display)
        
        layout.addWidget(sections_group)
        layout.addStretch()
        
        return area

    def handle_section_click_precise(self, event, section_type):
        """处理截面点击事件（精确微调）"""
        if not self.edit_mode or self.selected_particle is None or self.current_data is None:
            return
            
        # 获取点击位置
        pos = event.pos()
        click_x = pos.x()
        click_y = pos.y()
        
        # 获取标签尺寸
        if section_type == 'xy':
            label = self.xy_section_display
        elif section_type == 'xz':
            label = self.xz_section_display
        else:  # yz
            label = self.yz_section_display
            
        label_width = label.width()
        label_height = label.height()
        
        if label_width <= 0 or label_height <= 0:
            return
        
        # 获取当前选中粒子的信息
        particle_idx, particle = self.selected_particle
        
        try:
            current_x = float(particle['_rlnCoordinateX'])
            current_y = float(particle['_rlnCoordinateY'])
            current_z = float(particle['_rlnCoordinateZ'])
            
            # 获取显示的截面数据范围（从display_particle_sections方法中获取）
            # 这里需要知道当前显示的截面patch大小
            
            # 简单方案：假设显示的是固定大小的patch（比如64x64像素）
            patch_size = 32  # 这应该与display_particle_sections中的一致
            
            # 计算点击相对于截面中心的偏移
            center_offset_x = (click_x - label_width / 2)
            center_offset_y = (click_y - label_height / 2)
            
            # 将像素偏移转换为实际坐标偏移（假设1:1映射或根据需要调整比例）
            # 这里可以调整灵敏度
            sensitivity = 1.0  # 可以调整这个值来控制微调的灵敏度
            coord_offset_x = center_offset_x * sensitivity
            coord_offset_y = center_offset_y * sensitivity
            
            # 根据截面类型计算新的坐标
            if section_type == 'xy':
                # XY截面：调整X和Y坐标
                new_x = int(current_x + coord_offset_x)
                new_y = int(current_y + coord_offset_y)
                new_z = int(current_z)
            elif section_type == 'xz':
                # XZ截面：调整X和Z坐标
                new_x = int(current_x + coord_offset_x)
                new_y = int(current_y)
                new_z = int(current_z + coord_offset_y)
            else:  # yz
                # YZ截面：调整Y和Z坐标
                new_x = int(current_x)
                new_y = int(current_y + coord_offset_x)
                new_z = int(current_z + coord_offset_y)
            
            # 边界检查（基于实际数据尺寸）
            if self.current_data is not None:
                data_shape = self.current_data.shape
                new_x = max(0, min(new_x, data_shape[2] - 1))
                new_y = max(0, min(new_y, data_shape[1] - 1))
                new_z = max(0, min(new_z, data_shape[0] - 1))
            
            # 更新粒子坐标
            self.update_particle_coordinates(particle_idx, new_x, new_y, new_z)
            
            # 更新显示
            self.update_display()
            updated_particle = self.star_data.iloc[particle_idx]
            self.display_particle_sections(updated_particle)
            
            self.status_bar.showMessage(f"Adjusted particle {particle_idx} by ({coord_offset_x:.1f}, {coord_offset_y:.1f})")
            self.has_unsaved_changes = True
            
        except Exception as e:
            self.status_bar.showMessage(f"Error adjusting coordinates: {str(e)}")
            print(f"Error in section click: {e}")


    def on_xy_section_click(self, event):
        """处理XY截面点击"""
        if not self.edit_mode or self.selected_particle is None:
            return
        self.handle_section_click_precise(event, 'xy')

    def on_xz_section_click(self, event):
        """处理XZ截面点击"""
        if not self.edit_mode or self.selected_particle is None:
            return
        self.handle_section_click_precise(event, 'xz')

    def on_yz_section_click(self, event):
        """处理YZ截面点击"""
        if not self.edit_mode or self.selected_particle is None:
            return
        self.handle_section_click_precise(event, 'yz')

    # 添加更新粒子坐标的方法
    def update_particle_coordinates(self, particle_idx, new_x, new_y, new_z):
        """更新粒子坐标"""
        if self.star_data is not None and 0 <= particle_idx < len(self.star_data):
            self.star_data.at[particle_idx, '_rlnCoordinateX'] = str(new_x)
            self.star_data.at[particle_idx, '_rlnCoordinateY'] = str(new_y)
            self.star_data.at[particle_idx, '_rlnCoordinateZ'] = str(new_z)
            
            # 更新缓存
            self.build_particle_cache()
            
            # 如果这是选中的粒子，更新选中粒子引用
            if self.selected_particle and self.selected_particle[0] == particle_idx:
                self.selected_particle = (particle_idx, self.star_data.iloc[particle_idx])


    def create_filter_controls(self):
        display_group = QGroupBox("Lowpass Control")
        display_layout = QVBoxLayout(display_group)
        
        # 显示滤波复选框
        self.filter_checkbox = QCheckBox("Apply Display Low-pass Filter")
        self.filter_checkbox.stateChanged.connect(self.toggle_display_filter)
        
        # 滤波参数输入
        filter_param_layout = QHBoxLayout()
        filter_param_layout.addWidget(QLabel('Cutoff (Å):'))
        self.filter_cutoff_input = QLineEdit("10.0")
        self.filter_cutoff_input.setMaximumWidth(80)
        self.filter_cutoff_input.editingFinished.connect(self.update_display)
        filter_param_layout.addWidget(self.filter_cutoff_input)
        
        display_layout.addWidget(self.filter_checkbox)
        display_layout.addLayout(filter_param_layout)
        
        return display_group


    # 在 create_control_panel 方法中添加粒子控制组
    def create_particle_controls(self):
        particle_group = QGroupBox("Particle Control")
        particle_layout = QVBoxLayout(particle_group)
        
        # 统一的坐标文件操作组
        coord_group = QGroupBox("Coordinate Files")
        coord_layout = QVBoxLayout(coord_group)
        
        # 读取坐标文件
        open_coord_btn = QPushButton("Open Coordinate File")
        open_coord_btn.clicked.connect(self.open_coordinate_file)
        
        # 保存坐标文件
        save_coord_btn = QPushButton("Save Coordinate File")
        save_coord_btn.clicked.connect(self.save_coordinate_file)
        
        # 坐标文件格式说明
        format_label = QLabel("Supports: .star, .npy formats")
        format_label.setStyleSheet("QLabel { font-size: 8pt; color: #666666; }")
        
        coord_layout.addWidget(open_coord_btn)
        coord_layout.addWidget(save_coord_btn)
        coord_layout.addWidget(format_label)
        
        particle_layout.addWidget(coord_group)
        # 显示粒子复选框
        self.show_particles_checkbox = QCheckBox("Show Particles")
        self.show_particles_checkbox.stateChanged.connect(self.toggle_particle_display)
        
        marker_size_layout = QHBoxLayout()
        marker_size_layout.addWidget(QLabel("Marker Size:"))
        self.marker_size_spinbox = QSpinBox()
        #self.marker_size_spinbox.setRange(1, 20)
        self.marker_size_spinbox.setValue(3)
        self.marker_size_spinbox.valueChanged.connect(self.update_display)
        marker_size_layout.addWidget(self.marker_size_spinbox)

        # 粒子计数标签
        self.particle_count_label = QLabel("No particles loaded")
        # 编辑模式控件组
        edit_group = QGroupBox("Edit Mode")
        edit_layout = QVBoxLayout(edit_group)
        
        # 编辑模式开关
        self.edit_mode_checkbox = QCheckBox("Enable Edit Mode")
        self.edit_mode_checkbox.stateChanged.connect(self.toggle_edit_mode)
        
        # 编辑模式说明
        edit_help = QLabel("In edit mode:\n- Click on main image to add/delete particles\n- Click on particle to select\n- Use controls below to modify")
        edit_help.setStyleSheet("QLabel { font-size: 8pt; color: #666666; }")
        edit_help.setWordWrap(True)
        
        # 粒子操作按钮
        particle_ops_layout = QHBoxLayout()
        self.add_particle_btn = QPushButton("Add")
        self.add_particle_btn.clicked.connect(self.enable_add_particle_mode)
        self.delete_particle_btn = QPushButton("Del")
        self.delete_particle_btn.clicked.connect(self.delete_selected_particle)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.discard_changes)
        self.save_changes_btn = QPushButton("Save Changes")
        self.save_changes_btn.clicked.connect(self.save_particle_changes)
        
        particle_ops_layout.addWidget(self.add_particle_btn)
        particle_ops_layout.addWidget(self.delete_particle_btn)
        particle_ops_layout.addWidget(self.undo_btn)
        
        edit_layout.addWidget(self.edit_mode_checkbox)
        edit_layout.addWidget(edit_help)
        edit_layout.addLayout(particle_ops_layout)
        edit_layout.addWidget(self.save_changes_btn)
        
        
        particle_layout.addWidget(self.show_particles_checkbox)
        particle_layout.addLayout(marker_size_layout)
        particle_layout.addWidget(self.particle_count_label)
        particle_layout.addWidget(edit_group)


        return particle_group


    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready')
        
    def open_file(self):
        """打开 MRC 文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open MRC File', '', 'MRC Files (*.mrc *.rec *.st);;All Files (*)')
        
        if filename:
            try:
                self.load_mrc_file_with_progress(filename)
                self.status_bar.showMessage(f'Loaded: {filename}')
            except Exception as e:
                self.status_bar.showMessage(f'Error loading file: {str(e)}')
                print(f"Error: {e}")

    def enable_add_particle_mode(self):
        """启用添加粒子模式"""
        if not self.edit_mode:
            self.status_bar.showMessage("Please enable edit mode first")
            return
            
        if self.pending_new_particle:
            # 取消添加模式
            self.pending_new_particle = False
            self.add_particle_btn.setText("Add")
            self.status_bar.showMessage("Cancelled particle addition mode")
        else:
            # 启用添加模式
            self.pending_new_particle = True
            self.add_particle_btn.setText("Cancel Add")
            self.status_bar.showMessage("Click on main image to add new particle (Left-click to add, Right-click to delete)")


    def load_mrc_file_with_progress(self, filename):
        """带进度显示的MRC文件加载"""
        # 创建进度对话框
        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setLabelText("Loading MRC file...")
        self.progress_dialog.setRange(0, 100)
        self.progress_dialog.setWindowTitle("Loading MRC Data")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.progress_dialog.setWindowTitle("Loading...")
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        
        # 创建工作线程
        self.worker = MRCWorker(filename)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished_loading.connect(self.on_load_finished)
        self.worker.error_occurred.connect(self.on_load_error)
        
        # 开始加载
        self.worker.start()
        self.progress_dialog.show()
    

    # 修改读取新STAR文件时的处理
    def open_star_file(self):
        """打开 STAR 坐标文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open STAR File', '', 'STAR Files (*.star);;All Files (*)')
        
        if filename:
            # 如果正在编辑模式且有未保存更改，先处理
            if self.edit_mode and self.has_unsaved_changes:
                reply = QMessageBox.question(
                    self, 'Unsaved Changes',
                    'You have unsaved changes in current edit session. Load new file will discard them. Continue?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
            
            try:
                from oktober.io import parse_star_file
                self.star_data = parse_star_file(filename)
                
                # 如果在编辑模式，更新原始数据
                if self.edit_mode:
                    self.original_star_data = self.star_data.copy()
                    self.has_unsaved_changes = False
                
                # 安全检查
                if self.star_data is not None and not self.star_data.empty:
                    self.particle_count_label.setText(f"Particles: {len(self.star_data)}")
                    self.build_particle_cache()
                    if self.display_mode == "tomogram":
                        self.update_display()
                else:
                    self.particle_count_label.setText("Particles: 0")
                    self.star_data = None
                    
                self.status_bar.showMessage(f'Loaded STAR file: {filename}')
                
            except Exception as e:
                self.star_data = None
                self.particle_count_label.setText("Particles: 0")
                QMessageBox.critical(self, 'Load Error', f'Error loading STAR file: {str(e)}')
                self.status_bar.showMessage(f'Error loading STAR file: {str(e)}')
                print(f"STAR file loading error: {e}")


    # 具体的文件加载方法
    def load_star_file(self, filename):
        """加载STAR文件"""
        from io.star_loader import parse_star_file
        star_data = parse_star_file(filename)
        
        # 处理编辑模式下的数据保护
        self.handle_data_loading_protection()
        
        # 更新数据
        self.star_data = star_data
        
        # 如果在编辑模式，更新原始数据
        if hasattr(self, 'edit_mode') and self.edit_mode:
            if self.star_data is not None:
                self.original_star_data = self.star_data.copy()
            else:
                self.original_star_data = None
            self.has_unsaved_changes = False
        
        # 更新界面
        self.update_coordinate_display()
        self.status_bar.showMessage(f'Loaded STAR file: {filename}')

    def load_numpy_file(self, filename):
        """加载numpy文件"""
        numpy_data = np.load(filename)
        
        # 验证数据格式
        if len(numpy_data.shape) != 2:
            raise ValueError("Numpy annotation must be 2D array")
        
        if numpy_data.shape[1] not in [6, 8]:
            raise ValueError("Numpy annotation must have 6 or 8 columns")
        
        # 转换为STAR格式
        star_data = self.convert_numpy_to_star(numpy_data)
        
        # 处理编辑模式下的数据保护
        self.handle_data_loading_protection()
        
        # 更新数据
        self.star_data = star_data
        
        # 如果在编辑模式，更新原始数据
        if hasattr(self, 'edit_mode') and self.edit_mode:
            if self.star_data is not None:
                self.original_star_data = self.star_data.copy()
            else:
                self.original_star_data = None
            self.has_unsaved_changes = False
        
        # 更新界面
        self.update_coordinate_display()
        self.status_bar.showMessage(f'Loaded numpy file: {filename}')


    def auto_detect_and_load_file(self, filename):
        """自动检测文件格式并加载"""
        try:
            # 首先尝试作为STAR文件加载
            from io.star_loader import parse_star_file
            star_data = parse_star_file(filename)
            self.star_data = star_data
            self.status_bar.showMessage(f'Auto-detected and loaded as STAR file: {filename}')
        except:
            # 如果失败，尝试作为numpy文件加载
            try:
                numpy_data = np.load(filename)
                if len(numpy_data.shape) == 2 and numpy_data.shape[1] in [6, 8]:
                    star_data = self.convert_numpy_to_star(numpy_data)
                    self.star_data = star_data
                    self.status_bar.showMessage(f'Auto-detected and loaded as numpy file: {filename}')
                else:
                    raise ValueError("Unknown file format")
            except:
                raise ValueError("Cannot detect file format or unsupported format")

    # 数据保护处理
    def handle_data_loading_protection(self):
        """处理加载新数据时的编辑模式保护"""
        if (hasattr(self, 'edit_mode') and self.edit_mode and 
            hasattr(self, 'has_unsaved_changes') and self.has_unsaved_changes):
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'You have unsaved changes in current edit session. Loading new file will discard them. Continue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                raise Exception("User cancelled operation")


    # 更新显示的统一方法
    def update_coordinate_display(self):
        """更新坐标显示"""
        if self.star_data is not None and not self.star_data.empty:
            self.particle_count_label.setText(f"Particles: {len(self.star_data)}")
            self.build_particle_cache()
            if self.display_mode == "tomogram":
                self.update_display()
        else:
            self.particle_count_label.setText("Particles: 0")
            self.star_data = None

    # 具体的保存方法
    def save_star_format(self, filename):
        """保存为STAR格式"""
        if self.star_data is None:
            return
            
        # 创建STAR文件内容
        with open(filename, 'w') as f:
            f.write("# RELION; version 4.0\n\ndata_\n\nloop_\n")
            
            # 写入列头
            for col in self.star_data.columns:
                f.write(f"{col}\n")
            
            # 写入数据
            for _, row in self.star_data.iterrows():
                values = []
                for col in self.star_data.columns:
                    values.append(str(row[col]))
                f.write("\t".join(values) + "\n")

    def save_numpy_format(self, filename):
        """保存为numpy格式"""
        if self.star_data is None:
            return
            
        # 转换为numpy格式
        numpy_array = self.convert_star_to_numpy(self.star_data)
        
        # 保存numpy文件
        np.save(filename, numpy_array)


    def build_particle_cache(self):
        """构建粒子位置缓存以加速查找"""
        self.particle_positions = []
        if self.star_data is not None:
            for idx, particle in self.star_data.iterrows():
                try:
                    x = float(particle['_rlnCoordinateX'])
                    y = float(particle['_rlnCoordinateY'])
                    z = float(particle['_rlnCoordinateZ'])
                    self.particle_positions.append((idx, x, y, z, particle))
                except (ValueError, KeyError):
                    continue


    def update_progress(self, value):
        """更新进度"""
        if self.progress_dialog:
            self.progress_dialog.setValue(value)
            
    def on_load_finished(self, data, header):
        """加载完成回调"""
        self.current_data = data
        self.current_header = header
        
        print(f"Data shape: {self.current_data.shape}")
        print(f"Data type: {self.current_data.dtype}")
        
        # 确保是3D数据
        if len(self.current_data.shape) != 3:
            self.status_bar.showMessage('Error: File is not 3D data')
            return
            
        # 初始化当前切片
        self.current_slice = self.current_data.shape[0] // 2
        
        # 设置切片控制范围
        max_slice = self.current_data.shape[0] - 1
        self.slice_slider.setMaximum(max_slice)
        self.slice_spinbox.setMaximum(max_slice)
        self.slice_slider.setValue(self.current_slice)
        self.slice_spinbox.setValue(self.current_slice)
        
        #self.switch_to_tomogram_mode()
        self.switch_to_tomogram_tab()
        # 更新界面
        self.update_file_info()
        self.update_display()

        if self.progress_dialog:
            self.progress_dialog.close()
            
        #self.status_bar.showMessage(f'Loaded: {self.get_current_filename()}')


    def on_load_error(self, error_message):
        """加载错误回调"""
        self.status_bar.showMessage(f'Error loading file: {error_message}')
        if self.progress_dialog:
            self.progress_dialog.close()
        print(f"Error: {error_message}")


    def load_mrc_file(self, filename):
        """加载 MRC 文件"""
        with mrcfile.open(filename, mode='r') as mrc:
            self.current_data = mrc.data.copy()

        print(f"Data shape: {self.current_data.shape}")
        print(f"Data type: {self.current_data.dtype}")
        
        # 确保是3D数据
        if len(self.current_data.shape) != 3:
            raise ValueError("File is not 3D data")
            
        # 初始化当前切片
        self.current_slice = self.current_data.shape[0] // 2
        
        # 设置切片控制范围
        max_slice = self.current_data.shape[0] - 1
        self.slice_slider.setMaximum(max_slice)
        self.slice_spinbox.setMaximum(max_slice)
        self.slice_slider.setValue(self.current_slice)
        self.slice_spinbox.setValue(self.current_slice)
        
        # 更新界面
        self.update_file_info()
        self.update_tomogram_display()


    def update_file_info(self):
        """更新文件信息显示"""
        if self.current_data is not None:
            info_text = f"""Shape: {self.current_data.shape}
            Data Type: {self.current_data.dtype}
            X-Y Size: {self.current_data.shape[2]} x {self.current_data.shape[1]}
            Slices: {self.current_data.shape[0]}"""
            self.file_info_label.setText(info_text)


    def slice_changed(self, value):
        """切片滑动条改变回调"""
        self.current_slice = value
        self.slice_spinbox.blockSignals(True)  # 防止循环触发
        self.slice_spinbox.setValue(value)
        self.slice_spinbox.blockSignals(False)
        self.slice_label.setText(f'Slice: {value}/{self.slice_slider.maximum()}')
        #self.update_display()
        # 如果启用了滤波，延迟更新显示以避免卡顿
        if self.display_filter_enabled:
            from PyQt5.QtCore import QTimer
            if hasattr(self, '_display_timer'):
                self._display_timer.stop()
            else:
                self._display_timer = QTimer()
                self._display_timer.setSingleShot(True)
                self._display_timer.timeout.connect(self.update_display)
            self._display_timer.start(100)  # 100ms延迟
        else:
            self.update_display()


    def slice_spinbox_changed(self, value):
        """切片数值框改变回调"""
        self.current_slice = value
        self.slice_slider.blockSignals(True)  # 防止循环触发
        self.slice_slider.setValue(value)
        self.slice_slider.blockSignals(False)
        self.slice_label.setText(f'Slice: {value}/{self.slice_slider.maximum()}')
        self.update_display()


    def contrast_changed(self):
        """对比度改变回调"""
        if self.display_mode == "tomogram":
            self.update_display()
        elif self.display_mode == "projection" and self.mrcs_data is not None:
            self.update_projection_display()

        
    #def auto_contrast(self, img, lower_percentile=1, upper_percentile=99):
    #    """计算自动对比度参数"""
    #    vmin = np.percentile(img, lower_percentile)
    #    vmax = np.percentile(img, upper_percentile)
    #    return vmin, vmax


    def toggle_display_filter(self, state):
        self.display_filter_enabled = state == Qt.Checked

    def toggle_display_filter(self, state):
        """切换显示滤波"""
        self.display_filter_enabled = state == Qt.Checked
        # 更新当前显示
        if self.display_mode == "tomogram":
            self.update_display()
        elif self.display_mode == "projection" and self.mrcs_data is not None:
            self.update_projection_display()


    def toggle_particle_display(self, state):
        self.show_particles = state == Qt.Checked
        self.update_display()


    def update_display(self):
        if self.display_mode == "tomogram":
            self.update_tomogram_display()
        elif self.display_mode == "projection":
            self.update_projection_display()

    def update_tomogram_display(self):
        """更新显示"""
        if self.current_data is None or self.display_mode != "tomogram":
            return

        # 获取当前切片数据
        slice_data = self.current_data[self.current_slice]

        # 滤波
        if self.display_filter_enabled:
            try:
                #print(f"cutoff :{self.filter_cutoff_input.text()}")
                cutoff = float(self.filter_cutoff_input.text())
                apix = self.current_header.cella.x / self.current_header.mx # 从header获取实际值
                slice_data = lowpass_fourier_2d(slice_data, cutoff, apix)
            except Exception as e:
                print(f"Display filter error: {e}")
        
        # 计算对比度参数
        lower_pct = self.lower_slider.value()
        upper_pct = self.upper_slider.value()
        self.vmin, self.vmax = auto_contrast(slice_data, lower_pct, upper_pct)

        img_uint8 = apply_contrast(slice_data, self.vmin, self.vmax).astype(np.uint8)
        # 如果启用反转衬度，则反转图像
        if self.invert_contrast:
            img_uint8 = 255 - img_uint8

        if self.show_particles and self.star_data is not None and not self.star_data.empty:
            try:
                img_uint8 = self.draw_particles_on_image(img_uint8, self.current_slice)
            except Exception as e:
                print(f"Exception in drawing particles on image: {e}")

        # 如果有选中的粒子，额外高亮显示
        if self.show_particles and self.selected_particle:
            try:
                img_uint8 = self.highlight_selected_particle(img_uint8, self.selected_particle[1])
            except Exception as e:
                print(f"Exception in highlighting particle: {e}")

        # 转换为 QImage 并显示
        if len(img_uint8.shape) == 3:
            height, width, channels = img_uint8.shape
            bytes_per_line = width * channels
            if channels == 3:
                q_img = QImage(img_uint8.data, width, height, bytes_per_line, QImage.Format_RGB888)
            else:
                q_img = QImage(img_uint8.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        else:
            height, width = img_uint8.shape
            bytes_per_line = width
            q_img = QImage(img_uint8.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        
        # 缩放到合适大小
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(
            self.tomogram_display.width() - 20,
            self.tomogram_display.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.tomogram_display.setPixmap(scaled_pixmap)

    def toggle_invert_contrast(self):
        """切换反转衬度"""
        self.invert_contrast = self.invert_button.isChecked() if hasattr(self, 'invert_button') else False
        if self.invert_contrast:
            self.invert_button.setText("Normal Contrast")
        else:
            self.invert_button.setText("Invert Contrast")
        
        # 更新当前显示
        if self.display_mode == "tomogram":
            self.update_display()
        elif self.display_mode == "projection" and self.mrcs_data is not None:
            self.update_projection_display()


    def draw_particles_on_image(self, img_array, current_z):
        """优化版：只绘制当前视野内的颗粒"""
        if len(img_array.shape) == 3:
            height, width, channels = img_array.shape
        else:
            height, width = img_array.shape
        
        # 如果是灰度图，转换为RGB用于绘制
        if len(img_array.shape) == 2:
            img_rgb = np.stack([img_array, img_array, img_array], axis=-1)
        else:
            img_rgb = img_array.copy()

        if self.star_data is not None and not self.star_data.empty:
            height, width = img_array.shape
            marker_size = getattr(self, 'marker_size_spinbox', type('obj', (object,), {'value': lambda: 3})()).value()
            # 过滤当前切片附近的粒子
            nearby_particles = self.star_data[
                (abs(self.star_data['_rlnCoordinateZ'].astype(float) - current_z) <= 2)
            ]
            
            if len(nearby_particles) > 0:
                # 只处理视野内的粒子（添加边距）
                margin = 10
                visible_particles = nearby_particles[
                    (nearby_particles['_rlnCoordinateX'].astype(float) >= -margin) &
                    (nearby_particles['_rlnCoordinateX'].astype(float) <= width + margin) &
                    (nearby_particles['_rlnCoordinateY'].astype(float) >= -margin) &
                    (nearby_particles['_rlnCoordinateY'].astype(float) <= height + margin)
                ]
                
                # 限制最多绘制1000个粒子（避免过度绘制）
                #if len(visible_particles) > 1000:
                #    visible_particles = visible_particles.sample(1000)
                #    print(f"Too many particles ({len(visible_particles)}), sampling 1000")
                
                # 绘制粒子
                for _, particle in visible_particles.iterrows():
                    x = int(float(particle['_rlnCoordinateX']))
                    y = int(float(particle['_rlnCoordinateY']))
                    
                    # 绘制红色标记
                    if 0 <= x < width and 0 <= y < height:
                        # 绘制可变大小的圆形标记
                        self.draw_marker(img_rgb, x, y, marker_size, [255, 0, 0])
        
        return img_rgb


    def delete_selected_particle(self):
        """删除选中的粒子"""
        if not self.edit_mode:
            self.status_bar.showMessage("Please enable edit mode first")
            return
            
        if self.selected_particle is None:
            self.status_bar.showMessage("No particle selected")
            return
            
        # 从数据中删除粒子
        particle_idx = self.selected_particle[0]
        self.delete_particle_by_index(particle_idx)


    def highlight_selected_particle(self, img_array, particle):
        """高亮显示选中的粒子"""
        if len(img_array.shape) == 2:
            img_rgb = np.stack([img_array, img_array, img_array], axis=-1)
        else:
            img_rgb = img_array.copy()
        
        try:
            x = int(float(particle['_rlnCoordinateX']))
            y = int(float(particle['_rlnCoordinateY']))
            
            height, width = img_rgb.shape[:2]
            if 0 <= x < width and 0 <= y < height:
                # 绘制绿色圆圈表示选中的粒子
                marker_size = self.marker_size_spinbox.value() # 稍大一些
                self.draw_marker_colored(img_rgb, x, y, marker_size, [0, 255, 0])  # 绿色
                
        except Exception as e:
            print(f"Error highlighting particle: {e}")
        
        if len(img_array.shape) == 2:
            return img_rgb[:, :, 0]
        else:
            return img_rgb

    def draw_marker_colored(self, img_array, x, y, size, color):
        """绘制彩色标记"""
        height, width = img_array.shape[:2]
        
        if size == 1:
            if 0 <= y < height and 0 <= x < width:
                img_array[y, x] = color
        else:
            radius = size // 2
            for angle in range(0, 360, max(1, 360//(8*radius))):
                rad = np.radians(angle)
                nx = int(x + radius * np.cos(rad))
                ny = int(y + radius * np.sin(rad))
                if 0 <= ny < height and 0 <= nx < width:
                    img_array[ny, nx] = color

    def draw_marker(self, img_array, x, y, size, color):
        """绘制标记"""
        height, width = img_array.shape[:2]
        
        if size == 1:
            # 单点标记
            if 0 <= y < height and 0 <= x < width:
                img_array[y, x] = color
        elif size == 2:
            # 3x3方形标记
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        img_array[ny, nx] = color
        else:
            # 圆形标记
            radius = size // 2
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    distance_squared = dx*dx + dy*dy
                    if distance_squared <= radius*radius and distance_squared >= (radius-1)*(radius-1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < height and 0 <= nx < width:
                            img_array[ny, nx] = color


    # 修改鼠标点击处理来支持编辑模式
    def on_image_click(self, event):
        """处理图像点击事件（支持编辑模式）"""
        if self.current_data is None or self.display_mode != "tomogram":
            return
            
        # 获取点击位置
        pos = event.pos()
        x = pos.x()
        y = pos.y()
        
        # 转换为图像坐标
        img_x, img_y = self.label_to_image_coords(x, y)
        
        if self.edit_mode:
            self.handle_edit_mode_click(img_x, img_y, event)
        else:
            # 原有的粒子选择逻辑
            self.find_nearest_particle_optimized(img_x, img_y, self.current_slice)

    def handle_edit_mode_click(self, img_x, img_y, event):
        """处理编辑模式下的点击"""
        if event.button() == Qt.RightButton:
            # 右键总是用于删除操作
            clicked_particle = self.find_nearest_particle_for_deletion(img_x, img_y, self.current_slice)
            if clicked_particle:
                self.delete_particle_by_index(clicked_particle[0])
            return
        
        # 左键处理
        if self.pending_new_particle:
            # 添加新粒子
            self.add_new_particle(img_x, img_y)
            self.pending_new_particle = False
            self.add_particle_btn.setText("Add")  # 恢复按钮文本
        else:
            # 检查是否点击了现有粒子
            clicked_particle = self.find_nearest_particle_optimized(img_x, img_y, self.current_slice)
            if not clicked_particle:
                # 点击了空白区域 - 如果需要可以添加新粒子的提示
                self.status_bar.showMessage("Click 'Add Particle' button first to add new particles")


    def find_nearest_particle_for_deletion(self, click_x, click_y, click_z):
        """专门用于删除操作的粒子查找"""
        if not self.particle_positions:
            return None
            
        min_distance = float('inf')
        nearest_particle = None
        marker_size = self.marker_size_spinbox.value() if hasattr(self, 'marker_size_spinbox') else 3
        search_radius = max(marker_size * 2, 20)
        
        for idx, x, y, z, particle in self.particle_positions:
            if abs(z - click_z) <= 2:
                distance = np.sqrt((x - click_x)**2 + (y - click_y)**2)
                if distance <= search_radius and distance < min_distance:
                    min_distance = distance
                    nearest_particle = (idx, particle)
        
        return nearest_particle


    def label_to_image_coords(self, label_x, label_y):
        """将标签坐标转换为图像坐标"""
        if self.current_data is None:
            return label_x, label_y
        
        # 获取显示区域大小
        label_width = self.tomogram_display.width()
        label_height = self.tomogram_display.height()
        
        # 获取图像原始大小
        img_width = self.current_data.shape[2]
        img_height = self.current_data.shape[1]
        
        # 计算缩放后的pixmap大小
        aspect_ratio = min((label_width - 20) / img_width, (label_height - 20) / img_height)
        pixmap_width = int(img_width * aspect_ratio)
        pixmap_height = int(img_height * aspect_ratio)
        
        # 计算pixmap在label中的位置
        pixmap_x = (label_width - pixmap_width) // 2
        pixmap_y = (label_height - pixmap_height) // 2
        
        # 检查点击是否在pixmap区域内
        if (pixmap_x <= label_x <= pixmap_x + pixmap_width and 
            pixmap_y <= label_y <= pixmap_y + pixmap_height):
            
            # 转换坐标
            img_x = int((label_x - pixmap_x) * img_width / pixmap_width)
            img_y = int((label_y - pixmap_y) * img_height / pixmap_height)
            
            print(f"Converted to image coords: ({img_x}, {img_y})")  # 调试信息
            return img_x, img_y
        
        return label_x, label_y


    def find_nearest_particle(self, click_x, click_y, click_z):
        """查找最近的粒子"""
        if self.star_data is None or self.star_data.empty:
            return
            
        min_distance = float('inf')
        nearest_particle = None
        
        # 在当前切片附近的粒子中查找
        for idx, particle in self.star_data.iterrows():
            particle_x = float(particle['_rlnCoordinateX'])
            particle_y = float(particle['_rlnCoordinateY'])
            particle_z = float(particle['_rlnCoordinateZ'])
            
            # 只考虑当前切片附近的粒子
            if abs(particle_z - click_z) <= 2:
                distance = np.sqrt((particle_x - click_x)**2 + (particle_y - click_y)**2)
                if distance < min_distance and distance < 20:  # 20像素范围内
                    min_distance = distance
                    nearest_particle = (idx, particle)
        
        if nearest_particle:
            self.select_particle(nearest_particle[0], nearest_particle[1])


    def find_nearest_particle_optimized(self, click_x, click_y, click_z):
        """优化的最近粒子查找"""
        if not self.particle_positions:
            return None
            
        min_distance = float('inf')
        nearest_particle = None
        marker_size = self.marker_size_spinbox.value() if hasattr(self, 'marker_size_spinbox') else 3
        search_radius = marker_size + 10
        
        for idx, x, y, z, particle in self.particle_positions:
            # 只考虑当前切片附近的粒子
            if abs(z - click_z) <= 2:
                distance = np.sqrt((x - click_x)**2 + (y - click_y)**2)
                if distance <= search_radius and distance < min_distance:
                    min_distance = distance
                    nearest_particle = (idx, particle)
        
        if nearest_particle:
            self.select_particle(nearest_particle[0], nearest_particle[1])
            return nearest_particle
        
        return None


    # 修改 select_particle 方法来适应编辑模式
    def select_particle(self, index, particle):
        """选择粒子并显示详细信息"""
        self.selected_particle = (index, particle)
        
        # 安全地显示粒子信息
        try:
            info_text = f"Particle Index: {index}\n"
            info_text += f"X: {particle['_rlnCoordinateX']}\n"
            info_text += f"Y: {particle['_rlnCoordinateY']}\n"
            info_text += f"Z: {particle['_rlnCoordinateZ']}\n"
            
            for key in ['_rlnAngleRot', '_rlnAngleTilt', '_rlnAnglePsi']:
                if key in particle:
                    info_text += f"{key[4:]}: {particle[key]}\n"
                    
            if hasattr(self, 'particle_info_label'):
                self.particle_info_label.setText(info_text)
        except Exception as e:
            print(f"Error displaying particle info: {e}")
        
        # 显示三个截面
        try:
            if hasattr(self, 'xy_section_display'):
                self.display_particle_sections(particle)
        except Exception as e:
            print(f"Error displaying sections: {e}")
        
        # 更新显示
        if self.display_mode == "tomogram":
            self.update_display()

    def display_particle_sections(self, particle):
        """显示粒子的三个截面"""
        if self.current_data is None:
            return
            
        try:
            x = int(float(particle['_rlnCoordinateX']))
            y = int(float(particle['_rlnCoordinateY']))
            z = int(float(particle['_rlnCoordinateZ']))
            
            nz, ny, nx = self.current_data.shape
            
            # 提取截面数据（添加边界检查）
            patch_size = 32
            x_start = max(0, x - patch_size)
            x_end = min(nx, x + patch_size)
            y_start = max(0, y - patch_size)
            y_end = min(ny, y + patch_size)
            z_start = max(0, z - patch_size)
            z_end = min(nz, z + patch_size)
            
            # X-Y截面（当前Z切片）
            if 0 <= z < nz:
                xy_section = self.current_data[z, y_start:y_end, x_start:x_end]
                self.display_section(xy_section, self.xy_section_display)
            
            # X-Z截面（Y切片）
            if 0 <= y < ny:
                xz_section = self.current_data[z_start:z_end, y, x_start:x_end]
                self.display_section(xz_section, self.xz_section_display)
                
            # Y-Z截面（X切片）
            if 0 <= x < nx:
                yz_section = self.current_data[z_start:z_end, y_start:y_end, x]
                self.display_section(yz_section, self.yz_section_display)
                
        except Exception as e:
            print(f"Error displaying sections: {e}")

    def display_section(self, section_data, display_label):
        """显示单个截面"""
        if section_data.size == 0:
            return
            
        # 归一化到0-255
        section_normalized = section_data.astype(np.float32)
        section_min = section_normalized.min()
        section_max = section_normalized.max()
        
        if section_max > section_min:
            section_normalized = (section_normalized - section_min) / (section_max - section_min) * 255
        else:
            section_normalized = np.zeros_like(section_normalized)
        
        section_uint8 = section_normalized.astype(np.uint8)
        
        # 转换为QImage
        height, width = section_uint8.shape
        bytes_per_line = width
        q_img = QImage(section_uint8.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        
        # 缩放到显示区域
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        display_label.setPixmap(scaled_pixmap)


    def open_mrcs_file(self):
        """打开MRCS文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open MRCS File', '', 'MRCS Files (*.mrcs);;All Files (*)')
        
        if filename:
            try:
                self.load_mrcs_file_with_progress(filename)
            except Exception as e:
                self.status_bar.showMessage(f'Error loading MRCS file: {str(e)}')


    def load_mrcs_file_with_progress(self, filename):
        """带进度显示的MRCS文件加载"""
        # 创建进度对话框
        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setLabelText("Loading MRCS file...")
        self.progress_dialog.setRange(0, 0)  # 脉冲模式
        self.progress_dialog.setWindowTitle("Loading MRCS Data")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        
        # 创建工作线程
        self.mrcs_worker = MRCSWorker(filename)
        self.mrcs_worker.finished_loading.connect(self.on_mrcs_load_finished)
        self.mrcs_worker.error_occurred.connect(self.on_mrcs_load_error)
        
        # 开始加载
        self.mrcs_worker.start()
        self.progress_dialog.show()


    def on_mrcs_load_finished(self, data, header):
        """MRCS加载完成"""
        self.mrcs_data = data
        self.current_header = header
        self.current_projection_page = 0
        
        # 清除之前的3D数据
        self.current_data = None
        self.star_data = None
        self.selected_particle = None
        
        self.switch_to_projection_tab()
        # 更新界面
        self.update_file_info_mrcs()
        self.update_projection_display()
        #self.switch_to_projection_mode()
        
        if self.progress_dialog:
            self.progress_dialog.close()
            
        self.status_bar.showMessage(f'Loaded MRCS file: {data.shape} projections')


    def on_mrcs_load_error(self, error_message):
        """MRCS加载错误"""
        self.status_bar.showMessage(f'Error loading MRCS file: {error_message}')
        if self.progress_dialog:
            self.progress_dialog.close()


    def update_file_info_mrcs(self):
        """更新MRCS文件信息显示"""
        if self.mrcs_data is not None:
            import os
            filename_only = os.path.basename(self.current_filename) if hasattr(self, 'current_filename') else "unknown"
            info_text = f"""
    Projections: {self.mrcs_data.shape[0]}
    Projection Size: {self.mrcs_data.shape[2]} x {self.mrcs_data.shape[1]}
    Data Type: {self.mrcs_data.dtype}"""
            self.file_info_label.setText(info_text)
            
            # 切换到投影显示模式
            #self.switch_to_projection_mode()
            self.switch_to_projection_tab
    
    #def switch_to_tomogram_mode(self):
    #    """切换到tomogram显示模式"""
    #    self.display_mode = "tomogram"
        #self.display_stack.setCurrentIndex(0)  # 显示tomogram
    #    self.update_display()

    #def switch_to_projection_mode(self):
    #    """切换到投影显示模式"""
    #    self.display_mode = "projection"
    #    #self.display_stack.setCurrentIndex(1)  # 显示projection
    #    self.update_projection_display()
    
    def update_projection_display(self):
        """更新投影显示"""
        if self.mrcs_data is None or self.display_mode != "projection":
            return
        
        # 清空所有投影标签
        for label in self.projection_labels:
            label.clear()
            #label.setText("")
        
        # 计算当前页面的投影范围
        total_projections = self.mrcs_data.shape[0]
        self.projections_per_page = int(self.per_page_combo.currentText()) if self.per_page_combo else 100
        start_idx = self.current_projection_page * self.projections_per_page
        end_idx = min(start_idx + self.projections_per_page, total_projections)

        # 显示当前页面的投影
        for i in range(start_idx, end_idx):
            projection_idx = i - start_idx
            #print(f"projection_idx: {projection_idx} i: {i}")
            #print(f"len(self.projection_labels): {len(self.projection_labels)}")
            if projection_idx < len(self.projection_labels):
                projection = self.mrcs_data[i]
                
                # 应用滤波和对比度处理（使用相同的处理逻辑）
                processed_projection = self.process_projection(projection)
                #print(f"projection_idx: {projection_idx} i: {i}")
                # 转换为QImage并显示
                self.display_single_projection(processed_projection, self.projection_labels[projection_idx])
        
        self.update_pagination_info()

    def process_projection(self, projection):
        """处理单个投影（滤波、对比度等）"""
        processed = projection.copy()
        
        # 应用显示滤波
        if self.display_filter_enabled:
            try:
                cutoff = float(self.filter_cutoff_input.text())
                apix = 1.0 # 从header获取实际值
                #from your_filter_module import lowpass_fourier_2d
                processed = lowpass_fourier_2d(processed, cutoff, apix)
            except Exception as e:
                print(f"Display filter error: {e}")
        
        # 应用对比度调整
        lower_pct = self.lower_slider.value()
        upper_pct = self.upper_slider.value()
        vmin, vmax = auto_contrast(processed, lower_pct, upper_pct)
        
        processed = np.clip(processed, vmin, vmax)
        if vmax != vmin:
            processed = (processed - vmin) / (vmax - vmin) * 255
        else:
            processed = np.zeros_like(processed)
            
        # 反转衬度
        if self.invert_contrast:
            processed = 255 - processed
            
        return processed.astype(np.uint8)

    def display_single_projection(self, img_array, label):
        """在标签中显示单个投影"""
        height, width = img_array.shape
        bytes_per_line = width
        q_img = QImage(img_array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)


    def update_pagination_info(self):
        """更新分页信息"""
        if self.mrcs_data is not None:
            total_projections = self.mrcs_data.shape[0]
            self.projections_per_page = int(self.per_page_combo.currentText())
            total_pages = (total_projections + self.projections_per_page - 1) // self.projections_per_page
            
            current_page = self.current_projection_page + 1
            self.page_label.setText(f"Page {current_page}/{total_pages}")
            
            # 更新按钮状态
            self.prev_page_btn.setEnabled(self.current_projection_page > 0)
            self.next_page_btn.setEnabled(self.current_projection_page < total_pages - 1)

    def previous_projection_page(self):
        """上一页"""
        if self.current_projection_page > 0:
            self.current_projection_page -= 1
            self.update_projection_display()

    def next_projection_page(self):
        """下一页"""
        if self.mrcs_data is not None:
            total_projections = self.mrcs_data.shape[0]
            total_pages = (total_projections + self.projections_per_page - 1) // self.projections_per_page
            if self.current_projection_page < total_pages - 1:
                self.current_projection_page += 1
                self.update_projection_display()

    def change_projections_per_page(self, text):
        """改变每页投影数"""
        self.current_projection_page = 0  # 回到第一页
        self.update_projection_display()


    def toggle_edit_mode(self, state):
        """切换编辑模式（带数据保护）"""
        new_state = state == Qt.Checked
        
        # 如果要关闭编辑模式且有未保存的更改，弹出确认对话框
        if not new_state and self.edit_mode and self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'You have unsaved changes. Do you want to save them before exiting edit mode?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                # 保存更改
                self.save_particle_changes()
                if not self.has_unsaved_changes:  # 如果保存成功
                    self.proceed_exit_edit_mode()
                else:
                    # 保存失败，保持编辑模式
                    self.edit_mode_checkbox.setChecked(True)
                    return
            elif reply == QMessageBox.Discard:
                # 放弃更改，恢复原始数据
                self.discard_changes()
                self.proceed_exit_edit_mode()
            else:
                # 取消操作，保持编辑模式
                self.edit_mode_checkbox.setChecked(True)
                return
        elif new_state and not self.edit_mode:
            # 进入编辑模式
            self.enter_edit_mode()
        elif not new_state and self.edit_mode:
            # 关闭编辑模式（无未保存更改）
            self.proceed_exit_edit_mode()

    def enter_edit_mode(self):
        """进入编辑模式"""
        self.edit_mode = True
        # 保存原始数据副本
        if self.star_data is not None:
            self.original_star_data = self.star_data.copy()
        self.has_unsaved_changes = False
        
        self.status_bar.showMessage("Edit mode enabled: Left-click to select/add particles, Right-click to delete")
        # 改变显示区域边框来指示编辑模式
        self.tomogram_display.setStyleSheet("""
            QLabel { 
                border: 2px dashed #ff6b6b; 
                background-color: transparent;
            }
        """)
        # 确保粒子显示已开启
        if not self.show_particles:
            self.show_particles_checkbox.setChecked(True)

    def proceed_exit_edit_mode(self):
        """真正退出编辑模式"""
        self.edit_mode = False
        self.pending_new_particle = None
        self.has_unsaved_changes = False
        
        self.status_bar.showMessage("Edit mode disabled")
        # 恢复正常边框
        self.tomogram_display.setStyleSheet("""
            QLabel { 
                border: 1px solid gray; 
                background-color: transparent;
            }
        """)

    def discard_changes(self):
        """放弃更改，恢复原始数据"""
        if self.original_star_data is not None:
            self.star_data = self.original_star_data.copy()
            self.build_particle_cache()
            self.update_display()
        self.has_unsaved_changes = False

    # 修改添加/删除粒子的方法来标记更改
    def add_new_particle(self, x, y):
        """添加新粒子"""
        if self.current_data is None:
            return
            
        # 创建新粒子数据
        new_particle_data = {
            '_rlnCoordinateX': str(x),
            '_rlnCoordinateY': str(y),
            '_rlnCoordinateZ': str(self.current_slice),
            '_rlnAngleRot': '0.0',
            '_rlnAngleTilt': '0.0', 
            '_rlnAnglePsi': '0.0'
        }
        
        # 添加到数据中
        import pandas as pd
        new_row = pd.DataFrame([new_particle_data])
        
        if self.star_data is None:
            self.star_data = new_row
        else:
            self.star_data = pd.concat([self.star_data, new_row], ignore_index=True)
        
        self.build_particle_cache()  # 重建缓存
        self.update_display()
        self.has_unsaved_changes = True  # 标记有未保存更改
        self.status_bar.showMessage(f"Added new particle at ({x:.1f}, {y:.1f}, {self.current_slice})")

    def delete_particle_by_index(self, index):
        """根据索引删除粒子"""
        if self.star_data is not None and index < len(self.star_data):
            self.star_data = self.star_data.drop(index).reset_index(drop=True)
            if self.selected_particle and self.selected_particle[0] == index:
                self.selected_particle = None
            self.build_particle_cache()
            self.update_display()
            self.has_unsaved_changes = True  # 标记有未保存更改
            self.status_bar.showMessage(f"Deleted particle {index}")

    # 修改保存方法
    def save_particle_changes(self):
        """保存粒子坐标更改"""
        if self.star_data is None:
            self.status_bar.showMessage("No particle data to save")
            return
            
        # 弹出保存对话框
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Save Particle Coordinates', '', 'STAR Files (*.star);;All Files (*)')
        
        if filename:
            try:
                self.save_star_file(filename)
                self.status_bar.showMessage(f"Saved particle coordinates to {filename}")
                self.has_unsaved_changes = False  # 保存后清除更改标记
                
                # 询问是否继续编辑
                reply = QMessageBox.question(
                    self, 'Save Complete',
                    'Changes saved successfully. Do you want to continue editing?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.No:
                    self.edit_mode_checkbox.setChecked(False)
                    
            except Exception as e:
                QMessageBox.critical(self, 'Save Error', f"Error saving file: {str(e)}")
                self.status_bar.showMessage(f"Error saving file: {str(e)}")
    def save_star_file(self, filename):
        """保存STAR文件"""
        if self.star_data is None:
            return
            
        # 创建STAR文件内容
        with open(filename, 'w') as f:
            f.write("data_\n\nloop_\n")
            
            # 写入列头
            for col in self.star_data.columns:
                f.write(f"{col}\n")
            
            # 写入数据
            for _, row in self.star_data.iterrows():
                values = []
                for col in self.star_data.columns:
                    values.append(str(row[col]))
                f.write("\t".join(values) + "\n")

    # 添加窗口关闭事件处理
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 检查是否有未保存的编辑更改
        if self.edit_mode and self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'You have unsaved changes in edit mode. Do you want to save them before closing?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_particle_changes()
                if not self.has_unsaved_changes:  # 如果保存成功
                    event.accept()
                else:
                    # 保存失败，取消关闭
                    event.ignore()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                # 取消关闭
                event.ignore()
        else:
            event.accept()

    def open_numpy_annotation(self):
        """打开numpy格式的标注文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open Numpy Annotation File', '', 
            'Numpy Files (*.npy);;All Files (*)')
        
        if filename:
            try:
                # 读取numpy文件
                numpy_data = np.load(filename)
                
                # 验证数据格式
                if len(numpy_data.shape) != 2:
                    raise ValueError("Numpy annotation must be 2D array")
                
                if numpy_data.shape[1] not in [6, 8]:
                    raise ValueError("Numpy annotation must have 6 or 8 columns")
                
                # 转换为STAR格式
                star_data = self.convert_numpy_to_star(numpy_data)
                
                # 如果正在编辑模式且有未保存更改，先处理
                if (hasattr(self, 'edit_mode') and self.edit_mode and 
                    hasattr(self, 'has_unsaved_changes') and self.has_unsaved_changes):
                    reply = QMessageBox.question(
                        self, 'Unsaved Changes',
                        'You have unsaved changes in current edit session. Load new file will discard them. Continue?',
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        return
                
                # 更新数据
                self.star_data = star_data
                
                # 如果在编辑模式，更新原始数据
                if hasattr(self, 'edit_mode') and self.edit_mode:
                    if self.star_data is not None:
                        self.original_star_data = self.star_data.copy()
                    else:
                        self.original_star_data = None
                    self.has_unsaved_changes = False
                
                # 更新界面
                if self.star_data is not None and not self.star_data.empty:
                    self.particle_count_label.setText(f"Particles: {len(self.star_data)}")
                    self.build_particle_cache()
                    if self.display_mode == "tomogram":
                        self.update_display()
                else:
                    self.particle_count_label.setText("Particles: 0")
                    self.star_data = None
                    
                self.status_bar.showMessage(f'Loaded numpy annotation file: {filename}')
                
            except Exception as e:
                QMessageBox.critical(self, 'Load Error', f'Error loading numpy annotation file: {str(e)}')
                self.status_bar.showMessage(f'Error loading numpy file: {str(e)}')
                print(f"Numpy file loading error: {e}")

    def convert_numpy_to_star(self, numpy_data):
        """将numpy数组转换为STAR格式"""
        import pandas as pd
        
        # 解析numpy数据
        if numpy_data.shape[1] == 8:
            # 8列格式: z1,z2,y1,y2,x1,x2,class,confidence
            z1, z2, y1, y2, x1, x2, class_col, confidence = numpy_data.T
        elif numpy_data.shape[1] == 6:
            # 6列格式: z1,z2,y1,y2,x1,x2
            z1, z2, y1, y2, x1, x2 = numpy_data.T
            class_col = np.ones(len(numpy_data))  # 默认类别为1
            confidence = np.ones(len(numpy_data))  # 默认置信度为1
        else:
            raise ValueError("Unsupported numpy array format")
        
        # 计算中心坐标（使用框的中心）
        z_center = (z1 + z2) / 2
        y_center = (y1 + y2) / 2
        x_center = (x1 + x2) / 2
        
        # 创建STAR数据结构
        star_dict = {
            '_rlnCoordinateX': x_center.astype(str),
            '_rlnCoordinateY': y_center.astype(str),
            '_rlnCoordinateZ': z_center.astype(str),
            '_rlnAngleRot': ['0.0'] * len(numpy_data),
            '_rlnAngleTilt': ['0.0'] * len(numpy_data),
            '_rlnAnglePsi': ['0.0'] * len(numpy_data),
            '_rlnClassNumber': class_col.astype(str)
        }
        
        # 如果有置信度信息，添加到STAR文件中
        if numpy_data.shape[1] == 8:
            star_dict['_rlnAutopickFigureOfMerit'] = confidence.astype(str)
        
        # 创建DataFrame
        star_df = pd.DataFrame(star_dict)
        
        return star_df

    # 添加保存为numpy格式的功能
    def save_as_numpy_annotation(self):
        """保存为numpy格式的标注文件"""
        if self.star_data is None:
            self.status_bar.showMessage("No particle data to save")
            return
        
        # 弹出保存对话框
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Save as Numpy Annotation', '', 'Numpy Files (*.npy);;All Files (*)')
        
        if filename:
            try:
                # 转换为numpy格式
                numpy_array = self.convert_star_to_numpy(self.star_data)
                
                # 保存numpy文件
                np.save(filename, numpy_array)
                
                self.status_bar.showMessage(f"Saved numpy annotation to {filename}")
                
                # 如果在编辑模式，清除未保存标记
                if self.edit_mode:
                    self.has_unsaved_changes = False
                    
            except Exception as e:
                QMessageBox.critical(self, 'Save Error', f"Error saving numpy file: {str(e)}")
                self.status_bar.showMessage(f"Error saving numpy file: {str(e)}")
    def convert_star_to_numpy(self, star_data):
        """将STAR数据转换为numpy数组格式（6列：z1,z2,y1,y2,x1,x2）"""
        # 提取坐标
        x_center = star_data['_rlnCoordinateX'].astype(float)
        y_center = star_data['_rlnCoordinateY'].astype(float)
        z_center = star_data['_rlnCoordinateZ'].astype(float)
        
        # 假设固定的框大小（可以根据需要调整）
        box_size = 16  # 16x16x16的框
        
        # 计算框的边界
        x1 = x_center - box_size/2
        x2 = x_center + box_size/2
        y1 = y_center - box_size/2
        y2 = y_center + box_size/2
        z1 = z_center - box_size/2
        z2 = z_center + box_size/2
        
        # 创建numpy数组
        numpy_array = np.column_stack([z1, z2, y1, y2, x1, x2])
        
        # 如果STAR数据中有类别或置信度信息，可以扩展到8列
        if '_rlnClassNumber' in star_data.columns:
            class_col = star_data['_rlnClassNumber'].astype(float)
            if '_rlnAutopickFigureOfMerit' in star_data.columns:
                confidence = star_data['_rlnAutopickFigureOfMerit'].astype(float)
                numpy_array = np.column_stack([z1, z2, y1, y2, x1, x2, class_col, confidence])
            else:
                confidence = np.ones(len(star_data))  # 默认置信度
                numpy_array = np.column_stack([z1, z2, y1, y2, x1, x2, class_col, confidence])
        
        return numpy_array

    # 统一的读取坐标文件方法
    def open_coordinate_file(self):
        """打开坐标文件（支持STAR和numpy格式）"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open Coordinate File', '', 
            'Coordinate Files (*.star *.npy);;STAR Files (*.star);;Numpy Files (*.npy);;All Files (*)')
        
        if filename:
            try:
                # 根据文件扩展名判断格式
                if filename.endswith('.star'):
                    self.load_star_file(filename)
                elif filename.endswith('.npy'):
                    self.load_numpy_file(filename)
                else:
                    # 尝试自动检测格式
                    self.auto_detect_and_load_file(filename)
                    
            except Exception as e:
                QMessageBox.critical(self, 'Load Error', f'Error loading coordinate file: {str(e)}')
                self.status_bar.showMessage(f'Error loading file: {str(e)}')
                print(f"Coordinate file loading error: {e}")

    # 统一的保存坐标文件方法
    def save_coordinate_file(self):
        """保存坐标文件（支持多种格式）"""
        if self.star_data is None:
            self.status_bar.showMessage("No particle data to save")
            return
        
        # 弹出保存对话框，让用户选择格式
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, 'Save Coordinate File', '', 
            'STAR Files (*.star);;Numpy Files (*.npy);;All Files (*)')
        
        if filename:
            try:
                # 根据选择的过滤器或文件扩展名确定格式
                if selected_filter == 'STAR Files (*.star)' or filename.endswith('.star'):
                    self.save_star_format(filename)
                elif selected_filter == 'Numpy Files (*.npy)' or filename.endswith('.npy'):
                    self.save_numpy_format(filename)
                else:
                    # 默认保存为STAR格式
                    if not filename.endswith(('.star', '.npy')):
                        filename += '.star'
                    self.save_star_format(filename)
                    
                self.status_bar.showMessage(f"Saved coordinate file to {filename}")
                
                # 如果在编辑模式，清除未保存标记
                if self.edit_mode:
                    self.has_unsaved_changes = False
                    
            except Exception as e:
                QMessageBox.critical(self, 'Save Error', f"Error saving coordinate file: {str(e)}")
                self.status_bar.showMessage(f"Error saving file: {str(e)}")


def main():
    app = QApplication(sys.argv)
    viewer = MRCViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


def apply_simple_scientific_theme():
    """应用简化版科研主题"""
    stylesheet = """
        QMainWindow, QWidget {
            background-color: #fdf6e3;  /* 浅米色背景 */
            color: #586e75;             /* 深灰色文字 */
            font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
        }
        
        QGroupBox {
            background-color: rgba(238, 232, 213, 150);
            border: 1px solid #268bd2;  /* 蓝色边框 */
            margin-top: 1ex;
            font-weight: bold;
            color: #268bd2;
        }
        
        QPushButton {
            background-color: #eee8d5;
            color: #586e75;
            border: 1px solid #268bd2;
            padding: 6px 12px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #268bd2;
            color: white;
        }
        
        QPushButton:pressed {
            background-color: #1a6bab;
            color: white;
        }
        
        QPushButton:checked {
            background-color: #268bd2;
            color: white;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #93a1a1;
            height: 8px;
            background: #eee8d5;
            margin: 2px 0;
        }
        
        QSlider::handle:horizontal {
            background: #268bd2;
            border: 1px solid #1a6bab;
            width: 18px;
            margin: -2px 0;
            border-radius: 3px;
        }
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #eee8d5;
            color: #586e75;
            border: 1px solid #268bd2;
            padding: 4px;
            border-radius: 3px;
        }
        
        QTabBar::tab {
            background: #eee8d5;
            color: #586e75;
            padding: 8px 12px;
            margin: 2px;
            border: 1px solid #268bd2;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background: #268bd2;
            color: white;
            font-weight: bold;
        }
    """
    
    return stylesheet


def apply_solarized_light_theme(widget):
    """应用Solarized Light主题"""
    from PyQt5.QtGui import QPalette, QColor
    
    # Solarized Light 配色
    base03 = QColor(0, 43, 54)    # 深背景
    base02 = QColor(7, 54, 66)    # 背景
    base01 = QColor(88, 110, 117) # 注释/次要文字
    base00 = QColor(101, 123, 131)# 主要文字
    base0 = QColor(131, 148, 150) # 次要内容
    base1 = QColor(147, 161, 161) # 主要内容
    base2 = QColor(238, 232, 213)# 浅背景
    base3 = QColor(253, 246, 227)# 浅背景2
    yellow = QColor(181, 137, 0)  # 黄色
    orange = QColor(203, 75, 22)  # 橙色
    red = QColor(220, 50, 47)     # 红色
    magenta = QColor(211, 54, 130) # 品红
    violet = QColor(108, 113, 196) # 紫色
    blue = QColor(38, 139, 210)   # 蓝色
    cyan = QColor(42, 161, 152)   # 青色
    green = QColor(133, 153, 0)   # 绿色
    
    # 创建调色板
    palette = QPalette()
    
    # 主要背景和前景
    palette.setColor(QPalette.Window, base2)          # 窗口背景
    palette.setColor(QPalette.WindowText, base00)     # 窗口文字
    palette.setColor(QPalette.Base, base3)            # 文本编辑器背景
    palette.setColor(QPalette.AlternateBase, base2)   # 交替行背景
    palette.setColor(QPalette.ToolTipBase, base3)     # 工具提示背景
    palette.setColor(QPalette.ToolTipText, base00)    # 工具提示文字
    
    # 文本颜色
    palette.setColor(QPalette.Text, base00)           # 文本
    palette.setColor(QPalette.Button, base2)          # 按钮背景
    palette.setColor(QPalette.ButtonText, base00)     # 按钮文字
    palette.setColor(QPalette.BrightText, red)        # 高亮文字
    
    # 链接颜色
    palette.setColor(QPalette.Link, blue)
    palette.setColor(QPalette.LinkVisited, magenta)
    
    # 选择颜色
    palette.setColor(QPalette.Highlight, blue)        # 选中背景
    palette.setColor(QPalette.HighlightedText, base3) # 选中文字
    
    # 禁用状态
    palette.setColor(QPalette.Disabled, QPalette.Text, base1)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, base1)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, base1)
    
    widget.setPalette(palette)
    
    # 应用样式表
    widget.setStyleSheet(get_scientific_stylesheet(base2, base00, blue, red, green))


def get_scientific_stylesheet(  bg_color, text_color, accent_color, error_color, success_color):
    """获取科研风格的样式表"""
    return f"""
        QMainWindow, QDialog, QWidget {{
            background-color: {bg_color.name()};
            color: {text_color.name()};
            font-family: 'Segoe UI', 'Arial', sans-serif;
        }}
        
        QMenuBar {{
            background-color: {bg_color.lighter(105).name()};
            color: {text_color.name()};
            border-bottom: 1px solid {accent_color.name()};
        }}
        
        QMenuBar::item {{
            background: transparent;
            padding: 4px 8px;
        }}
        
        QMenuBar::item:selected {{
            background: {accent_color.name()};
            color: white;
        }}
        
        QMenuBar::item:pressed {{
            background: {accent_color.darker(120).name()};
            color: white;
        }}
        
        QMenu {{
            background-color: {bg_color.name()};
            color: {text_color.name()};
            border: 1px solid {accent_color.name()};
        }}
        
        QMenu::item {{
            padding: 4px 20px;
        }}
        
        QMenu::item:selected {{
            background-color: {accent_color.name()};
            color: white;
        }}
        
        QToolBar {{
            background-color: {bg_color.lighter(102).name()};
            border: none;
        }}
        
        QPushButton {{
            background-color: {bg_color.lighter(110).name()};
            color: {text_color.name()};
            border: 1px solid {accent_color.name()};
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: normal;
        }}
        
        QPushButton:hover {{
            background-color: {accent_color.name()};
            color: white;
        }}
        
        QPushButton:pressed {{
            background-color: {accent_color.darker(120).name()};
            color: white;
        }}
        
        QPushButton:checked {{
            background-color: {accent_color.name()};
            color: white;
        }}
        
        QGroupBox {{
            background-color: transparent;
            border: 1px solid {accent_color.name()};
            margin-top: 1ex;
            font-weight: bold;
            color: {accent_color.name()};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}
        
        QSlider::groove:horizontal {{
            border: 1px solid {text_color.name()};
            height: 8px;
            background: {bg_color.lighter(110).name()};
            margin: 2px 0;
        }}
        
        QSlider::handle:horizontal {{
            background: {accent_color.name()};
            border: 1px solid {accent_color.darker(120).name()};
            width: 18px;
            margin: -2px 0;
            border-radius: 3px;
        }}
        
        QScrollBar:vertical {{
            background: {bg_color.lighter(105).name()};
            width: 15px;
            margin: 22px 0 22px 0;
        }}
        
        QScrollBar::handle:vertical {{
            background: {accent_color.name()};
            min-height: 20px;
            border-radius: 4px;
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            background: {bg_color.lighter(110).name()};
            height: 20px;
            subcontrol-position: top;
            subcontrol-origin: margin;
        }}
        
        QLabel {{
            color: {text_color.name()};
        }}
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {bg_color.lighter(115).name()};
            color: {text_color.name()};
            border: 1px solid {accent_color.name()};
            padding: 4px;
            border-radius: 3px;
        }}
        
        QTabWidget::pane {{
            border: 1px solid {accent_color.name()};
            border-top: none;
        }}
        
        QTabBar::tab {{
            background: {bg_color.lighter(105).name()};
            color: {text_color.name()};
            padding: 8px 12px;
            margin: 2px;
            border: 1px solid {accent_color.name()};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected {{
            background: {accent_color.name()};
            color: white;
            font-weight: bold;
        }}
        
        QTabBar::tab:!selected {{
            margin-top: 2px;
        }}
        
        QStatusBar {{
            background-color: {bg_color.lighter(102).name()};
            border-top: 1px solid {accent_color.name()};
        }}
    """


def apply_simple_scientific_theme(widget):
    """应用简化版科研主题"""
    stylesheet = """
        QMainWindow, QWidget {
            background-color: #fdf6e3;  /* 浅米色背景 */
            color: #586e75;             /* 深灰色文字 */
            font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
        }
        
        QGroupBox {
            background-color: rgba(238, 232, 213, 150);
            border: 1px solid #268bd2;  /* 蓝色边框 */
            margin-top: 1ex;
            font-weight: bold;
            color: #268bd2;
        }
        
        QPushButton {
            background-color: #eee8d5;
            color: #586e75;
            border: 1px solid #268bd2;
            padding: 6px 12px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #268bd2;
            color: white;
        }
        
        QPushButton:pressed {
            background-color: #1a6bab;
            color: white;
        }
        
        QPushButton:checked {
            background-color: #268bd2;
            color: white;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #93a1a1;
            height: 8px;
            background: #eee8d5;
            margin: 2px 0;
        }
        
        QSlider::handle:horizontal {
            background: #268bd2;
            border: 1px solid #1a6bab;
            width: 18px;
            margin: -2px 0;
            border-radius: 3px;
        }
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #eee8d5;
            color: #586e75;
            border: 1px solid #268bd2;
            padding: 4px;
            border-radius: 3px;
        }
        
        QTabBar::tab {
            background: #eee8d5;
            color: #586e75;
            padding: 8px 12px;
            margin: 2px;
            border: 1px solid #268bd2;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background: #268bd2;
            color: white;
            font-weight: bold;
        }
    """
    
    widget.setStyleSheet(stylesheet)


def apply_lab_theme(widget):
    """应用实验室风格主题"""
    lab_stylesheet = """
        QMainWindow, QWidget {
            background-color: #f5f5f5;
            color: #333333;
            font-family: 'Helvetica Neue', 'Arial', sans-serif;
        }
        
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            margin-top: 1ex;
            color: #555555;
            font-weight: normal;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 3px;
            font-weight: 500;
        }
        
        QPushButton:hover {
            background-color: #45a049;
        }
        
        QPushButton:pressed {
            background-color: #3d8b40;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #ddd;
            height: 6px;
            background: #f0f0f0;
            border-radius: 3px;
        }
        
        QSlider::handle:horizontal {
            background: #4CAF50;
            border: 1px solid #3d8b40;
            width: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
            padding: 8px;
            border-radius: 3px;
        }
        
        QLineEdit:focus {
            border: 2px solid #4CAF50;
        }
    """
    widget.setStyleSheet(lab_stylesheet)


def apply_academic_blue_theme(widget):
    """应用学术蓝主题"""
    academic_stylesheet = """
    QMainWindow, QWidget {
        background-color: #f8f9fa;
        color: #2c3e50;
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 9pt;
    }
    
    QGroupBox {
        background-color: #ffffff;
        border: 2px solid #3498db;
        margin-top: 1ex;
        color: #2980b9;
        font-weight: bold;
        padding: 10px;  /* 增加内边距 */
    }
    
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        padding: 6px 12px;  /* 减少padding */
        border-radius: 4px;
        font-weight: bold;
        min-height: 20px;  /* 设置最小高度 */
    }
    
    QPushButton:hover {
        background-color: #2980b9;
    }
    
    QPushButton:pressed {
        background-color: #1f618d;
    }
    
    QPushButton:disabled {
        background-color: #bdc3c7;
    }
    
    QSlider::groove:horizontal {
        border: 1px solid #bdc3c7;
        height: 6px;
        background: #ecf0f1;
        border-radius: 3px;
    }
    
    QSlider::handle:horizontal {
        background: #3498db;
        border: 1px solid #2980b9;
        width: 16px;  /* 减小手柄大小 */
        margin: -5px 0;
        border-radius: 8px;
    }
    
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #ffffff;
        color: #2c3e50;
        border: 2px solid #3498db;
        padding: 4px 6px;  /* 减少padding */
        border-radius: 3px;
        min-height: 20px;  /* 设置最小高度 */
    }
    
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        width: 16px;  /* 减小微调按钮大小 */
    }
    
    QTabBar::tab {
        background: #ecf0f1;
        color: #2c3e50;
        padding: 6px 12px;  /* 减少padding */
        border: 1px solid #3498db;
        border-bottom: none;
        min-width: 150px;  /* 设置最小宽度 */
        min-height: 35px; /* 设置最小高度 */
    }
    
    QTabBar::tab:selected {
        background: #3498db;
        color: white;
        font-weight: bold;
    }
    
    QLabel {
        color: #2c3e50;
        min-height: 15px;  /* 确保标签有足够的高度 */
    }
    
    QComboBox QAbstractItemView {
        border: 1px solid #3498db;
        background: white;
    }
    
    QScrollBar:vertical {
        background: #ecf0f1;
        width: 12px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background: #3498db;
        border-radius: 6px;
        min-height: 20px;
    }
    """
    widget.setStyleSheet(academic_stylesheet)


def apply_material_theme(widget):
    """应用Material Design风格"""
    material_stylesheet = """
        QMainWindow, QWidget {
            background-color: #fafafa;
            color: #212121;
            font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
        }
        
        QGroupBox {
            background-color: white;
            border: 1px solid #e0e0e0;
            margin-top: 1ex;
            font-weight: 500;
            color: #616161;
            border-radius: 4px;
        }
        
        QPushButton {
            background-color: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        QPushButton:hover {
            background-color: #1976D2;
        }
        
        QPushButton:pressed {
            background-color: #0D47A1;
        }
        
        QPushButton:disabled {
            background-color: #BDBDBD;
        }
        
        QSlider::groove:horizontal {
            border: none;
            height: 4px;
            background: #E0E0E0;
            border-radius: 2px;
        }
        
        QSlider::handle:horizontal {
            background: #2196F3;
            border: none;
            width: 20px;
            margin: -8px 0;
            border-radius: 10px;
        }
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: white;
            color: #212121;
            border: 1px solid #E0E0E0;
            padding: 8px;
            border-radius: 4px;
        }
        
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
            border: 2px solid #2196F3;
        }
        
        QTabBar::tab {
            background: transparent;
            color: #757575;
            padding: 12px 24px;
            margin: 0;
            border: none;
            border-bottom: 2px solid transparent;
        }
        
        QTabBar::tab:selected {
            color: #2196F3;
            border-bottom: 2px solid #2196F3;
        }
    """
    widget.setStyleSheet(material_stylesheet)
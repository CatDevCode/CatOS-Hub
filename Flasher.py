import sys
import os
import requests
import serial.tools.list_ports
import platform
import threading
import time
import subprocess
import esptool
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QComboBox, QLabel, QProgressBar,
                             QDialog, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QFont, QFontDatabase

class CustomMessageBox(QDialog):
    def __init__(self, parent=None, title="", message="", message_type="info", buttons="ok"):
        super().__init__(parent)
        self.title = title
        self.message = message
        self.message_type = message_type
        self.buttons = buttons
        self.result = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setFixedSize(450, 250)
        self.setModal(True)
        
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: black;
                border: 2px solid white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_label = QLabel(self.title)
        title_font = QFont(self.parent().custom_font)
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        if self.message_type == "success":
            title_label.setStyleSheet("color: #00ff00;")
        elif self.message_type == "error":
            title_label.setStyleSheet("color: #ff0000;")
        elif self.message_type == "warning":
            title_label.setStyleSheet("color: #ffff00;")
        else:
            title_label.setStyleSheet("color: white;")
            
        title_label.setAlignment(Qt.AlignCenter)
        
        message_label = QLabel(self.message)
        message_font = QFont(self.parent().custom_font)
        message_font.setPointSize(12)
        message_label.setFont(message_font)
        message_label.setStyleSheet("color: white;")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        
        button_layout = QHBoxLayout()
        
        if self.buttons == "ok":
            ok_button = QPushButton("OK")
            ok_button.setFont(self.parent().custom_font)
            ok_button.setFixedSize(100, 35)
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: black;
                    color: white;
                    border: 2px solid white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #333;
                }
                QPushButton:pressed {
                    background-color: #555;
                }
            """)
            ok_button.clicked.connect(self.accept)
            button_layout.addStretch()
            button_layout.addWidget(ok_button)
            button_layout.addStretch()
            
        elif self.buttons == "yesno":
            yes_button = QPushButton("Yes")
            yes_button.setFont(self.parent().custom_font)
            yes_button.setFixedSize(80, 35)
            yes_button.setStyleSheet("""
                QPushButton {
                    background-color: black;
                    color: white;
                    border: 2px solid white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #333;
                }
                QPushButton:pressed {
                    background-color: #555;
                }
            """)
            yes_button.clicked.connect(self.accept)
            
            no_button = QPushButton("No")
            no_button.setFont(self.parent().custom_font)
            no_button.setFixedSize(80, 35)
            no_button.setStyleSheet("""
                QPushButton {
                    background-color: black;
                    color: white;
                    border: 2px solid white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #333;
                }
                QPushButton:pressed {
                    background-color: #555;
                }
            """)
            no_button.clicked.connect(self.reject)
            
            button_layout.addStretch()
            button_layout.addWidget(yes_button)
            button_layout.addSpacing(20)
            button_layout.addWidget(no_button)
            button_layout.addStretch()
        
        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

class DownloadThread(QThread):
    progress_updated = pyqtSignal(int)
    download_finished = pyqtSignal(bool, str)
    
    def __init__(self, repo_owner, repo_name, cache_dir):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cache_dir = cache_dir
        
    def run(self):
        try:
            # получаем инфу
            latest_release_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
            response = requests.get(latest_release_url)
            if response.status_code != 200:
                self.download_finished.emit(False, f"Ошибка при получении информации о релизе: {response.status_code}")
                return
                
            release_data = response.json()
            release_tag = release_data['tag_name']

            firmware_url = None
            for asset in release_data.get('assets', []):
                if asset['name'] == 'firmware.bin':
                    firmware_url = asset['browser_download_url']
                    break
            
            if not firmware_url:
                self.download_finished.emit(False, "Файл firmware.bin не найден в релизе")
                return
            
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # сохраняем инфу
            with open(os.path.join(self.cache_dir, 'current_release.txt'), 'w') as f:
                f.write(release_tag)
            
            # ииии скачиваем
            response = requests.get(firmware_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            firmware_path = os.path.join(self.cache_dir, 'firmware.bin')
            downloaded_size = 0
            
            with open(firmware_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress_updated.emit(progress)
            
            self.download_finished.emit(True, f"The firmware has been downloaded successfully: {release_tag}")
            
        except Exception as e:
            self.download_finished.emit(False, f"Error: {str(e)}")

class FlashThread(QThread):
    progress_updated = pyqtSignal(int)
    flash_finished = pyqtSignal(bool, str)
    console_message = pyqtSignal(str)
    
    def __init__(self, port, flash_files):
        super().__init__()
        self.port = port
        self.flash_files = flash_files
        
    def run(self):
        try:
            self.console_message.emit("The ESP32 firmware process begins...")
            
            # чекаем файлы
            for file_info in self.flash_files:
                if not os.path.exists(file_info["path"]):
                    error_msg = f"❌ File not found: {file_info['path']}"
                    self.console_message.emit(error_msg)
                    self.flash_finished.emit(False, error_msg)
                    return
            
            command = [
                '--chip', 'esp32',
                '--port', self.port,
                '--baud', '460800',
                '--before', 'default_reset',
                '--after', 'hard_reset',
                'write_flash',
                '-z',
                '--flash_mode', 'dio',
                '--flash_freq', '80m',
                '--flash_size', '4MB'
            ]
            
            for file_info in self.flash_files:
                command.extend([file_info["offset"], file_info["path"]])
            
            self.console_message.emit(f"The firmware command: esptool.py {' '.join(command)}")
            
            self.console_message.emit("Connecting and upload fimware to ESP32...")
            self.progress_updated.emit(10)
            
            try:
                esptool.main(command)
                self.console_message.emit("The firmware is completed successfully!")
                self.progress_updated.emit(100)
                self.flash_finished.emit(True, "ESP32 has been successfully stitched!")
                
            except SystemExit as e:
                if e.code == 0:
                    self.console_message.emit("The firmware is completed successfully!")
                    self.progress_updated.emit(100)
                    self.flash_finished.emit(True, "ESP32 has been successfully stitched!")
                else:
                    error_msg = f"Firmware error ({e.code})"
                    self.console_message.emit(error_msg)
                    self.flash_finished.emit(False, error_msg)
                    
            except Exception as e:
                error_msg = f"Error when calling esptool: {str(e)}"
                self.console_message.emit(error_msg)
                self.flash_finished.emit(False, error_msg)
            
        except Exception as e:
            error_msg = f"Critical error: {str(e)}"
            self.console_message.emit(error_msg)
            self.flash_finished.emit(False, error_msg)

class EraseThread(QThread):
    progress_updated = pyqtSignal(int)
    erase_finished = pyqtSignal(bool, str)
    console_message = pyqtSignal(str)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
        
    def run(self):
        try:
            self.console_message.emit("The cleaning of the ESP32 flash memory begins...")
            
            command = [
                '--chip', 'esp32',
                '--port', self.port,
                '--baud', '460800',
                'erase_flash'
            ]
            
            self.console_message.emit(f"The cleaning command: esptool.py {' '.join(command)}")
            self.progress_updated.emit(20)
            
            try:
                esptool.main(command)
                self.console_message.emit("The flash memory cleanup has been completed successfully!")
                self.progress_updated.emit(100)
                self.erase_finished.emit(True, "ESP32 flash memory has been successfully cleared!")
                
            except SystemExit as e:
                if e.code == 0:
                    self.console_message.emit("The flash memory cleanup has been completed successfully!")
                    self.progress_updated.emit(100)
                    self.erase_finished.emit(True, "The ESP32 flash memory has been successfully cleared!")
                else:
                    error_msg = f"Cleaning error (code {e.code})"
                    self.console_message.emit(error_msg)
                    self.erase_finished.emit(False, error_msg)
                    
            except Exception as e:
                error_msg = f"Error when calling esptool: {str(e)}"
                self.console_message.emit(error_msg)
                self.erase_finished.emit(False, error_msg)
            
        except Exception as e:
            error_msg = f"Critical error: {str(e)}"
            self.console_message.emit(error_msg)
            self.erase_finished.emit(False, error_msg)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # шрифт
        self.custom_font = self.load_font("VCROSDMonoRUSbyD.ttf")
        
        self.initUI()
    
    def load_font(self, font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                font_name = font_families[0]
                print(f"front loaded: {font_name}")
                return QFont(font_name, 11)
        print("font is not loaded")
        return QFont("Arial", 11)
    
    def get_available_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = []
        for port in ports:
            port_list.append(port.device)
        return port_list
    
    def initUI(self):
        self.setWindowTitle("CatOs flasher")
        self.setFixedSize(600, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        
        pixmap = QPixmap("background.jpg")
        if not pixmap.isNull():
            pixmap = pixmap.scaled(600, 600, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        else:
            print("error with background.jpg")
        
        bottom_panel = QWidget()
        bottom_panel.setFixedHeight(50)
        bottom_panel.setStyleSheet("background-color: black;")
        
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(20, 5, 20, 5)
        
        self.port_combo = QComboBox()
        self.port_combo.setFont(self.custom_font)
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: black;
                color: white;
                border: 2px solid white;
                padding: 5px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: black;
                color: white;
                border: 2px solid white;
            }
        """)
        
        available_ports = self.get_available_ports()
        if available_ports:
            self.port_combo.addItem("Select port...")
            for port in available_ports:
                self.port_combo.addItem(port)
        else:
            self.port_combo.addItem("No ports found")
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setFont(self.custom_font)
        self.ok_button.setFixedSize(80, 35)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border: 2px solid white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        
        bottom_layout.addWidget(self.port_combo)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.ok_button)
        
        layout.addWidget(self.image_label, 1)
        layout.addWidget(bottom_panel)
        
        self.ok_button.clicked.connect(self.open_flash_window)
    
    def open_flash_window(self):
        selected_port = self.port_combo.currentText()
        if selected_port != "Select port..." and selected_port != "No ports found":
            self.flash_window = FlashWindow(self.custom_font, selected_port)
            self.flash_window.show()
            self.close()

class FlashWindow(QMainWindow):
    def __init__(self, custom_font, selected_port):
        super().__init__()
        self.custom_font = custom_font
        self.selected_port = selected_port
        self.download_thread = None
        self.flash_thread = None
        self.erase_thread = None
        self.initUI()
        
    def get_catos_version(self):
        cache_dir = "fimware"
        version_file = os.path.join(cache_dir, 'current_release.txt')
        
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    version = f.read().strip()
                    return version if version else "Unknown"
            except:
                return "Unknown"
        else:
            return "Unknown"
        
    def initUI(self):
        self.setWindowTitle(f"CatOs flasher - ({self.selected_port})")
        self.setFixedSize(600, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        overlay_layout = QVBoxLayout(central_widget)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        
        background_widget = QWidget()
        background_widget.setStyleSheet("background-color: black;")
        
        background_layout = QVBoxLayout(background_widget)
        background_layout.setContentsMargins(0, 0, 0, 0)
        
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        
        pixmap = QPixmap("main.jpg")
        if not pixmap.isNull():
            pixmap = pixmap.scaled(600, 600, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            image_label.setPixmap(pixmap)
        else:
            print("Error with main.jpg")
        
        background_layout.addWidget(image_label)

        large_font = QFont(self.custom_font)
        large_font.setPointSize(22)

        version_font = QFont(self.custom_font)
        version_font.setPointSize(14)
        
        catos_label = QLabel(background_widget)
        catos_label.setText(f"CatOs on\n{self.selected_port}")
        catos_label.setFont(large_font)
        catos_label.setStyleSheet("color: white; background-color: transparent;")
        catos_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        catos_label.setGeometry(15, 30, 300, 100)
        
        self.download_button = QPushButton("Download Firmware", background_widget)
        self.download_button.setFont(self.custom_font)
        self.download_button.setFixedSize(200, 40)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border: 2px solid white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        self.download_button.setGeometry(45, 143, 200, 40)
        self.download_button.clicked.connect(self.download_firmware)
        
        self.progress_bar = QProgressBar(background_widget)
        self.progress_bar.setGeometry(45, 193, 200, 40)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid white;
                background-color: black;
                text-align: center;
                color: black;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: white;
            }
        """)
        
        progress_font = QFont(self.custom_font)
        progress_font.setPointSize(12)
        self.progress_bar.setFont(progress_font)
        
        self.flash_button = QPushButton("Flash", background_widget)
        self.flash_button.setFont(self.custom_font)
        self.flash_button.setFixedSize(200, 40)
        self.flash_button.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border: 2px solid white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        self.flash_button.setGeometry(45, 430, 200, 40)
        self.flash_button.clicked.connect(self.flash_firmware)
        
        self.flash_progress_bar = QProgressBar(background_widget)
        self.flash_progress_bar.setGeometry(45, 490, 200, 40)
        self.flash_progress_bar.setMinimum(0)
        self.flash_progress_bar.setMaximum(100)
        self.flash_progress_bar.setValue(0)
    
        self.flash_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid white;
                background-color: black;
                text-align: center;
                color: black;
                font-weight: bold;
            }
            QProgress_bar::chunk {
                background-color: white;
            }
        """)
        
        self.flash_progress_bar.setFont(progress_font)
        
        self.erase_button = QPushButton("Erase ESP32", background_widget)
        self.erase_button.setFont(self.custom_font)
        self.erase_button.setFixedSize(200, 40)
        self.erase_button.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border: 2px solid white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        self.erase_button.setGeometry(45, 555, 200, 40)
        self.erase_button.clicked.connect(self.erase_esp32)
        
        self.catos_version_label = QLabel(background_widget)
        catos_version = self.get_catos_version()
        self.catos_version_label.setText(f"CatOs: {catos_version}")
        self.catos_version_label.setFont(version_font)
        self.catos_version_label.setStyleSheet("color: white; background-color: transparent;")
        self.catos_version_label.setAlignment(Qt.AlignLeft)
        self.catos_version_label.setGeometry(15, 290, 350, 35)
        
        os_label = QLabel(background_widget)
        os_name = platform.system()
        os_label.setText(f"OC: {os_name}")
        os_label.setFont(version_font)
        os_label.setStyleSheet("color: white; background-color: transparent;")
        os_label.setAlignment(Qt.AlignLeft)
        os_label.setGeometry(15, 320, 350, 35)
        
        flasher_version_label = QLabel(background_widget)
        flasher_version_label.setText("CatOs Flasher: v0.1")
        flasher_version_label.setFont(version_font)
        flasher_version_label.setStyleSheet("color: white; background-color: transparent;")
        flasher_version_label.setAlignment(Qt.AlignLeft)
        flasher_version_label.setGeometry(15, 350, 350, 35)
        
        self.console = QTextEdit(background_widget)
        self.console.setGeometry(308, 190, 280, 400)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: 2px solid white;
                font-family: "Courier New";
                font-size: 10px;
            }
        """)
        self.console.setReadOnly(True)
        self.console.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.console.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.console.append(f"Selected port: {self.selected_port}")
        
        overlay_layout.addWidget(background_widget)
    
    def download_firmware(self):
        self.download_button.setEnabled(False)
        
        self.progress_bar.setValue(0)
        
        self.console.append("Starting firmware download...")
        
        cache_dir = "fimware"
        self.download_thread = DownloadThread("CatDevCode", "CatOs", cache_dir)
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.download_finished.connect(self.download_complete)
        self.download_thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        if value % 10 == 0:
            self.console.append(f"Download progress: {value}%")
    
    def download_complete(self, success, message):
        self.download_button.setEnabled(True)
        
        if success:
            catos_version = self.get_catos_version()
            self.catos_version_label.setText(f"CatOs: {catos_version}")
        
        if success:
            self.console.append("Firmware download completed successfully!")
        else:
            self.console.append("Firmware download failed!")
        
        if success:
            msg_box = CustomMessageBox(self, "Success!", message, "success")
        else:
            msg_box = CustomMessageBox(self, "Error", message, "error")
        
        msg_box.exec_()
    
    def flash_firmware(self):
        # чекаем наличие файлов
        flash_files = [
            {"path": "flash/bootloader.bin", "offset": "0x1000"},
            {"path": "flash/partitions.bin", "offset": "0x8000"},
            {"path": "flash/boot_app0.bin", "offset": "0xE000"},
            {"path": "fimware/firmware.bin", "offset": "0x10000"}
        ]

        missing_files = []
        for file_info in flash_files:
            if not os.path.exists(file_info["path"]):
                missing_files.append(file_info["path"])
        
        if missing_files:
            error_msg = f"Missing files for the firmware:\n" + "\n".join(missing_files)
            self.console.append(error_msg)
            msg_box = CustomMessageBox(self, "Error", error_msg, "error")
            msg_box.exec_()
            return
        
        self.flash_button.setEnabled(False)
        
        self.flash_progress_bar.setValue(0)
        
        self.console.append("Starting ESP32 flash process...")
        
        self.flash_thread = FlashThread(self.selected_port, flash_files)
        self.flash_thread.progress_updated.connect(self.update_flash_progress)
        self.flash_thread.flash_finished.connect(self.flash_complete)
        self.flash_thread.console_message.connect(self.console.append)
        self.flash_thread.start()
    
    def update_flash_progress(self, value):
        self.flash_progress_bar.setValue(value)
    
    def flash_complete(self, success, message):
        self.flash_button.setEnabled(True)
        
        if success:
            self.console.append("Flash process completed successfully!")
            self.console.append("You can now reset ESP32 to normal mode")
        else:
            self.console.append("Flash process failed!")
        
        if success:
            msg_box = CustomMessageBox(self, "Success!", message, "success")
        else:
            msg_box = CustomMessageBox(self, "Error", message, "error")
        
        msg_box.exec_()
    
    def erase_esp32(self):
        confirm_msg = CustomMessageBox(
            self, 
            "Warning!", 
            "This operation will completely clear the ESP32 flash memory.\n"
            "All data will be permanently deleted.\n\n"
            "Are you sure you want to continue?",
            "warning",
            "yesno"
        )
        
        result = confirm_msg.exec_()
        if result != QDialog.Accepted:
            self.console.append("Cleaning canceled by the user")
            return
        
        self.erase_button.setEnabled(False)
        self.flash_progress_bar.setValue(0)
        
        self.console.append("Starting ESP32 flash memory erase...")
        
        self.erase_thread = EraseThread(self.selected_port)
        self.erase_thread.progress_updated.connect(self.update_flash_progress)
        self.erase_thread.erase_finished.connect(self.erase_complete)
        self.erase_thread.console_message.connect(self.console.append)
        self.erase_thread.start()
    
    def erase_complete(self, success, message):
        self.erase_button.setEnabled(True)
        
        if success:
            self.console.append("Flash memory erase completed successfully!")
        else:
            self.console.append("Flash memory erase failed!")


        if success:
            msg_box = CustomMessageBox(self, "Success!", message, "success")
        else:
            msg_box = CustomMessageBox(self, "Error", message, "error")
        
        msg_box.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet("QMainWindow { background-color: black; }")
    
    main_window = MainWindow()
    main_window.show()
    
    sys.exit(app.exec_())
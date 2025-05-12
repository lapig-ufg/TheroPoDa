import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QSplitter, QComboBox, QSpinBox, QDateEdit, QFileDialog,
    QDialog, QTextEdit
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QIcon


import ee
import os
import subprocess

def initialize_ee():
    """Initialize Earth Engine using gcloud credentials"""
    try:
        # First try normal initialization
        ee.Initialize()
        return True
    except (ee.ee_exception.EEException, Exception):
        # If that fails, guide user through gcloud auth
        response = QMessageBox.question(
            None,
            "Authentication Required",
            "Earth Engine needs Google Cloud authentication.\n\n"
            "We'll open a terminal window where you need to:\n"
            "1. Run the command that appears\n"
            "2. Login with your Google account\n"
            "3. Return here when done\n\n"
            "Proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if response == QMessageBox.Yes:
            try:
                # Platform-specific terminal commands
                if os.name == 'nt':  # Windows
                    subprocess.Popen(['start', 'cmd', '/k', 'gcloud auth application-default login'], shell=True)
                elif os.uname().sysname == 'Darwin':  # macOS
                    subprocess.Popen(['open', '-a', 'Terminal', '-e', 'gcloud auth application-default login'])
                else:  # Linux
                    subprocess.Popen(['x-terminal-emulator', '-e', 'gcloud auth application-default login'])
                
                QMessageBox.information(
                    None,
                    "Next Steps",
                    "1. Complete the login in the terminal\n"
                    "2. Close the terminal when done\n"
                    "3. Restart this application"
                )
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "Error",
                    f"Couldn't open terminal: {str(e)}\n\n"
                    "Please manually run this command:\n"
                    "gcloud auth application-default login"
                )
        return False


class AnalysisThread(QThread):
    """Thread to run the analysis without freezing the GUI"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            from main import run_analysis
            run_analysis(**self.params)
            self.finished_signal.emit(True)
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False)

class TheroPoDaGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        if not initialize_ee():
            sys.exit(1)  # Exit if authentication fails
        # if not check_ee_auth():
        #     self.show_auth_dialog()
        self.setWindowTitle("TheroPoDa - Time Series Analysis Tool")
        self.setWindowIcon(QIcon('icon.ico'))
        self.setGeometry(100, 100, 800, 400)
        self.analysis_thread = None
        self.setup_ui()

    def initialize_ee(self):
        """Initialize EE with authentication check"""
        try:
            ee.Initialize()
            return True
        except ee.ee_exception.EEException:
            auth_dialog = EEAuthDialog(self)
            return auth_dialog.exec_() == QDialog.Accepted
    
    def show_auth_dialog(self):
        auth_dialog = EEAuthDialog(self)
        if auth_dialog.exec_() != QDialog.Accepted:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "You must authenticate with Earth Engine to use this application."
            )
            sys.exit(1)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Input Panel
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        
        # Earth Engine Asset
        self.asset_input = self._create_input_field(
            "Earth Engine Asset Path:",
            "users/vieiramesquita/LAPIG_FieldSamples/...",
            input_layout
        )
        
        # ID Field
        self.id_field_input = self._create_input_field(
            "ID Field Name:", 
            "e.g., ID_POINTS",
            input_layout
        )
             
        # Choose output folder
        output_layout = QHBoxLayout()
        self.output_folder_input = QLineEdit()
        self.output_folder_input.setPlaceholderText("Select output folder...")
        output_folder_btn = QPushButton("Browse...")
        output_folder_btn.clicked.connect(self.select_output_folder)
        output_layout.addWidget(QLabel("Output Folder:"))
        output_layout.addWidget(self.output_folder_input)
        output_layout.addWidget(output_folder_btn)
        input_layout.addLayout(output_layout)
        
        # Collection Type
        input_layout.addWidget(QLabel("Satellite Collection:"))
        self.collection_combo = QComboBox()
        self.collection_combo.addItems(["Sentinel", "Landsat"])
        input_layout.addWidget(self.collection_combo)
        
        # Output Name
        self.output_input = self._create_input_field(
            "Output File Name:", 
            "e.g., output_results",
            input_layout
        )
        
        # Date Range
        input_layout.addWidget(QLabel("Date Range:"))
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit(QDate(2019, 1, 1))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate(2025, 1, 1))
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("Start:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("End:"))
        date_layout.addWidget(self.end_date)
        input_layout.addLayout(date_layout)
        
        # Window Size
        input_layout.addWidget(QLabel("Standardization Window (days):"))
        self.window_size = QSpinBox()
        self.window_size.setRange(1, 30)
        self.window_size.setValue(15)
        input_layout.addWidget(self.window_size)
        
        # Number of cores used
        input_layout.addWidget(QLabel("Number of Cores:"))
        self.core_spin = QSpinBox()
        self.core_spin.setRange(1, os.cpu_count() or 4)
        self.core_spin.setValue(min(12, os.cpu_count() or 4))
        input_layout.addWidget(self.core_spin)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.clicked.connect(self.run_analysis)
        btn_layout.addWidget(self.run_btn)
        input_layout.addLayout(btn_layout)
        
        # Status
        self.status_label = QLabel("Ready to analyze")
        self.status_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.status_label)
        
        main_layout.addWidget(input_panel)

    def select_output_folder(self):
        """Open dialog to select output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.output_folder_input.setText(folder)
    
    def _create_input_field(self, label_text, placeholder, layout):
        """Helper to create consistent input fields"""
        label = QLabel(label_text)
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        layout.addWidget(label)
        layout.addWidget(field)
        return field

    def validate_inputs(self):
        """Validate all user inputs"""
        if not self.asset_input.text():
            QMessageBox.warning(self, "Error", "Please enter an Earth Engine Asset Path")
            return False
        if not self.id_field_input.text():
            QMessageBox.warning(self, "Error", "Please enter an ID Field Name")
            return False
        if not self.output_input.text():
            QMessageBox.warning(self, "Error", "Please enter an Output File Name")
            return False
        if self.start_date.date() >= self.end_date.date():
            QMessageBox.warning(self, "Error", "Start date must be before end date")
            return False
        if not self.output_folder_input.text():
            QMessageBox.warning(self, "Error", "Please select an output folder")
            return False
        return True

    def run_analysis(self):
        """Start the analysis process directly"""
        if not self.validate_inputs():
            return
            
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Analysis is already running!")
            return
            
        try:
            ee.Initialize()
        except:
            self.show_auth_dialog()
            return
            
        self.status_label.setText("Running analysis...")
        self.run_btn.setEnabled(False)
        
        output_folder = self.output_folder_input.text()
        
        # Prepare parameters
        params = {
            'asset': self.asset_input.text(),
            'id_field': self.id_field_input.text(),
            'collection': self.collection_combo.currentText(),
            'output_name': self.output_input.text(),
            'output_folder': output_folder,
            'start_date': self.start_date.date().toString("yyyy-MM-dd"),
            'end_date': self.end_date.date().toString("yyyy-MM-dd"),
            'window': self.window_size.value(),
            'n_cores': self.core_spin.value()
        }
        
        # Create and start thread
        self.analysis_thread = AnalysisThread(params)
        self.analysis_thread.update_signal.connect(self.update_status)
        self.analysis_thread.finished_signal.connect(self.analysis_completed)
        self.analysis_thread.start()

    def update_status(self, message):
        """Update status label with progress"""
        self.status_label.setText(message)

    def analysis_completed(self, success):
        """Handle analysis completion"""
        self.run_btn.setEnabled(True)
        if success:
            self.status_label.setText("Analysis completed successfully!")
            QMessageBox.information(self, "Success", "Analysis completed successfully!")
        else:
            self.status_label.setText("Analysis failed")
            QMessageBox.critical(self, "Error", "Analysis failed - check console for details")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            reply = QMessageBox.question(
                self,
                'Analysis Running',
                'Terminate the running analysis process?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.analysis_thread.terminate()
                self.analysis_thread.wait()
        event.accept()

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    window = TheroPoDaGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
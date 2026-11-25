import os
import platform
import shutil
import subprocess
import sys

import ee

try:
    from PyQt5.QtCore import QDate, QThread, pyqtSignal, Qt
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import (
        QApplication,
        QComboBox,
        QDateEdit,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit(
        f"PyQt5 is required for gui.py ({exc}). "
        "In WSL/Linux, install PyQt5 or use CLI (main.py) / Dashboard (streamlit run dashboard.py)."
    ) from exc


def _is_wsl() -> bool:
    return "microsoft" in platform.release().lower()


def _open_auth_terminal():
    """Open an interactive terminal for Earth Engine authentication across Windows, WSL, macOS, and Linux."""
    if os.name == "nt":
        subprocess.Popen(["start", "cmd", "/k", "earthengine authenticate"], shell=True)
    elif _is_wsl():
        subprocess.Popen(["wsl.exe", "earthengine", "authenticate"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Terminal", "-e", "earthengine authenticate"])
    else:
        term = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or shutil.which("xterm")
        if not term:
            raise RuntimeError("No terminal emulator found in PATH.")
        subprocess.Popen([term, "-e", "earthengine authenticate"])


def initialize_ee(project=None):
    """Initialize Earth Engine using existing or gcloud credentials."""
    try:
        kwargs = {"opt_url": "https://earthengine-highvolume.googleapis.com"}
        if project:
            kwargs["project"] = project
        ee.Initialize(**kwargs)
        return True
    except Exception:
        response = QMessageBox.question(
            None,
            "Authentication Required",
            "Earth Engine needs Google Cloud authentication.\n\n"
            "We'll open a terminal window where you need to:\n"
            "1. Login with your Google account\n"
            "2. Return here when done\n\n"
            "Proceed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if response == QMessageBox.Yes:
            try:
                _open_auth_terminal()
                QMessageBox.information(
                    None,
                    "Next Steps",
                    "1. Complete the login in the terminal\n"
                    "2. Close the terminal when done\n"
                    "3. Restart or re-run the analysis",
                )
            except Exception as exc:
                QMessageBox.critical(
                    None,
                    "Error",
                    f"Couldn't open terminal: {exc}\n\nPlease run manually:\nearthengine authenticate",
                )
        return False


class AnalysisThread(QThread):
    """Background thread to run the analysis without freezing the GUI."""

    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            from main import run_analysis

            output_parquet = run_analysis(**self.params)
            self.finished_signal.emit(True, output_parquet)
        except Exception as exc:
            self.update_signal.emit(f"Error: {exc}")
            self.finished_signal.emit(False, str(exc))


class TheroPoDaGUI(QMainWindow):
    """Main desktop GUI for TheroPoDa v2."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TheroPoDa v2 - Time Series & Trend Analysis")
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setGeometry(100, 100, 780, 620)
        self.analysis_thread = None
        self.dashboard_proc = None
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        asset_layout = QHBoxLayout()
        self.asset_input = QLineEdit()
        self.asset_input.setPlaceholderText("GEE Asset path or local file (.gpkg, .shp, .geojson, .parquet)")
        browse_asset_btn = QPushButton("Browse File...")
        browse_asset_btn.clicked.connect(self.select_vector_file)
        layout.addWidget(QLabel("Vector Input (GEE Asset or Local File):"))
        asset_layout.addWidget(self.asset_input)
        asset_layout.addWidget(browse_asset_btn)
        layout.addLayout(asset_layout)
        self.id_field_input = self._create_input_field("ID Field Name:", "e.g., ID_POINTS", layout)
        self.project_input = self._create_input_field(
            "Earth Engine Project ID (optional):", "e.g., ee-vieiramesquita", layout
        )

        # Output folder
        folder_layout = QHBoxLayout()
        self.output_folder_input = QLineEdit()
        self.output_folder_input.setPlaceholderText("Select output folder...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.select_output_folder)
        folder_layout.addWidget(QLabel("Output Folder:"))
        folder_layout.addWidget(self.output_folder_input)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)

        self.output_input = self._create_input_field("Output File Name:", "e.g., output_results", layout)

        # Collection
        layout.addWidget(QLabel("Satellite Collection:"))
        self.collection_combo = QComboBox()
        self.collection_combo.addItems(["Sentinel", "Landsat"])
        layout.addWidget(self.collection_combo)

        # Mask configuration
        layout.addWidget(QLabel("LULC Mask Mode:"))
        self.mask_combo = QComboBox()
        self.mask_combo.addItems(
            ["None", "mapbiomas-pasture", "mapbiomas-pasture-grasslands", "Custom Asset"]
        )
        self.mask_combo.currentTextChanged.connect(self._on_mask_mode_changed)
        layout.addWidget(self.mask_combo)

        self.custom_mask_input = self._create_input_field(
            "Custom Mask Asset (Image or ImageCollection):",
            "e.g., projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3",
            layout,
        )
        self.mask_classes_input = self._create_input_field(
            "Mask Classes (comma-separated, optional):", "e.g., 15 or 15, 11, 12", layout
        )
        self.mask_start_year_input = self._create_input_field(
            "Mask Start Year (only if bands have no year in name):", "e.g., 1985", layout
        )
        self._on_mask_mode_changed(self.mask_combo.currentText())

        # Date Range
        layout.addWidget(QLabel("Date Range:"))
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit(QDate(2019, 1, 1))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate(2025, 1, 1))
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("Start:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("End:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Window & Cores
        spin_layout = QHBoxLayout()
        self.window_size = QSpinBox()
        self.window_size.setRange(1, 30)
        self.window_size.setValue(15)
        self.core_spin = QSpinBox()
        self.core_spin.setRange(1, os.cpu_count() or 4)
        self.core_spin.setValue(min(12, os.cpu_count() or 4))
        spin_layout.addWidget(QLabel("Window (days):"))
        spin_layout.addWidget(self.window_size)
        spin_layout.addWidget(QLabel("Cores:"))
        spin_layout.addWidget(self.core_spin)
        layout.addLayout(spin_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.clicked.connect(self.run_analysis)
        self.dashboard_btn = QPushButton("Open Dashboard")
        self.dashboard_btn.clicked.connect(self.open_dashboard)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.dashboard_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("Ready to analyze")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def _on_mask_mode_changed(self, text):
        is_custom = text == "Custom Asset"
        is_none = text == "None"
        self.custom_mask_input.setEnabled(is_custom)
        self.mask_classes_input.setEnabled(not is_none)
        self.mask_start_year_input.setEnabled(is_custom)

    def select_vector_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local Vector File",
            "",
            "Vector Files (*.gpkg *.shp *.geojson *.json *.parquet *.geoparquet *.zip);;All Files (*)",
        )
        if file_path:
            self.asset_input.setText(file_path)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.output_folder_input.setText(folder)

    def _create_input_field(self, label_text, placeholder, layout):
        label = QLabel(label_text)
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        layout.addWidget(label)
        layout.addWidget(field)
        return field

    def validate_inputs(self):
        if not self.asset_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter an Earth Engine Asset Path")
            return False
        if not self.id_field_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter an ID Field Name")
            return False
        if not self.output_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter an Output File Name")
            return False
        if not self.output_folder_input.text().strip():
            QMessageBox.warning(self, "Error", "Please select an output folder")
            return False
        if self.start_date.date() >= self.end_date.date():
            QMessageBox.warning(self, "Error", "Start date must be before end date")
            return False
        if self.mask_combo.currentText() == "Custom Asset" and not self.custom_mask_input.text().strip():
            QMessageBox.warning(self, "Error", "Please enter a Custom Mask Asset path")
            return False
        return True

    def run_analysis(self):
        if not self.validate_inputs():
            return
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Analysis is already running!")
            return

        project = self.project_input.text().strip() or None
        if not initialize_ee(project=project):
            return

        mask_mode = self.mask_combo.currentText()
        if mask_mode == "None":
            mask_val = None
        elif mask_mode == "Custom Asset":
            mask_val = self.custom_mask_input.text().strip()
        else:
            mask_val = mask_mode

        classes_raw = self.mask_classes_input.text().strip() or None
        start_year_raw = self.mask_start_year_input.text().strip()
        mask_start_year = int(start_year_raw) if start_year_raw.isdigit() else None

        self.status_label.setText("Running analysis...")
        self.run_btn.setEnabled(False)

        params = {
            "asset": self.asset_input.text().strip(),
            "id_field": self.id_field_input.text().strip(),
            "collection": self.collection_combo.currentText(),
            "output_name": self.output_input.text().strip(),
            "output_folder": self.output_folder_input.text().strip(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "window": self.window_size.value(),
            "n_cores": self.core_spin.value(),
            "project": project,
            "mask": mask_val,
            "mask_classes": [classes_raw] if classes_raw else None,
            "mask_start_year": mask_start_year,
        }

        self.analysis_thread = AnalysisThread(params)
        self.analysis_thread.update_signal.connect(self.update_status)
        self.analysis_thread.finished_signal.connect(self.analysis_completed)
        self.analysis_thread.start()

    def open_dashboard(self):
        """Launch the Streamlit dashboard in the selected output folder."""
        dashboard_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.py")
        if not os.path.exists(dashboard_script):
            QMessageBox.warning(self, "Error", f"dashboard.py not found at {dashboard_script}")
            return
        env = os.environ.copy()
        folder = self.output_folder_input.text().strip()
        if folder:
            env["THEROPODA_DATA_DIR"] = folder
        self.dashboard_proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", dashboard_script],
            env=env,
        )
        self.status_label.setText("Dashboard launched in browser (Streamlit)")

    def update_status(self, message):
        self.status_label.setText(message)

    def analysis_completed(self, success, info):
        self.run_btn.setEnabled(True)
        if success:
            self.status_label.setText(f"Completed: {os.path.basename(info)}")
            QMessageBox.information(self, "Success", f"Analysis completed!\nOutput: {info}")
        else:
            self.status_label.setText("Analysis failed")
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{info}")

    def closeEvent(self, event):
        if self.analysis_thread and self.analysis_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Analysis Running",
                "Terminate the running analysis process?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.analysis_thread.terminate()
                self.analysis_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = TheroPoDaGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

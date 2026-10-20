# -*- coding: utf-8 -*-
"""
=============================================================================
THESIS PROJECT / TEOAE RESEARCH - ITS BIOMEDICAL ENGINEERING
Main Orchestrator: TEOAE GUI & Signal Processing Pipeline Interface
=============================================================================
"""

import sys
import os
import datetime
import threading
import subprocess
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

# =====================================================================
# MODULE IMPORTS (Encapsulation of Core Acquisition & DSP Algorithms)
# =====================================================================
import modul_perekaman
import modul_analisisfix

# ---------------------------------------------------------------------
# CYBER / TERMINAL UI STYLESHEET (RASPBERRY PI OPTIMIZED)
# ---------------------------------------------------------------------
QSS = """
QWidget {
    background-color: #050810; 
    color: #4a7a9c;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}
QLineEdit {
    background-color: #08101a;
    border: 1px solid #1a2b3c;
    border-radius: 4px;
    color: #00e5ff;
    padding: 6px 10px;
    font-weight: bold;
}
QLineEdit:focus { border: 1px solid #00e5ff; }

#Panel {
    background-color: transparent;
    border: 1px solid #1a2b3c;
    border-radius: 4px;
}

#BtnRecord {
    background-color: rgba(41, 98, 255, 0.05);
    color: #2962ff;
    border: 1px solid #2962ff;
    border-radius: 4px;
    font-weight: bold;
    letter-spacing: 2px;
    height: 35px;
}
#BtnRecord:hover { background-color: rgba(41, 98, 255, 0.2); }

#BtnAnalyze {
    background-color: rgba(0, 230, 118, 0.05);
    color: #00e676;
    border: 1px solid #00e676;
    border-radius: 4px;
    font-weight: bold;
    letter-spacing: 2px;
    height: 35px;
}
#BtnAnalyze:hover { background-color: rgba(0, 230, 118, 0.2); }
#BtnAnalyze:disabled { color: #2d4a3e; border: 1px solid #2d4a3e; }

QTextEdit {
    background-color: transparent;
    border: 1px solid #1a2b3c;
    border-radius: 4px;
    color: #00e5ff;
    padding: 8px;
}
#StatusPill {
    border: 1px solid #00e676;
    border-radius: 12px;
    padding: 4px 15px;
    color: #00e676;
    font-weight: bold;
    background-color: rgba(0, 230, 118, 0.05);
}
"""

def _tag(text):
    label = QLabel(f"// {text.upper()}")
    label.setStyleSheet("color:#4a7a9c; font-size:10px; letter-spacing:2px; margin-bottom: 5px;")
    return label

class TouchLineEdit(QLineEdit):
    _onboard_process = None

    def focusInEvent(self, event):
        super().focusInEvent(event)
        try:
            if TouchLineEdit._onboard_process is None or TouchLineEdit._onboard_process.poll() is not None:
                env = os.environ.copy()
                TouchLineEdit._onboard_process = subprocess.Popen(
                    ['onboard'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
                )
        except Exception as e:
            print(f"[Keyboard] Failed to launch virtual keyboard: {e}")

class CommunicationSignals(QObject):
    log_signal = pyqtSignal(str)
    recording_finished = pyqtSignal(bool)
    analysis_finished = pyqtSignal(object, str, list, float, float, float)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TEOAE ANALYZER - COMMAND CENTER")
        self.setStyleSheet(QSS)

        self.signals = CommunicationSignals()
        self.signals.log_signal.connect(self._append_log)
        self.signals.recording_finished.connect(self._on_recording_completed)
        self.signals.analysis_finished.connect(self._on_analysis_completed)

        self.canvas_main = None
        self.canvas_snr = None
        self._setup_ui()
        self._start_clock()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)        
        self.showMaximized()

    def _start_clock(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)

    def _update_time(self):
        self.lbl_time.setText(datetime.datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))

    def _setup_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget); main_layout.setContentsMargins(5,5,5,5); main_layout.setSpacing(5)

        # --------- HEADER SECTION ---------
        header_layout = QHBoxLayout()
        title_column = QVBoxLayout(); title_column.setSpacing(2)
        box_title = QHBoxLayout()
        dot_label = QLabel("<>"); dot_label.setStyleSheet("color:#00e5ff; font-size:18px;")
        title_text = QLabel("TEOAE  ANALYZER"); title_text.setStyleSheet("color:#ffffff; font-size:18px; font-weight:bold; letter-spacing:3px;")
        box_title.addWidget(dot_label); box_title.addWidget(title_text); box_title.addStretch()
        subtitle = QLabel("ITS BIOMEDICAL ENG"); subtitle.setStyleSheet("color:#2a4a6a; font-size:9px; letter-spacing:2px; margin-left: 18px;")
        title_column.addLayout(box_title); title_column.addWidget(subtitle)
        header_layout.addLayout(title_column); header_layout.addStretch()
        
        self.lbl_time = QLabel("YYYY-MM-DD   HH:MM:SS"); self.lbl_time.setStyleSheet("color:#4a7a9c; font-size:11px; margin-right: 15px;")
        header_layout.addWidget(self.lbl_time, alignment=Qt.AlignmentFlag.AlignBottom)
        self.sys_ready_pill = QLabel("[ SYSTEM READY ]"); self.sys_ready_pill.setObjectName("StatusPill")
        header_layout.addWidget(self.sys_ready_pill, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.btn_exit = QPushButton("EXIT [X]")
        self.btn_exit.setFixedHeight(23)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 23, 68, 0.05); color: #ff1744;
                border: 1px solid #ff1744; border-radius: 4px; font-weight: bold;
                letter-spacing: 2px; height: 28px; padding: 0px 12px;
            }
            QPushButton:hover { background-color: rgba(255, 23, 68, 0.2); }
        """)
        self.btn_exit.clicked.connect(self.close)
        header_layout.addWidget(self.btn_exit, alignment=Qt.AlignmentFlag.AlignBottom)
        main_layout.addLayout(header_layout)
       
        # --------- MAIN BODY SECTION ---------
        body_layout = QHBoxLayout(); body_layout.setSpacing(15)
        
        # -- SIDEBAR (PIPELINE INPUT CONTROLS) --
        sidebar_layout = QVBoxLayout(); sidebar_layout.setSpacing(15)
        sidebar_widget = QWidget(); sidebar_widget.setFixedWidth(200)
        sl = QVBoxLayout(sidebar_widget); sl.setContentsMargins(0,0,0,0); sl.setSpacing(12)
        
        sl.addWidget(_tag("Hardware Config"))
        self.in_port = TouchLineEdit("/dev/ttyUSB0"); sl.addWidget(self.in_port)
        self.in_dur = TouchLineEdit("30"); sl.addWidget(self.in_dur)
        
        sl.addSpacing(5)
        sl.addWidget(_tag("Target Filename"))
        self.in_file = TouchLineEdit(f"REC_{datetime.datetime.now().strftime('%H%M%S')}.csv")
        sl.addWidget(self.in_file)

        self.btn_record = QPushButton("▶ START RECORDING"); self.btn_record.setObjectName("BtnRecord")
        self.btn_record.clicked.connect(self._start_recording); sl.addWidget(self.btn_record)

        self.btn_analyze = QPushButton("⬡ ANALYZE DATA"); self.btn_analyze.setObjectName("BtnAnalyze")
        self.btn_analyze.clicked.connect(self._start_analysis); sl.addWidget(self.btn_analyze)
        
        sl.addSpacing(5)
        sl.addWidget(_tag("System Log"))
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)
        sl.addWidget(self.log_area)
        
        sidebar_layout.addWidget(sidebar_widget); body_layout.addLayout(sidebar_layout)

        # -- VISUALIZATION PANEL & ORCHESTRATION RESULTS --
        visualization_panel = QVBoxLayout(); visualization_panel.setSpacing(15)
        self.banner_container = QHBoxLayout(); self.banner_container.setSpacing(10)

        self.frame_result = QFrame(); self.frame_result.setObjectName("Panel")
        self.lay_result = QHBoxLayout(self.frame_result)
        self.lbl_result_title = QLabel("RESULT :"); self.lbl_result_title.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lbl_result_val = QLabel("WAITING"); self.lbl_result_val.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lay_result.addWidget(self.lbl_result_title); self.lay_result.addWidget(self.lbl_result_val); self.lay_result.addStretch()
        
        self.frame_recording = QFrame(); self.frame_recording.setObjectName("Panel")
        self.lay_recording = QHBoxLayout(self.frame_recording)
        self.lbl_recording_title = QLabel("RECORDING :"); self.lbl_recording_title.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lbl_recording_val = QLabel("READY"); self.lbl_recording_val.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lay_recording.addWidget(self.lbl_recording_title); self.lay_recording.addWidget(self.lbl_recording_val); self.lay_recording.addStretch()

        self.banner_container.addWidget(self.frame_result); self.banner_container.addWidget(self.frame_recording)
        visualization_panel.addLayout(self.banner_container)
        
        # --- TOP PANEL: WAVEFORM & WWR ---
        self.frame_top = QFrame(); self.frame_top.setObjectName("Panel")
        self.lay_top_main = QHBoxLayout(self.frame_top); self.lay_top_main.setContentsMargins(12,12,12,12)

        self.lay_plot_left = QVBoxLayout()
        self.lbl_wf_title = _tag("TEOAE Signal - Waveform")
        self.lay_plot_left.addWidget(self.lbl_wf_title)
        self.lbl_top = QLabel("Waiting for data stream..."); self.lbl_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay_plot_left.addWidget(self.lbl_top)
        self.lay_top_main.addLayout(self.lay_plot_left, stretch=8)

        self.lay_wwr_right = QVBoxLayout()
        self.lay_wwr_right.setContentsMargins(10, 20, 20, 10); self.lay_wwr_right.addStretch()
        self.lbl_wwr_tag = QLabel("WWR"); self.lbl_wwr_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_wwr_tag.setStyleSheet("color:#4a7a9c; font-size:36px; font-weight:bold; font-style:italic;")
        self.lbl_wwr_pct = QLabel("0.0%"); self.lbl_wwr_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_wwr_pct.setStyleSheet("color:#ffffff; font-size:38px; font-weight:bold; font-style:italic;")
        self.lay_wwr_right.addWidget(self.lbl_wwr_tag); self.lay_wwr_right.addWidget(self.lbl_wwr_pct)
        self.lay_wwr_right.addStretch()
        self.lay_top_main.addLayout(self.lay_wwr_right, stretch=2)
        visualization_panel.addWidget(self.frame_top, stretch=5)

        # --- BOTTOM ROW PANEL ---
        bottom_row = QHBoxLayout(); bottom_row.setSpacing(15)
        self.frame_bot_l = QFrame(); self.frame_bot_l.setObjectName("Panel")
        self.lay_bot_l = QVBoxLayout(self.frame_bot_l); self.lay_bot_l.setContentsMargins(12,12,12,12)
        self.lay_bot_l.addWidget(_tag("SNR Bins - Signal VS Noise"))
        self.lbl_bot_l = QLabel("SNR Plot Area"); self.lbl_bot_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay_bot_l.addWidget(self.lbl_bot_l)
        bottom_row.addWidget(self.frame_bot_l, stretch=5)

        self.frame_bot_r = QFrame(); self.frame_bot_r.setObjectName("Panel")
        self.lay_bot_r = QVBoxLayout(self.frame_bot_r); self.lay_bot_r.setContentsMargins(12,12,12,12)
        self.lay_bot_r.addWidget(_tag("Numerical Readout"))
        self.num_grid = QGridLayout(); self.num_grid.setVerticalSpacing(7)
        self.lay_bot_r.addLayout(self.num_grid); self.lay_bot_r.addSpacing(3)

        self.frame_rad = QFrame(); self.frame_rad.setObjectName("Panel")
        self.frame_rad.setStyleSheet("background-color: rgba(0, 229, 255, 0.03);")
        self.lay_rad_box = QHBoxLayout(self.frame_rad)
        self.lbl_rad_tag = QLabel("// RAD2D"); self.lbl_rad_tag.setStyleSheet("font-size:9px; color:#4a7a9c;")
        self.lbl_rad_status = QLabel("WAITING"); self.lbl_rad_status.setStyleSheet("font-weight:bold; font-size:13px; color:#4a7a9c;")
        self.lay_rad_box.addWidget(self.lbl_rad_tag); self.lay_rad_box.addStretch(); self.lay_rad_box.addWidget(self.lbl_rad_status)
        self.lay_bot_r.addWidget(self.frame_rad); self.lay_bot_r.addStretch()
        bottom_row.addWidget(self.frame_bot_r, stretch=4)

        visualization_panel.addLayout(bottom_row, stretch=4)
        body_layout.addLayout(visualization_panel); main_layout.addLayout(body_layout)

        # --------- FOOTER SECTION ---------
        footer_layout = QHBoxLayout()
        self.lbl_footer_status = QLabel("WAITING - Ready"); self.lbl_footer_status.setStyleSheet("color:#00e5ff;")
        lbl_footer_branding = QLabel("ITS Biomed . 2026"); lbl_footer_branding.setStyleSheet("color:#2a4a6a;")
        footer_layout.addWidget(self.lbl_footer_status); footer_layout.addStretch(); footer_layout.addWidget(lbl_footer_branding); main_layout.addLayout(footer_layout)
        
    def _append_log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f'<span style="color:#2a4a6a;">[{timestamp}]</span> <span style="color:#00e5ff;">{message}</span>')

    def _start_recording(self):
        self.btn_record.setEnabled(False); self.btn_analyze.setEnabled(False)
        self._update_banner_status("RECORDING", "Capturing TEOAE signal...", "#ff9100")
        threading.Thread(target=self._recording_worker, daemon=True).start()

    def _recording_worker(self):
        port, duration, filename = self.in_port.text(), int(self.in_dur.text()), self.in_file.text()
        if not filename.endswith('.csv'): filename += '.csv'
        is_success, _ = modul_perekaman.rekam_data(port, 921600, duration, filename, log_callback=self.signals.log_signal.emit)
        self.signals.recording_finished.emit(is_success)

    def _on_recording_completed(self, is_success):
        self.btn_record.setEnabled(True); self.btn_analyze.setEnabled(True)
        if is_success: 
            self._update_banner_status("READY", "Data captured successfully.", "#00e5ff")
        else: 
            self._update_banner_status("FAILED", "Check serial connection.", "#ff1744")

    def _start_analysis(self):
        filename = self.in_file.text().strip()
        if not filename.endswith('.csv'): filename += '.csv'
        csv_folder = "/home/teoae/teoae/Data_Primer/csv"
        full_path = os.path.join(csv_folder, filename)
        if not os.path.exists(full_path): 
            self._append_log(f"<span style='color:#ff1744;'>ERROR: '{filename}' not found!</span>"); return
        self.btn_analyze.setEnabled(False); self._append_log("Processing DSP Pipeline...")
        threading.Thread(target=self._analysis_worker, args=(full_path,), daemon=True).start()

    def _analysis_worker(self, full_file_path):
        try:
            # Calling core analysis functions from the decoupled signal processing module
            fig, status, snr_data, wwr, csc, rad_dist = modul_analisisfix.proses_data_oae(full_file_path, log_callback=self.signals.log_signal.emit)
            self.signals.analysis_finished.emit(fig, status, snr_data, wwr, csc, rad_dist)
        except Exception as e:
            self.signals.log_signal.emit(f"<span style='color:#ff1744;'>CRASH: {str(e)}</span>")
            self.signals.analysis_finished.emit(None, "ERROR", [], 0.0, 0.0, 0.0)

    def _on_analysis_completed(self, fig, status, snr_data, wwr, csc, rad_dist):
        self.btn_analyze.setEnabled(True)
        if status == "ERROR" or fig is None: return

        result_color = "#00e676" if status == "PASS" else "#ff1744"
        self.lbl_result_title.setStyleSheet(f"font-weight:bold; color: {result_color};")
        self.lbl_result_val.setText(status)
        self.lbl_result_val.setStyleSheet(f"color: {result_color}; font-weight:bold; font-size:12px;")
        self.frame_result.setStyleSheet(f"#Panel {{ border: 1px solid {result_color}; }}")

        rec_status = "VALID" if csc > 60 else "INVALID"
        rec_color = "#00e676" if csc > 60 else "#ff1744"
        self.lbl_recording_val.setText(f"{rec_status} ({csc:.1f}%)")
        self.frame_recording.setStyleSheet(f"#Panel {{ border: 1px solid {rec_color}; }}")

        wwr_color = "#00e676" if wwr >= 70 else "#ff1744"
        self.lbl_wwr_pct.setText(f"{wwr:.1f}%")
        self.lbl_wwr_pct.setStyleSheet(f"color: {wwr_color}; font-size:38px; font-weight:bold; font-style:italic;")

        rad_pass_text = "Pass" if rad_dist <= 2.2 else "Refer"
        rad_color = "#00e676" if rad_pass_text == "Pass" else "#ff1744"
        self.lbl_rad_status.setText(f"RAD2D : {rad_dist:.2f} ({rad_pass_text})")
        self.lbl_rad_status.setStyleSheet(f"color: {rad_color}; font-weight:bold; font-size:13px;")

        if self.lbl_top: self.lbl_top.deleteLater(); self.lbl_top = None
        if self.canvas_main: self.canvas_main.deleteLater()
        
        fig.patch.set_facecolor("#050810")
        for ax in fig.get_axes():
            ax.set_facecolor("#050810")
            ax.tick_params(colors="#4a7a9c", labelsize=8)
            for name, spine in ax.spines.items():
                if name in ['bottom', 'left']: spine.set_visible(True); spine.set_edgecolor("#1a2b3c")
                else: spine.set_visible(False)
                    
        self.canvas_main = FigureCanvas(fig); self.lay_plot_left.addWidget(self.canvas_main)
        self._render_snr_bars(snr_data)
        self._render_numerics(snr_data)

    def _update_banner_status(self, status, description, color):
        self.lbl_result_val.setText(status); self.lbl_result_val.setStyleSheet(f"color: {color}; font-weight:bold;")
        self.frame_result.setStyleSheet(f"#Panel {{ border: 1px solid {color}; }}")
        self.lbl_recording_val.setText(description); self.lbl_recording_val.setStyleSheet(f"color: {color}; font-weight:bold;")
        self.frame_recording.setStyleSheet(f"#Panel {{ border: 1px solid {color}; }}")
        self.lbl_footer_status.setText(f"{status} - {description}"); self.lbl_footer_status.setStyleSheet(f"color:{color};")

    def _render_snr_bars(self, snr_data):
        if self.lbl_bot_l: self.lbl_bot_l.deleteLater(); self.lbl_bot_l = None
        if self.canvas_snr: self.canvas_snr.deleteLater()
        freqs = [row[0] for row in snr_data]    
        snr_vals = [float(row[4]) for row in snr_data] 
        noi_vals = [float(row[3]) for row in snr_data] 
        fig, ax = plt.subplots(figsize=(4.5, 2))
        fig.patch.set_facecolor("#050810"); fig.subplots_adjust(left=0.05, right=0.95, top=0.85, bottom=0.25)
        ax.set_facecolor("#050810")
        x = np.arange(len(freqs)); width = 0.3
        ax.bar(x - width/2, snr_vals, width, color='#00e5ff', label='Signal')
        ax.bar(x + width/2, noi_vals, width, color='#1a3b4c', label='Noise')
        leg = ax.legend(loc='upper right', frameon=False, fontsize=7)
        for text in leg.get_texts(): text.set_color('#4a7a9c')
        ax.set_yticks([]); ax.set_xticks(x)
        ax.set_xticklabels([f"{float(f)/1000:.1f}k".replace(".0", "") for f in freqs])
        ax.tick_params(colors="#4a7a9c", labelsize=8)
        for s in ax.spines.values(): s.set_visible(False)
        ax.spines['bottom'].set_visible(True); ax.spines['bottom'].set_edgecolor("#1a2b3c")
        self.canvas_snr = FigureCanvas(fig); self.lay_bot_l.addWidget(self.canvas_snr)
        
    def _render_numerics(self, snr_data):
        for i in reversed(range(self.num_grid.count())): 
            widget = self.num_grid.itemAt(i).widget()
            if widget: widget.setParent(None)
        headers = ["FREQ", "SNR", "STATUS"]
        for col, text in enumerate(headers):
            lbl = QLabel(text); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#2a4a6a; font-weight:bold; font-size:11px; border-bottom: 1px solid #1a2b3c; padding-bottom: 3px;")
            self.num_grid.addWidget(lbl, 0, col)
        for row_idx, row_data in enumerate(snr_data, start=1):
            freq_label = QLabel(f"{row_data[0]} Hz"); freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_label.setStyleSheet("color:#4a7a9c; font-size: 11px;")
            val_label = QLabel(f"{row_data[1]} dB"); val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_label.setStyleSheet("color:#00e5ff; font-size: 11px; font-weight: bold;")
            stat_label = QLabel(f"{row_data[2]}"); stat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color_code = "#00e676" if row_data[2]=="PASS" else "#ff9100"
            stat_label.setStyleSheet(f"color:{color_code}; font-weight:bold; font-size: 11px;")
            self.num_grid.addWidget(freq_label, row_idx, 0); self.num_grid.addWidget(val_label, row_idx, 1); self.num_grid.addWidget(stat_label, row_idx, 2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    sys.exit(app.exec())

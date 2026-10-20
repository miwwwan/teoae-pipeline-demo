# -*- coding: utf-8 -*-
"""
=============================================================================
PROYEK SKRIPSI / RISET TEOAE - ITS BIOMEDICAL ENGINEERING
File Utama (Main Orchestrator): Antarmuka & Pipeline Analisis Sinyal TEOAE
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
# IMPOR MODUL ANALISIS & PEREKAMAN (Enkapsulasi Algoritma Inti)
# =====================================================================
import modul_perekaman
import modul_analisisfix

# ---------------------------------------------------------------------
# CYBER / TERMINAL UI STYLESHEET (RASPI OPTIMIZED)
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
    l = QLabel(f"// {text.upper()}")
    l.setStyleSheet("color:#4a7a9c; font-size:10px; letter-spacing:2px; margin-bottom: 5px;")
    return l

class TouchLineEdit(QLineEdit):
    _onboard_proc = None

    def focusInEvent(self, event):
        super().focusInEvent(event)
        try:
            if TouchLineEdit._onboard_proc is None or TouchLineEdit._onboard_proc.poll() is not None:
                env = os.environ.copy()
                TouchLineEdit._onboard_proc = subprocess.Popen(
                    ['onboard'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
                )
        except Exception as e:
            print(f"[Keyboard] Gagal buka: {e}")

class CommSignals(QObject):
    log_signal = pyqtSignal(str)
    recording_finished = pyqtSignal(bool)
    analysis_finished = pyqtSignal(object, str, list, float, float, float)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TEOAE ANALYZER - COMMAND CENTER")
        self.setStyleSheet(QSS)

        self.signals = CommSignals()
        self.signals.log_signal.connect(self._add_log)
        self.signals.recording_finished.connect(self._on_rec_done)
        self.signals.analysis_finished.connect(self._on_analysis_done)

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
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setContentsMargins(5,5,5,5); layout.setSpacing(5)

        # --------- HEADER ---------
        header = QHBoxLayout()
        title_col = QVBoxLayout(); title_col.setSpacing(2)
        box_title = QHBoxLayout()
        dot = QLabel("<>"); dot.setStyleSheet("color:#00e5ff; font-size:18px;")
        t = QLabel("TEOAE  ANALYZER"); t.setStyleSheet("color:#ffffff; font-size:18px; font-weight:bold; letter-spacing:3px;")
        box_title.addWidget(dot); box_title.addWidget(t); box_title.addStretch()
        s = QLabel("ITS BIOMEDICAL ENG"); s.setStyleSheet("color:#2a4a6a; font-size:9px; letter-spacing:2px; margin-left: 18px;")
        title_col.addLayout(box_title); title_col.addWidget(s)
        header.addLayout(title_col); header.addStretch()
        
        self.lbl_time = QLabel("YYYY-MM-DD   HH:MM:SS"); self.lbl_time.setStyleSheet("color:#4a7a9c; font-size:11px; margin-right: 15px;")
        header.addWidget(self.lbl_time, alignment=Qt.AlignmentFlag.AlignBottom)
        self.sys_ready_pill = QLabel("[ SYSTEM READY ]"); self.sys_ready_pill.setObjectName("StatusPill")
        header.addWidget(self.sys_ready_pill, alignment=Qt.AlignmentFlag.AlignBottom)
        
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
        header.addWidget(self.btn_exit, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
       
        # --------- MAIN BODY ---------
        body = QHBoxLayout(); body.setSpacing(15)
        
        # -- SIDEBAR (PIPELINE INPUT CONTROLS) --
        sidebar = QVBoxLayout(); sidebar.setSpacing(15)
        sidebar_widget = QWidget(); sidebar_widget.setFixedWidth(200)
        sl = QVBoxLayout(sidebar_widget); sl.setContentsMargins(0,0,0,0); sl.setSpacing(12)
        
        sl.addWidget(_tag("Hardware Config"))
        self.in_port = TouchLineEdit("/dev/ttyUSB0"); sl.addWidget(self.in_port)
        self.in_dur = TouchLineEdit("30"); sl.addWidget(self.in_dur)
        
        sl.addSpacing(5)
        sl.addWidget(_tag("Target Filename"))
        self.in_file = TouchLineEdit(f"REC_{datetime.datetime.now().strftime('%H%M%S')}.csv")
        sl.addWidget(self.in_file)

        self.btn_rec = QPushButton("▶ START RECORDING"); self.btn_rec.setObjectName("BtnRecord")
        self.btn_rec.clicked.connect(self._start_rec); sl.addWidget(self.btn_rec)

        self.btn_ana = QPushButton("⬡ ANALYZE DATA"); self.btn_ana.setObjectName("BtnAnalyze")
        self.btn_ana.clicked.connect(self._start_analysis); sl.addWidget(self.btn_ana)
        
        sl.addSpacing(5)
        sl.addWidget(_tag("System Log"))
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)
        sl.addWidget(self.log_area)
        
        sidebar.addWidget(sidebar_widget); body.addLayout(sidebar)

        # -- VISUALIZATION PANEL & HASIL ORCHESTRATION --
        viz_panel = QVBoxLayout(); viz_panel.setSpacing(15)
        self.banner_container = QHBoxLayout(); self.banner_container.setSpacing(10)

        self.frame_res = QFrame(); self.frame_res.setObjectName("Panel")
        self.lay_res = QHBoxLayout(self.frame_res)
        self.lbl_res_title = QLabel("RESULT :"); self.lbl_res_title.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lbl_res_val = QLabel("WAITING"); self.lbl_res_val.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lay_res.addWidget(self.lbl_res_title); self.lay_res.addWidget(self.lbl_res_val); self.lay_res.addStretch()
        
        self.frame_rec = QFrame(); self.frame_rec.setObjectName("Panel")
        self.lay_rec = QHBoxLayout(self.frame_rec)
        self.lbl_rec_title = QLabel("RECORDING :"); self.lbl_rec_title.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lbl_rec_val = QLabel("READY"); self.lbl_rec_val.setStyleSheet("font-weight:bold; color:#4a7a9c;")
        self.lay_rec.addWidget(self.lbl_rec_title); self.lay_rec.addWidget(self.lbl_rec_val); self.lay_rec.addStretch()

        self.banner_container.addWidget(self.frame_res); self.banner_container.addWidget(self.frame_rec)
        viz_panel.addLayout(self.banner_container)
        
        # --- PANEL WAVEFORM & WWR ---
        self.frame_top = QFrame(); self.frame_top.setObjectName("Panel")
        self.lay_top_main = QHBoxLayout(self.frame_top); self.lay_top_main.setContentsMargins(12,12,12,12)

        self.lay_plot_kiri = QVBoxLayout()
        self.lbl_wf_title = _tag("Sinyal TEOAE - Waveform")
        self.lay_plot_kiri.addWidget(self.lbl_wf_title)
        self.lbl_top = QLabel("Waiting for data stream..."); self.lbl_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay_plot_kiri.addWidget(self.lbl_top)
        self.lay_top_main.addLayout(self.lay_plot_kiri, stretch=8)

        self.lay_wwr_kanan = QVBoxLayout()
        self.lay_wwr_kanan.setContentsMargins(10, 20, 20, 10); self.lay_wwr_kanan.addStretch()
        self.lbl_wwr_tag = QLabel("WWR"); self.lbl_wwr_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_wwr_tag.setStyleSheet("color:#4a7a9c; font-size:36px; font-weight:bold; font-style:italic;")
        self.lbl_wwr_pct = QLabel("0.0%"); self.lbl_wwr_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_wwr_pct.setStyleSheet("color:#ffffff; font-size:38px; font-weight:bold; font-style:italic;")
        self.lay_wwr_kanan.addWidget(self.lbl_wwr_tag); self.lay_wwr_kanan.addWidget(self.lbl_wwr_pct)
        self.lay_wwr_kanan.addStretch()
        self.lay_top_main.addLayout(self.lay_wwr_kanan, stretch=2)
        viz_panel.addWidget(self.frame_top, stretch=5)

        bot_row = QHBoxLayout(); bot_row.setSpacing(15)
        self.frame_bot_l = QFrame(); self.frame_bot_l.setObjectName("Panel")
        self.lay_bot_l = QVBoxLayout(self.frame_bot_l); self.lay_bot_l.setContentsMargins(12,12,12,12)
        self.lay_bot_l.addWidget(_tag("SNR Bins - Signal VS Noise"))
        self.lbl_bot_l = QLabel("SNR Plot Area"); self.lbl_bot_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay_bot_l.addWidget(self.lbl_bot_l)
        bot_row.addWidget(self.frame_bot_l, stretch=5)

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
        bot_row.addWidget(self.frame_bot_r, stretch=4)

        viz_panel.addLayout(bot_row, stretch=4)
        body.addLayout(viz_panel); layout.addLayout(body)

        footer = QHBoxLayout()
        self.lbl_footer_status = QLabel("WAITING - Ready"); self.lbl_footer_status.setStyleSheet("color:#00e5ff;")
        lbl_footer_branding = QLabel("ITS Biomed . 2026"); lbl_footer_branding.setStyleSheet("color:#2a4a6a;")
        footer.addWidget(self.lbl_footer_status); footer.addStretch(); footer.addWidget(lbl_footer_branding); layout.addLayout(footer)
        
    def _add_log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f'<span style="color:#2a4a6a;">[{ts}]</span> <span style="color:#00e5ff;">{msg}</span>')

    def _start_rec(self):
        self.btn_rec.setEnabled(False); self.btn_ana.setEnabled(False)
        self._update_banner("RECORDING", "Capturing TEOAE signal...", "#ff9100")
        threading.Thread(target=self._rec_worker, daemon=True).start()

    def _rec_worker(self):
        port, dur, fn = self.in_port.text(), int(self.in_dur.text()), self.in_file.text()
        if not fn.endswith('.csv'): fn += '.csv'
        ok, _ = modul_perekaman.rekam_data(port, 921600, dur, fn, log_callback=self.signals.log_signal.emit)
        self.signals.recording_finished.emit(ok)

    def _on_rec_done(self, ok):
        self.btn_rec.setEnabled(True); self.btn_ana.setEnabled(True)
        if ok: self._update_banner("READY", "Data captured successfully.", "#00e5ff")
        else: self._update_banner("FAILED", "Check serial connection.", "#ff1744")

    def _start_analysis(self):
        fn = self.in_file.text().strip()
        if not fn.endswith('.csv'): fn += '.csv'
        folder_csv = "/home/teoae/teoae/Data_Primer/csv"
        full_path = os.path.join(folder_csv, fn)
        if not os.path.exists(full_path): 
            self._add_log(f"<span style='color:#ff1744;'>ERROR: '{fn}' not found!</span>"); return
        self.btn_ana.setEnabled(False); self._add_log("Processing DSP Pipeline...")
        threading.Thread(target=self._ana_worker, args=(full_path,), daemon=True).start()

    def _ana_worker(self, path_lengkap):
        try:
            # Memanggil fungsi inti dari modul analisis sinyal terpisah
            fig, status, snr_data, wwr, csc, rad_dist = modul_analisisfix.proses_data_oae(path_lengkap, log_callback=self.signals.log_signal.emit)
            self.signals.analysis_finished.emit(fig, status, snr_data, wwr, csc, rad_dist)
        except Exception as e:
            self.signals.log_signal.emit(f"<span style='color:#ff1744;'>CRASH: {str(e)}</span>")
            self.signals.analysis_finished.emit(None, "ERROR", [], 0.0, 0.0, 0.0)

    def _on_analysis_done(self, fig, status, snr_data, wwr, csc, rad_dist):
        self.btn_ana.setEnabled(True)
        if status == "ERROR" or fig is None: return

        res_color = "#00e676" if status == "PASS" else "#ff1744"
        self.lbl_res_title.setStyleSheet(f"font-weight:bold; color: {res_color};")
        self.lbl_res_val.setText(status)
        self.lbl_res_val.setStyleSheet(f"color: {res_color}; font-weight:bold; font-size:12px;")
        self.frame_res.setStyleSheet(f"#Panel {{ border: 1px solid {res_color}; }}")

        rec_status = "VALID" if csc > 60 else "INVALID"
        rec_color = "#00e676" if csc > 60 else "#ff1744"
        self.lbl_rec_val.setText(f"{rec_status} ({csc:.1f}%)")
        self.frame_rec.setStyleSheet(f"#Panel {{ border: 1px solid {rec_color}; }}")

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
                    
        self.canvas_main = FigureCanvas(fig); self.lay_plot_kiri.addWidget(self.canvas_main)
        self._render_snr_bars(snr_data)
        self._render_numerics(snr_data)

    def _update_banner(self, status, desc, color):
        self.lbl_res_val.setText(status); self.lbl_res_val.setStyleSheet(f"color: {color}; font-weight:bold;")
        self.frame_res.setStyleSheet(f"#Panel {{ border: 1px solid {color}; }}")
        self.lbl_rec_val.setText(desc); self.lbl_rec_val.setStyleSheet(f"color: {color}; font-weight:bold;")
        self.frame_rec.setStyleSheet(f"#Panel {{ border: 1px solid {color}; }}")
        self.lbl_footer_status.setText(f"{status} - {desc}"); self.lbl_footer_status.setStyleSheet(f"color:{color};")

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
            w = self.num_grid.itemAt(i).widget()
            if w: w.setParent(None)
        headers = ["FREQ", "SNR", "STATUS"]
        for col, text in enumerate(headers):
            lbl = QLabel(text); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#2a4a6a; font-weight:bold; font-size:11px; border-bottom: 1px solid #1a2b3c; padding-bottom: 3px;")
            self.num_grid.addWidget(lbl, 0, col)
        for row_idx, row_data in enumerate(snr_data, start=1):
            f_lbl = QLabel(f"{row_data[0]} Hz"); f_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            f_lbl.setStyleSheet("color:#4a7a9c; font-size: 11px;")
            v_lbl = QLabel(f"{row_data[1]} dB"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_lbl.setStyleSheet("color:#00e5ff; font-size: 11px; font-weight: bold;")
            s_lbl = QLabel(f"{row_data[2]}"); s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c = "#00e676" if row_data[2]=="PASS" else "#ff9100"
            s_lbl.setStyleSheet(f"color:{c}; font-weight:bold; font-size: 11px;")
            self.num_grid.addWidget(f_lbl, row_idx, 0); self.num_grid.addWidget(v_lbl, row_idx, 1); self.num_grid.addWidget(s_lbl, row_idx, 2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

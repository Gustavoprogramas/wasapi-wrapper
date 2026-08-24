"""
MicBoost - Otimizador de Latência de Microfone para Windows
Interface gráfica principal com customtkinter.
"""

import customtkinter as ctk
import threading
import time
import sys
import os
from typing import Optional

from audio_engine import AudioEngine, AudioDeviceInfo
from system_optimizer import SystemOptimizer


# ─── Tema e Cores ─────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_dark": "#0d1117",
    "bg_card": "#161b22",
    "bg_card_hover": "#1c2333",
    "accent": "#58a6ff",
    "accent_hover": "#79c0ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "text": "#e6edf3",
    "text_dim": "#8b949e",
    "border": "#30363d",
    "slider_track": "#21262d",
}


class MicBoostApp(ctk.CTk):
    """Aplicativo principal MicBoost."""

    APP_TITLE = "🎤 MicBoost — Otimizador de Latência"
    APP_SIZE = "520x780"

    def __init__(self):
        super().__init__()

        # ─── Configuração da janela ──────────────
        self.title(self.APP_TITLE)
        self.geometry(self.APP_SIZE)
        self.minsize(480, 700)
        self.configure(fg_color=COLORS["bg_dark"])

        # Tentar definir ícone
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # ─── Inicialização dos motores ──────────
        self.audio = AudioEngine()
        self.audio.set_status_callback(self._on_audio_status)
        self.optimizer = SystemOptimizer()

        # ─── Variáveis ─────────────────────────
        self.input_devices: list[AudioDeviceInfo] = []
        self.output_devices: list[AudioDeviceInfo] = []
        self._latency_update_running = False
        self._status_text = "Parado"
        self._status_color = COLORS["text_dim"]

        # ─── Construir interface ─────────────────
        self._build_ui()
        self._refresh_devices()

        # ─── Fechar corretamente ─────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════════════
    # ██  UI BUILDER
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        """Constrói toda a interface gráfica."""

        # Container principal com scroll
        self.main_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
        )
        self.main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Header ───────────────────────────────
        self._build_header()

        # ── Dispositivos ──────────────────────────
        self._build_devices_section()

        # ── Configurações de Buffer ──────────────
        self._build_buffer_section()

        # ── Monitor de Latência ──────────────────
        self._build_monitor_section()

        # ── Otimizações do Sistema ───────────────
        self._build_optimizations_section()

        # ── Botões de Controle ───────────────────
        self._build_controls_section()

    def _create_card(self, parent, title: str = "") -> ctk.CTkFrame:
        """Cria um card estilizado."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.pack(fill="x", pady=(0, 10))

        if title:
            label = ctk.CTkLabel(
                card, text=title,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLORS["accent"],
                anchor="w",
            )
            label.pack(fill="x", padx=16, pady=(12, 4))

            separator = ctk.CTkFrame(card, height=1, fg_color=COLORS["border"])
            separator.pack(fill="x", padx=16, pady=(4, 8))

        return card

    def _build_header(self):
        """Constrói o header do app."""
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        title = ctk.CTkLabel(
            header,
            text="🎤 MicBoost",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=COLORS["text"],
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Otimizador de Latência de Microfone",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"],
        )
        subtitle.pack(anchor="w")

    def _build_devices_section(self):
        """Seção de seleção de dispositivos."""
        card = self._create_card(self.main_frame, "📟  Dispositivos de Áudio")

        # Input
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=16, pady=(4, 4))

        ctk.CTkLabel(
            input_frame, text="Entrada (Microfone):",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        self.input_combo = ctk.CTkComboBox(
            input_frame,
            values=["Carregando..."],
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=11),
            fg_color=COLORS["slider_track"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            state="readonly",
            width=400,
        )
        self.input_combo.pack(fill="x", pady=(4, 8))

        # Output
        output_frame = ctk.CTkFrame(card, fg_color="transparent")
        output_frame.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(
            output_frame, text="Saída (Monitoramento):",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        self.output_combo = ctk.CTkComboBox(
            output_frame,
            values=["Carregando..."],
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=11),
            fg_color=COLORS["slider_track"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            state="readonly",
            width=400,
        )
        self.output_combo.pack(fill="x", pady=(4, 4))

        # Refresh button
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Atualizar Dispositivos",
            command=self._refresh_devices,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            hover_color=COLORS["bg_card_hover"],
            height=30,
            width=180,
        )
        self.refresh_btn.pack(anchor="w")

    def _build_buffer_section(self):
        """Seção de configurações de buffer."""
        card = self._create_card(self.main_frame, "⚡  Configurações de Buffer")

        # Buffer size slider
        buf_frame = ctk.CTkFrame(card, fg_color="transparent")
        buf_frame.pack(fill="x", padx=16, pady=(4, 4))

        buf_label_frame = ctk.CTkFrame(buf_frame, fg_color="transparent")
        buf_label_frame.pack(fill="x")

        ctk.CTkLabel(
            buf_label_frame, text="Tamanho do Buffer:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.buffer_value_label = ctk.CTkLabel(
            buf_label_frame, text="128 samples",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.buffer_value_label.pack(side="right")

        self.buffer_slider = ctk.CTkSlider(
            buf_frame,
            from_=0, to=5,
            number_of_steps=5,
            command=self._on_buffer_change,
            fg_color=COLORS["slider_track"],
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.buffer_slider.set(2)  # 128 (index 2)
        self.buffer_slider.pack(fill="x", pady=(4, 2))

        # Buffer labels
        buf_labels = ctk.CTkFrame(buf_frame, fg_color="transparent")
        buf_labels.pack(fill="x")
        for i, size in enumerate(AudioEngine.BUFFER_SIZES):
            lbl = ctk.CTkLabel(
                buf_labels, text=str(size),
                font=ctk.CTkFont(size=9),
                text_color=COLORS["text_dim"],
            )
            lbl.place(relx=i / 5, anchor="n")

        # Latência teórica
        self.theoretical_label = ctk.CTkLabel(
            buf_frame,
            text="Latência teórica: ~5.33 ms",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self.theoretical_label.pack(anchor="w", pady=(12, 4))

        # Sample Rate
        sr_frame = ctk.CTkFrame(card, fg_color="transparent")
        sr_frame.pack(fill="x", padx=16, pady=(8, 4))

        ctk.CTkLabel(
            sr_frame, text="Sample Rate:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.samplerate_combo = ctk.CTkComboBox(
            sr_frame,
            values=["44100 Hz", "48000 Hz", "96000 Hz", "192000 Hz"],
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["slider_track"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            state="readonly",
            width=140,
            command=self._on_samplerate_change,
        )
        self.samplerate_combo.set("48000 Hz")
        self.samplerate_combo.pack(side="right")

        # Checkboxes
        checks_frame = ctk.CTkFrame(card, fg_color="transparent")
        checks_frame.pack(fill="x", padx=16, pady=(8, 12))

        self.exclusive_var = ctk.BooleanVar(value=True)
        self.exclusive_check = ctk.CTkCheckBox(
            checks_frame,
            text="Modo Exclusivo WASAPI (menor latência)",
            variable=self.exclusive_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"],
        )
        self.exclusive_check.pack(anchor="w", pady=(0, 4))

        self.monitoring_var = ctk.BooleanVar(value=True)
        self.monitoring_check = ctk.CTkCheckBox(
            checks_frame,
            text="Monitoramento (ouvir mic no fone)",
            variable=self.monitoring_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"],
        )
        self.monitoring_check.pack(anchor="w")

    def _build_monitor_section(self):
        """Seção de monitoramento de latência."""
        card = self._create_card(self.main_frame, "📊  Monitor de Latência")

        monitor_frame = ctk.CTkFrame(card, fg_color="transparent")
        monitor_frame.pack(fill="x", padx=16, pady=(4, 12))

        # Latência atual
        lat_frame = ctk.CTkFrame(monitor_frame, fg_color="transparent")
        lat_frame.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            lat_frame, text="Latência Atual:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.latency_label = ctk.CTkLabel(
            lat_frame, text="— ms",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["success"],
        )
        self.latency_label.pack(side="right")

        # Barra de latência
        self.latency_bar = ctk.CTkProgressBar(
            monitor_frame,
            fg_color=COLORS["slider_track"],
            progress_color=COLORS["success"],
            height=8,
            corner_radius=4,
        )
        self.latency_bar.set(0)
        self.latency_bar.pack(fill="x", pady=(0, 8))

        # Stats grid
        stats_grid = ctk.CTkFrame(monitor_frame, fg_color="transparent")
        stats_grid.pack(fill="x")

        # Status
        status_row = ctk.CTkFrame(stats_grid, fg_color="transparent")
        status_row.pack(fill="x", pady=1)
        ctk.CTkLabel(status_row, text="Status:", font=ctk.CTkFont(size=11),
                      text_color=COLORS["text_dim"]).pack(side="left")
        self.status_label = ctk.CTkLabel(
            status_row, text="⏸ Parado",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"],
        )
        self.status_label.pack(side="right")

        # Underruns
        underrun_row = ctk.CTkFrame(stats_grid, fg_color="transparent")
        underrun_row.pack(fill="x", pady=1)
        ctk.CTkLabel(underrun_row, text="Buffer Underruns:", font=ctk.CTkFont(size=11),
                      text_color=COLORS["text_dim"]).pack(side="left")
        self.underrun_label = ctk.CTkLabel(
            underrun_row, text="0",
            font=ctk.CTkFont(size=11), text_color=COLORS["text"],
        )
        self.underrun_label.pack(side="right")

        # CPU Load
        cpu_row = ctk.CTkFrame(stats_grid, fg_color="transparent")
        cpu_row.pack(fill="x", pady=1)
        ctk.CTkLabel(cpu_row, text="Uso de CPU (áudio):", font=ctk.CTkFont(size=11),
                      text_color=COLORS["text_dim"]).pack(side="left")
        self.cpu_label = ctk.CTkLabel(
            cpu_row, text="—",
            font=ctk.CTkFont(size=11), text_color=COLORS["text"],
        )
        self.cpu_label.pack(side="right")

        # Modo
        mode_row = ctk.CTkFrame(stats_grid, fg_color="transparent")
        mode_row.pack(fill="x", pady=1)
        ctk.CTkLabel(mode_row, text="Modo:", font=ctk.CTkFont(size=11),
                      text_color=COLORS["text_dim"]).pack(side="left")
        self.mode_label = ctk.CTkLabel(
            mode_row, text="—",
            font=ctk.CTkFont(size=11), text_color=COLORS["text"],
        )
        self.mode_label.pack(side="right")

    def _build_optimizations_section(self):
        """Seção de otimizações do sistema."""
        card = self._create_card(self.main_frame, "🔧  Otimizações do Sistema")

        opt_frame = ctk.CTkFrame(card, fg_color="transparent")
        opt_frame.pack(fill="x", padx=16, pady=(4, 12))

        self.opt_priority_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opt_frame,
            text="Prioridade Real-Time do processo",
            variable=self.opt_priority_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"],
        ).pack(anchor="w", pady=(0, 4))

        self.opt_cpu_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_frame,
            text="Fixar em um core de CPU",
            variable=self.opt_cpu_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"],
        ).pack(anchor="w", pady=(0, 4))

        self.opt_power_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_frame,
            text="Ativar plano Alto Desempenho",
            variable=self.opt_power_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"],
        ).pack(anchor="w", pady=(0, 4))

        # Log de otimizações
        self.opt_log = ctk.CTkTextbox(
            opt_frame,
            height=150,
            font=ctk.CTkFont(size=10, family="Consolas"),
            fg_color=COLORS["slider_track"],
            text_color=COLORS["text_dim"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
        )
        self.opt_log.pack(fill="x", pady=(8, 0))
        self.opt_log.insert("end", "Aguardando início...\n")
        self.opt_log.configure(state="disabled")

    def _build_controls_section(self):
        """Seção de botões de controle."""
        controls = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        controls.pack(fill="x", pady=(4, 0))

        btn_frame = ctk.CTkFrame(controls, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶  INICIAR",
            command=self._start_audio,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["success"],
            hover_color="#2ea043",
            height=44,
            corner_radius=10,
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹  PARAR",
            command=self._stop_audio,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["error"],
            hover_color="#da3633",
            height=44,
            corner_radius=10,
            state="disabled",
        )
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # Volume
        vol_frame = ctk.CTkFrame(controls, fg_color="transparent")
        vol_frame.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(
            vol_frame, text="🔊 Volume:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left")

        self.volume_label = ctk.CTkLabel(
            vol_frame, text="100%",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self.volume_label.pack(side="right")

        self.volume_slider = ctk.CTkSlider(
            vol_frame,
            from_=0, to=200,
            command=self._on_volume_change,
            fg_color=COLORS["slider_track"],
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            width=200,
        )
        self.volume_slider.set(100)
        self.volume_slider.pack(side="right", padx=(8, 8))

    # ═══════════════════════════════════════════════════
    # ██  CALLBACKS E LÓGICA
    # ═══════════════════════════════════════════════════

    def _refresh_devices(self):
        """Atualiza a lista de dispositivos de áudio."""
        try:
            # Primeiro tenta apenas WASAPI
            self.input_devices = self.audio.get_input_devices()
            self.output_devices = self.audio.get_output_devices()

            # Se não encontrar WASAPI, pega todos
            if not self.input_devices:
                self.input_devices = self.audio.get_all_input_devices()
            if not self.output_devices:
                self.output_devices = self.audio.get_all_output_devices()

            input_names = [f"{d.name}" for d in self.input_devices]
            output_names = [f"{d.name}" for d in self.output_devices]

            if input_names:
                self.input_combo.configure(values=input_names)
                self.input_combo.set(input_names[0])
            else:
                self.input_combo.configure(values=["Nenhum dispositivo encontrado"])
                self.input_combo.set("Nenhum dispositivo encontrado")

            if output_names:
                self.output_combo.configure(values=output_names)
                self.output_combo.set(output_names[0])
            else:
                self.output_combo.configure(values=["Nenhum dispositivo encontrado"])
                self.output_combo.set("Nenhum dispositivo encontrado")

        except Exception as e:
            self._log_optimization(f"Erro ao listar dispositivos: {e}")

    def _on_buffer_change(self, value):
        """Callback quando o slider de buffer muda."""
        index = int(round(value))
        buffer_size = AudioEngine.BUFFER_SIZES[index]
        self.buffer_value_label.configure(text=f"{buffer_size} samples")
        self._update_theoretical_latency(buffer_size)

    def _on_samplerate_change(self, value):
        """Callback quando o sample rate muda."""
        buffer_index = int(round(self.buffer_slider.get()))
        buffer_size = AudioEngine.BUFFER_SIZES[buffer_index]
        self._update_theoretical_latency(buffer_size)

    def _on_volume_change(self, value):
        """Callback quando o volume muda."""
        volume = int(value)
        self.volume_label.configure(text=f"{volume}%")
        self.audio.set_volume(volume / 100.0)

    def _update_theoretical_latency(self, buffer_size: int):
        """Atualiza a latência teórica exibida."""
        sr_text = self.samplerate_combo.get()
        sample_rate = int(sr_text.replace(" Hz", ""))
        latency_ms = (buffer_size / sample_rate) * 1000 * 2
        self.theoretical_label.configure(
            text=f"Latência teórica: ~{latency_ms:.2f} ms"
        )

    def _get_selected_input_device(self) -> Optional[int]:
        """Retorna o índice do dispositivo de entrada selecionado."""
        selected = self.input_combo.get()
        for dev in self.input_devices:
            if dev.name == selected:
                return dev.index
        return None

    def _get_selected_output_device(self) -> Optional[int]:
        """Retorna o índice do dispositivo de saída selecionado."""
        selected = self.output_combo.get()
        for dev in self.output_devices:
            if dev.name == selected:
                return dev.index
        return None

    def _start_audio(self):
        """Inicia o stream de áudio."""
        input_dev = self._get_selected_input_device()
        output_dev = self._get_selected_output_device()

        if input_dev is None:
            self._log_optimization("❌ Selecione um dispositivo de entrada!")
            return
        if output_dev is None:
            self._log_optimization("❌ Selecione um dispositivo de saída!")
            return

        # Pega configurações
        buffer_index = int(round(self.buffer_slider.get()))
        buffer_size = AudioEngine.BUFFER_SIZES[buffer_index]
        sr_text = self.samplerate_combo.get()
        sample_rate = int(sr_text.replace(" Hz", ""))
        exclusive = self.exclusive_var.get()
        monitoring = self.monitoring_var.get()

        # Aplica otimizações do sistema
        self._apply_optimizations()

        # Inicia em thread separada para não travar a GUI
        def _start():
            try:
                self.audio.start(
                    input_device=input_dev,
                    output_device=output_dev,
                    buffer_size=buffer_size,
                    sample_rate=sample_rate,
                    exclusive=exclusive,
                    monitoring=monitoring,
                )
                # Atualiza UI na thread principal
                self.after(0, self._on_stream_started)
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._on_stream_error(msg))

        threading.Thread(target=_start, daemon=True).start()

    def _stop_audio(self):
        """Para o stream de áudio."""
        self.audio.stop()
        self._latency_update_running = False
        self.optimizer.restore_all()

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="⏸ Parado", text_color=COLORS["text_dim"])
        self.latency_label.configure(text="— ms", text_color=COLORS["text_dim"])
        self.latency_bar.set(0)
        self.mode_label.configure(text="—")
        self.cpu_label.configure(text="—")
        self._log_optimization("⏹ Stream parado")

    def _on_stream_started(self):
        """Callback quando o stream inicia com sucesso."""
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="🟢 Rodando", text_color=COLORS["success"])
        
        mode = "Exclusivo WASAPI" if self.audio.exclusive_mode else "Compartilhado"
        self.mode_label.configure(text=mode)

        self._log_optimization(f"✅ Stream iniciado — Modo: {mode}")

        # Inicia atualização de latência
        self._latency_update_running = True
        self._update_latency_display()

    def _on_stream_error(self, error: str):
        """Callback quando o stream falha."""
        self.status_label.configure(text="❌ Erro", text_color=COLORS["error"])
        self._log_optimization(f"❌ Erro: {error}")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _on_audio_status(self, status: str, message: str):
        """Callback de status do motor de áudio."""
        msg_copy = f"[{status}] {message}"
        self.after(0, lambda m=msg_copy: self._log_optimization(m))

    def _update_latency_display(self):
        """Atualiza o display de latência periodicamente."""
        if not self._latency_update_running or not self.audio.is_running:
            return

        stats = self.audio.get_latency_stats()
        stream_info = self.audio.get_stream_info()

        # Latência total (usa a do stream se disponível, senão teórica)
        if stream_info and 'latency' in stream_info:
            total_lat = stream_info['latency']['input'] + stream_info['latency']['output']
        elif stats.total_latency_ms > 0:
            total_lat = stats.total_latency_ms
        else:
            total_lat = stats.theoretical_latency_ms

        # Atualiza label de latência
        self.latency_label.configure(text=f"{total_lat:.2f} ms")

        # Cor baseada na latência
        if total_lat < 5:
            color = COLORS["success"]
        elif total_lat < 15:
            color = COLORS["warning"]
        else:
            color = COLORS["error"]
        self.latency_label.configure(text_color=color)
        self.latency_bar.configure(progress_color=color)

        # Barra de progresso (normalizada: 0ms=0, 50ms=1)
        bar_value = min(1.0, total_lat / 50.0)
        self.latency_bar.set(bar_value)

        # Underruns
        self.underrun_label.configure(text=str(stats.underruns))
        if stats.underruns > 0:
            self.underrun_label.configure(text_color=COLORS["warning"])

        # CPU load
        if stream_info and 'cpu_load' in stream_info:
            self.cpu_label.configure(text=f"{stream_info['cpu_load']:.1f}%")

        # Reagenda
        self.after(200, self._update_latency_display)

    def _apply_optimizations(self):
        """Aplica as otimizações selecionadas."""
        self._clear_opt_log()

        results = self.optimizer.apply_all_optimizations(
            realtime_priority=self.opt_priority_var.get(),
            fix_cpu_core=self.opt_cpu_var.get(),
        )

        if self.opt_power_var.get():
            results.append(self.optimizer.set_high_performance_power_plan())

        for r in results:
            icon = "✅" if r.success else "⚠️"
            self._log_optimization(f"{icon} {r.name}: {r.message}")

    def _log_optimization(self, text: str):
        """Adiciona texto ao log de otimizações."""
        self.opt_log.configure(state="normal")
        self.opt_log.insert("end", text + "\n")
        self.opt_log.see("end")
        self.opt_log.configure(state="disabled")

    def _clear_opt_log(self):
        """Limpa o log de otimizações."""
        self.opt_log.configure(state="normal")
        self.opt_log.delete("1.0", "end")
        self.opt_log.configure(state="disabled")

    def _on_close(self):
        """Handler de fechamento do app."""
        self._latency_update_running = False
        self.audio.stop()
        self.optimizer.restore_all()
        self.destroy()


# ─── Entry Point ──────────────────────────────────────────

def main():
    """Ponto de entrada principal."""
    app = MicBoostApp()
    app.mainloop()


if __name__ == "__main__":
    main()

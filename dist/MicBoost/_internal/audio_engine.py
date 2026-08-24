"""
MicBoost - Audio Engine
Motor de áudio WASAPI com latência mínima para Windows.
Gerencia streams de áudio em modo exclusivo com buffers otimizados.
"""

import sounddevice as sd
import numpy as np
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class AudioDeviceInfo:
    """Informações de um dispositivo de áudio."""
    index: int
    name: str
    host_api: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_wasapi: bool


@dataclass
class LatencyStats:
    """Estatísticas de latência em tempo real."""
    input_latency_ms: float = 0.0
    output_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    buffer_size: int = 0
    sample_rate: float = 0.0
    theoretical_latency_ms: float = 0.0
    underruns: int = 0


class AudioEngine:
    """
    Motor de áudio de baixa latência usando WASAPI Exclusive Mode.
    
    Funcionalidades:
    - Enumeração de dispositivos WASAPI
    - Passthrough de áudio em tempo real (mic → output)
    - Modo exclusivo para latência mínima
    - Monitoramento de latência em tempo real
    """

    # Tamanhos de buffer suportados (em samples)
    BUFFER_SIZES = [32, 64, 128, 256, 512, 1024]
    
    # Sample rates comuns
    SAMPLE_RATES = [44100, 48000, 96000, 192000]

    def __init__(self):
        self.stream: Optional[sd.Stream] = None
        self.is_running: bool = False
        self.exclusive_mode: bool = True
        self.buffer_size: int = 128
        self.sample_rate: float = 48000
        self.input_device: Optional[int] = None
        self.output_device: Optional[int] = None
        self.latency_stats = LatencyStats()
        self._underrun_count: int = 0
        self._lock = threading.Lock()
        self._on_status_callback: Optional[Callable] = None
        self._on_latency_callback: Optional[Callable] = None
        self._volume: float = 1.0
        self._muted: bool = False
        self._monitoring: bool = True  # Passthrough ativado por padrão

    def set_status_callback(self, callback: Callable):
        """Define callback para atualizações de status."""
        self._on_status_callback = callback

    def set_latency_callback(self, callback: Callable):
        """Define callback para atualizações de latência."""
        self._on_latency_callback = callback

    def get_host_apis(self) -> list:
        """Retorna lista de host APIs disponíveis."""
        return list(sd.query_hostapis())

    def get_wasapi_host_api_index(self) -> Optional[int]:
        """Encontra o índice da host API WASAPI."""
        for i, api in enumerate(sd.query_hostapis()):
            if 'wasapi' in api['name'].lower():
                return i
        return None

    def get_devices(self, input_only: bool = False, output_only: bool = False,
                    wasapi_only: bool = True) -> list[AudioDeviceInfo]:
        """
        Lista dispositivos de áudio disponíveis.
        
        Args:
            input_only: Retorna apenas dispositivos de entrada
            output_only: Retorna apenas dispositivos de saída
            wasapi_only: Filtra apenas dispositivos WASAPI
        """
        devices = []
        all_devices = sd.query_devices()
        host_apis = sd.query_hostapis()
        wasapi_index = self.get_wasapi_host_api_index()

        for i, dev in enumerate(all_devices):
            host_api = host_apis[dev['hostapi']]
            is_wasapi = (dev['hostapi'] == wasapi_index) if wasapi_index is not None else False

            if wasapi_only and not is_wasapi:
                continue
            if input_only and dev['max_input_channels'] == 0:
                continue
            if output_only and dev['max_output_channels'] == 0:
                continue

            devices.append(AudioDeviceInfo(
                index=i,
                name=dev['name'],
                host_api=host_api['name'],
                max_input_channels=dev['max_input_channels'],
                max_output_channels=dev['max_output_channels'],
                default_samplerate=dev['default_samplerate'],
                is_wasapi=is_wasapi,
            ))

        return devices

    def get_input_devices(self) -> list[AudioDeviceInfo]:
        """Lista dispositivos de entrada WASAPI."""
        return self.get_devices(input_only=True)

    def get_output_devices(self) -> list[AudioDeviceInfo]:
        """Lista dispositivos de saída WASAPI."""
        return self.get_devices(output_only=True)

    def get_all_input_devices(self) -> list[AudioDeviceInfo]:
        """Lista TODOS os dispositivos de entrada (todas as APIs)."""
        return self.get_devices(input_only=True, wasapi_only=False)

    def get_all_output_devices(self) -> list[AudioDeviceInfo]:
        """Lista TODOS os dispositivos de saída (todas as APIs)."""
        return self.get_devices(output_only=True, wasapi_only=False)

    def _audio_callback(self, indata: np.ndarray, outdata: np.ndarray,
                         frames: int, time_info, status):
        """
        Callback de áudio chamado pelo PortAudio.
        Faz passthrough direto do input para output com latência mínima.
        """
        if status:
            if status.input_underflow or status.output_underflow:
                self._underrun_count += 1

        if self._monitoring and not self._muted:
            outdata[:] = indata * self._volume
        else:
            outdata[:] = 0

        # Atualiza estatísticas de latência
        if time_info:
            try:
                input_lat = time_info.input_buffer_adc_time
                output_lat = time_info.output_buffer_dac_time
                current_time = time_info.current_time
                
                self.latency_stats.input_latency_ms = max(0, (current_time - input_lat) * 1000) if input_lat > 0 else 0
                self.latency_stats.output_latency_ms = max(0, (output_lat - current_time) * 1000) if output_lat > 0 else 0
                self.latency_stats.total_latency_ms = self.latency_stats.input_latency_ms + self.latency_stats.output_latency_ms
            except Exception:
                pass

        self.latency_stats.underruns = self._underrun_count

    def _get_wasapi_settings(self):
        """Cria configurações WASAPI para modo exclusivo."""
        if self.exclusive_mode:
            try:
                return sd.WasapiSettings(exclusive=True)
            except Exception:
                return None
        return None

    def calculate_theoretical_latency(self) -> float:
        """Calcula a latência teórica baseada no buffer e sample rate."""
        if self.sample_rate > 0:
            return (self.buffer_size / self.sample_rate) * 1000 * 2  # input + output
        return 0.0

    def start(self, input_device: int, output_device: int,
              buffer_size: int = 128, sample_rate: float = 48000,
              exclusive: bool = True, monitoring: bool = True):
        """
        Inicia o stream de áudio com latência otimizada.
        
        Args:
            input_device: Índice do dispositivo de entrada
            output_device: Índice do dispositivo de saída
            buffer_size: Tamanho do buffer em samples
            sample_rate: Taxa de amostragem em Hz
            exclusive: Usar WASAPI Exclusive Mode
            monitoring: Ativar passthrough (mic → output)
        """
        with self._lock:
            if self.is_running:
                self.stop()

            self.input_device = input_device
            self.output_device = output_device
            self.buffer_size = buffer_size
            self.sample_rate = sample_rate
            self.exclusive_mode = exclusive
            self._monitoring = monitoring
            self._underrun_count = 0

            # Calcula latência teórica
            self.latency_stats.buffer_size = buffer_size
            self.latency_stats.sample_rate = sample_rate
            self.latency_stats.theoretical_latency_ms = self.calculate_theoretical_latency()
            self.latency_stats.underruns = 0

            try:
                # Configurações WASAPI
                wasapi_settings = self._get_wasapi_settings()
                extra_input = wasapi_settings
                extra_output = wasapi_settings

                self.stream = sd.Stream(
                    device=(input_device, output_device),
                    samplerate=sample_rate,
                    blocksize=buffer_size,
                    dtype='float32',
                    channels=1,
                    latency='low',
                    callback=self._audio_callback,
                    extra_settings=(extra_input, extra_output),
                )
                self.stream.start()
                self.is_running = True

                if self._on_status_callback:
                    self._on_status_callback("running", "Stream iniciado com sucesso")

            except sd.PortAudioError as e:
                error_msg = str(e)
                # Se falhar com modo exclusivo, tenta modo compartilhado
                if self.exclusive_mode:
                    try:
                        self.stream = sd.Stream(
                            device=(input_device, output_device),
                            samplerate=sample_rate,
                            blocksize=buffer_size,
                            dtype='float32',
                            channels=1,
                            latency='low',
                            callback=self._audio_callback,
                        )
                        self.stream.start()
                        self.is_running = True
                        self.exclusive_mode = False

                        if self._on_status_callback:
                            self._on_status_callback("warning",
                                f"Modo exclusivo falhou, usando modo compartilhado.\n"
                                f"Erro original: {error_msg}")
                    except sd.PortAudioError as e2:
                        if self._on_status_callback:
                            self._on_status_callback("error", f"Erro ao iniciar stream: {e2}")
                        raise
                else:
                    if self._on_status_callback:
                        self._on_status_callback("error", f"Erro ao iniciar stream: {e}")
                    raise

    def stop(self):
        """Para o stream de áudio."""
        with self._lock:
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self.is_running = False

            if self._on_status_callback:
                self._on_status_callback("stopped", "Stream parado")

    def restart(self):
        """Reinicia o stream com as configurações atuais."""
        if self.input_device is not None and self.output_device is not None:
            self.start(
                self.input_device, self.output_device,
                self.buffer_size, self.sample_rate,
                self.exclusive_mode, self._monitoring
            )

    def set_volume(self, volume: float):
        """Define o volume do passthrough (0.0 a 2.0)."""
        self._volume = max(0.0, min(2.0, volume))

    def set_muted(self, muted: bool):
        """Muta/desmuta o passthrough."""
        self._muted = muted

    def set_monitoring(self, enabled: bool):
        """Ativa/desativa o passthrough de monitoramento."""
        self._monitoring = enabled

    def get_latency_stats(self) -> LatencyStats:
        """Retorna estatísticas de latência atuais."""
        return self.latency_stats

    def get_stream_info(self) -> dict:
        """Retorna informações sobre o stream ativo."""
        if self.stream and self.is_running:
            return {
                'active': self.stream.active,
                'samplerate': self.stream.samplerate,
                'blocksize': self.stream.blocksize,
                'latency': {
                    'input': self.stream.latency[0] * 1000 if self.stream.latency else 0,
                    'output': self.stream.latency[1] * 1000 if self.stream.latency else 0,
                },
                'exclusive': self.exclusive_mode,
                'cpu_load': self.stream.cpu_load * 100 if hasattr(self.stream, 'cpu_load') else 0,
            }
        return {}

    def __del__(self):
        """Garante que o stream é fechado ao destruir o objeto."""
        self.stop()

"""
MicBoost - Audio Engine
Native C++ wrapper for low-latency audio processing via WASAPI.
"""

import ctypes
import os
import json
from dataclasses import dataclass
from typing import Optional, Callable

@dataclass
class AudioDeviceInfo:
    """Audio device information."""
    index: int
    name: str
    host_api: str = "WASAPI"
    max_input_channels: int = 2
    max_output_channels: int = 2
    default_samplerate: float = 48000.0
    is_wasapi: bool = True

@dataclass
class LatencyStats:
    """Real-time latency statistics."""
    input_latency_ms: float = 0.0
    output_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    buffer_size: int = 0
    sample_rate: float = 0.0
    theoretical_latency_ms: float = 0.0
    underruns: int = 0

class AudioEngine:
    """Audio engine implementation using native backend."""

    BUFFER_SIZES = [32, 64, 128, 256, 512, 1024]
    SAMPLE_RATES = [44100, 48000, 96000, 192000]

    def __init__(self):
        self._on_status_callback: Optional[Callable] = None
        self.is_running = False
        self.exclusive_mode = False
        self.buffer_size = 128
        self.sample_rate = 48000
        self.latency_stats = LatencyStats()
        self._monitoring = True
        self._volume = 1.0
        
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine", "build", "Release", "audio_engine.dll")
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"Native audio engine library not found at: {dll_path}")
            
        self.dll = ctypes.CDLL(dll_path)
        
        self.dll.InitEngine.restype = ctypes.c_bool
        self.dll.GetDeviceListJson.restype = ctypes.c_char_p
        self.dll.StartStream.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.dll.StartStream.restype = ctypes.c_bool
        self.dll.StopStream.restype = None
        self.dll.IsStreamRunning.restype = ctypes.c_bool
        self.dll.GetStats.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_int)]
        self.dll.GetStats.restype = None
        self.dll.SetVolume.argtypes = [ctypes.c_float]
        self.dll.SetVolume.restype = None

        self.dll.InitEngine()

    def set_status_callback(self, callback: Callable):
        self._on_status_callback = callback

    def _notify(self, status: str, message: str):
        if self._on_status_callback:
            self._on_status_callback(status, message)

    def _get_devices_json(self) -> dict:
        json_str = self.dll.GetDeviceListJson().decode('utf-8')
        try:
            return json.loads(json_str)
        except Exception:
            return {"inputs": [], "outputs": []}

    def get_input_devices(self) -> list[AudioDeviceInfo]:
        devs = self._get_devices_json()
        return [AudioDeviceInfo(index=d['id'], name=d['name']) for d in devs.get('inputs', [])]

    def get_output_devices(self) -> list[AudioDeviceInfo]:
        devs = self._get_devices_json()
        return [AudioDeviceInfo(index=d['id'], name=d['name']) for d in devs.get('outputs', [])]

    def get_all_input_devices(self) -> list[AudioDeviceInfo]:
        return self.get_input_devices()

    def get_all_output_devices(self) -> list[AudioDeviceInfo]:
        return self.get_output_devices()

    def start(self, input_device: int, output_device: int,
              buffer_size: int = 128, sample_rate: float = 48000,
              exclusive: bool = True, monitoring: bool = True):
              
        if self.is_running:
            self.stop()
            
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self._monitoring = monitoring
        
        self.latency_stats.buffer_size = buffer_size
        self.latency_stats.sample_rate = sample_rate
        self.latency_stats.theoretical_latency_ms = (buffer_size / sample_rate) * 1000 * 2
        
        self._notify("info", f"Starting engine | IN: {input_device}, OUT: {output_device}")
        
        success = self.dll.StartStream(
            int(input_device), 
            int(output_device), 
            int(sample_rate), 
            int(buffer_size), 
            exclusive
        )
        
        if not success:
            if exclusive:
                self._notify("info", "Exclusive mode failed. Falling back to shared mode.")
                success = self.dll.StartStream(
                    int(input_device), 
                    int(output_device), 
                    int(sample_rate), 
                    int(buffer_size), 
                    False
                )
                self.exclusive_mode = False
            
            if not success:
                self._notify("error", "Failed to start audio stream. Device may be in use.")
                raise RuntimeError("Failed to start audio stream.")
        else:
            self.exclusive_mode = exclusive

        self.is_running = True
        self.set_volume(self._volume if self._monitoring else 0.0)
        
        mode_str = "Exclusive" if self.exclusive_mode else "Shared"
        self._notify("running", f"Stream started [{mode_str}]")

    def stop(self):
        if self.is_running:
            self.dll.StopStream()
            self.is_running = False
            self._notify("stopped", "Stream stopped.")

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(2.0, volume))
        if self._monitoring:
            self.dll.SetVolume(ctypes.c_float(self._volume))

    def set_monitoring(self, enabled: bool):
        self._monitoring = enabled
        self.dll.SetVolume(ctypes.c_float(self._volume if enabled else 0.0))

    def get_latency_stats(self) -> LatencyStats:
        if self.is_running:
            lat = ctypes.c_float(0.0)
            underruns = ctypes.c_int(0)
            self.dll.GetStats(ctypes.byref(lat), ctypes.byref(underruns))
            
            self.latency_stats.total_latency_ms = lat.value
            self.latency_stats.input_latency_ms = lat.value / 2.0
            self.latency_stats.output_latency_ms = lat.value / 2.0
            self.latency_stats.underruns = underruns.value
            
        return self.latency_stats

    def get_stream_info(self) -> dict:
        if not self.is_running:
            return {}
            
        lat = ctypes.c_float(0.0)
        underruns = ctypes.c_int(0)
        self.dll.GetStats(ctypes.byref(lat), ctypes.byref(underruns))
        
        return {
            'active': True,
            'samplerate': self.sample_rate,
            'blocksize': self.buffer_size,
            'latency': {
                'input': lat.value / 2.0,
                'output': lat.value / 2.0,
            },
            'exclusive': self.exclusive_mode,
            'cpu_load': 0.1,
        }

    def __del__(self):
        self.stop()

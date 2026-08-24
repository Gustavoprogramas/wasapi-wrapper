#include "miniaudio.h"
#include <windows.h>
#include <string>
#include <vector>
#include <sstream>
#include <atomic>
#include <iomanip>
#include <iostream>

// We pack everything into a single state struct instead of polluting the global namespace.
struct MicBoostState {
    ma_context ctx;
    ma_device wasapi_dev;
    bool backend_ready = false;
    std::atomic<bool> active_session{false};
    std::string cached_json_topology;
    std::atomic<float> master_gain{1.0f};
    std::atomic<int> drop_count{0};
    
    std::vector<ma_device_info> inputs_cache;
    std::vector<ma_device_info> outputs_cache;
};

static MicBoostState mb_state;

// Pushes a debug string to the Windows debugger (sysinternals DebugView)
void log_debug(const char* msg) {
    OutputDebugStringA((std::string("[MicBoost Core] ") + msg + "\n").c_str());
}

void audio_routing_callback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount)
{
    // A null input or output means the driver starved us or dropped a packet.
    if (!pInput || !pOutput) {
        mb_state.drop_count++;
        return;
    }
    
    float* dest = (float*)pOutput;
    const float* src = (const float*)pInput;
    
    int out_ch = pDevice->playback.channels;
    int in_ch = pDevice->capture.channels;
    float current_gain = mb_state.master_gain.load(std::memory_order_relaxed);

    // Hard panning mono to stereo for monitoring
    for (ma_uint32 i = 0; i < frameCount; ++i) {
        float raw_sample = src[i * in_ch] * current_gain;
        for (int c = 0; c < out_ch; ++c) {
            dest[i * out_ch + c] = raw_sample;
        }
    }
}

// A quick-and-dirty JSON string escape so we don't need a massive library like nlohmann just for device enumeration.
std::string sanitize_for_json(const std::string& raw) {
    std::ostringstream oss;
    for (char c : raw) {
        if (c == '"' || c == '\\' || (c >= '\x00' && c <= '\x1f')) {
            oss << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)c;
        } else {
            oss << c;
        }
    }
    return oss.str();
}

extern "C" {

    __declspec(dllexport) bool MB_InitializeAudioBackend() {
        if (mb_state.backend_ready) return true;
        
        log_debug("Spinning up WASAPI backend...");
        
        ma_context_config cfg = ma_context_config_init();
        ma_backend only_wasapi[] = { ma_backend_wasapi };
        
        if (ma_context_init(only_wasapi, 1, &cfg, &mb_state.ctx) != MA_SUCCESS) {
            log_debug("FATAL: Could not bind to WASAPI.");
            return false;
        }
        
        mb_state.backend_ready = true;
        return true;
    }

    __declspec(dllexport) const char* MB_EnumerateDevicesAsJson() {
        if (!mb_state.backend_ready) MB_InitializeAudioBackend();

        ma_device_info* playbacks;
        ma_uint32 playback_qty;
        ma_device_info* captures;
        ma_uint32 capture_qty;

        if (ma_context_get_devices(&mb_state.ctx, &playbacks, &playback_qty, &captures, &capture_qty) != MA_SUCCESS) {
            log_debug("WARN: Failed to enumerate topologies.");
            return "{\"inputs\":[],\"outputs\":[]}";
        }

        mb_state.inputs_cache.assign(captures, captures + capture_qty);
        mb_state.outputs_cache.assign(playbacks, playbacks + playback_qty);

        // Stitching JSON manually. 
        std::ostringstream json;
        json << "{\"inputs\":[";
        for (ma_uint32 i = 0; i < capture_qty; ++i) {
            json << "{\"id\":" << i << ",\"name\":\"" << sanitize_for_json(captures[i].name) << "\"}";
            if (i < capture_qty - 1) json << ",";
        }
        json << "],\"outputs\":[";
        for (ma_uint32 i = 0; i < playback_qty; ++i) {
            json << "{\"id\":" << i << ",\"name\":\"" << sanitize_for_json(playbacks[i].name) << "\"}";
            if (i < playback_qty - 1) json << ",";
        }
        json << "]}";

        mb_state.cached_json_topology = json.str();
        return mb_state.cached_json_topology.c_str();
    }

    __declspec(dllexport) bool MB_LaunchWasapiStream(int in_id, int out_id, int hz, int buf_size, bool req_exclusive) {
        if (mb_state.active_session) return false;
        if (!mb_state.backend_ready) MB_InitializeAudioBackend();

        if (in_id < 0 || in_id >= mb_state.inputs_cache.size() || out_id < 0 || out_id >= mb_state.outputs_cache.size()) {
            log_debug("ERROR: Invalid device IDs provided.");
            return false;
        }

        ma_device_config dev_cfg = ma_device_config_init(ma_device_type_duplex);
        
        // --- Capture specific hacks ---
        dev_cfg.capture.pDeviceID = &mb_state.inputs_cache[in_id].id;
        dev_cfg.capture.format    = ma_format_f32;
        // We specifically pin the capture to 1 channel (mono). Cheap USB podcast mics (like the Fifine series)
        // often crash or reject the format if we try to pull stereo in exclusive mode.
        dev_cfg.capture.channels  = 1; 
        dev_cfg.capture.shareMode = req_exclusive ? ma_share_mode_exclusive : ma_share_mode_shared;

        // --- Playback config ---
        dev_cfg.playback.pDeviceID = &mb_state.outputs_cache[out_id].id;
        dev_cfg.playback.format    = ma_format_f32;
        dev_cfg.playback.channels  = 2; // Always push stereo down the wire for the monitoring mix
        dev_cfg.playback.shareMode = req_exclusive ? ma_share_mode_exclusive : ma_share_mode_shared;

        dev_cfg.sampleRate = hz;
        dev_cfg.dataCallback = audio_routing_callback;
        
        // Squeeze the buffer to hit our latency targets. Double buffering is usually safest against jitter.
        dev_cfg.periodSizeInFrames = buf_size > 0 ? buf_size : 128;
        dev_cfg.periods = 2; 

        if (ma_device_init(&mb_state.ctx, &dev_cfg, &mb_state.wasapi_dev) != MA_SUCCESS) {
            log_debug("WARN: Exclusive mode likely rejected by driver. Falling back to shared WASAPI ring buffer...");
            if (req_exclusive) {
                dev_cfg.capture.shareMode = ma_share_mode_shared;
                dev_cfg.playback.shareMode = ma_share_mode_shared;
                if (ma_device_init(&mb_state.ctx, &dev_cfg, &mb_state.wasapi_dev) != MA_SUCCESS) {
                    log_debug("FATAL: Shared mode fallback failed too. Giving up.");
                    return false;
                }
            } else {
                return false;
            }
        }

        mb_state.drop_count = 0;
        
        if (ma_device_start(&mb_state.wasapi_dev) != MA_SUCCESS) {
            log_debug("FATAL: Driver accepted config but refused to start stream.");
            ma_device_uninit(&mb_state.wasapi_dev);
            return false;
        }

        mb_state.active_session = true;
        log_debug("SUCCESS: Stream is live.");
        return true;
    }

    __declspec(dllexport) void MB_HaltStream() {
        if (!mb_state.active_session) return;
        ma_device_stop(&mb_state.wasapi_dev);
        ma_device_uninit(&mb_state.wasapi_dev);
        mb_state.active_session = false;
        log_debug("Stream halted.");
    }

    __declspec(dllexport) bool MB_IsStreamActive() {
        return mb_state.active_session.load(std::memory_order_relaxed);
    }

    __declspec(dllexport) void MB_FetchLatencyMetrics(float* out_latency_ms, int* out_drops) {
        if (!mb_state.active_session) {
            if (out_latency_ms) *out_latency_ms = 0.0f;
            if (out_drops) *out_drops = 0;
            return;
        }

        if (out_latency_ms) {
            // Rough latency heuristic based on WASAPI internals + buffer sizing
            float cap_ms = (float)mb_state.wasapi_dev.capture.internalPeriodSizeInFrames / mb_state.wasapi_dev.sampleRate * 1000.0f;
            float play_ms = (float)mb_state.wasapi_dev.playback.internalPeriodSizeInFrames / mb_state.wasapi_dev.sampleRate * 1000.0f;
            
            // Shared mode usually eats an extra ~10ms in the OS mixer engine
            float os_tax = (mb_state.wasapi_dev.capture.shareMode == ma_share_mode_shared) ? 10.0f : 2.0f;
            *out_latency_ms = cap_ms + play_ms + os_tax;
        }
        
        if (out_drops) {
            *out_drops = mb_state.drop_count.load(std::memory_order_relaxed);
        }
    }

    __declspec(dllexport) void MB_AdjustGain(float vol) {
        mb_state.master_gain.store(vol, std::memory_order_relaxed);
    }
}

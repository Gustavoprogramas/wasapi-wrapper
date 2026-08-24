#include "miniaudio.h"
#include <string>
#include <vector>
#include <sstream>
#include <atomic>
#include <iomanip>

ma_context g_context;
ma_device g_device;
bool g_isContextInitialized = false;
std::atomic<bool> g_isStreamRunning{false};
std::string g_deviceJsonCache;
std::atomic<float> g_volume{1.0f};
std::atomic<int> g_underruns{0};

// Temporary buffers for device enumeration
std::vector<ma_device_info> g_captureDevices;
std::vector<ma_device_info> g_playbackDevices;

void data_callback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount)
{
    // If underflow/overflow occurs, we might not get input/output
    if (pInput == NULL || pOutput == NULL) {
        g_underruns++;
        return;
    }
    
    float* fOut = (float*)pOutput;
    const float* fIn = (const float*)pInput;
    int channelsOut = pDevice->playback.channels;
    int channelsIn = pDevice->capture.channels;
    float vol = g_volume.load();

    for (ma_uint32 i = 0; i < frameCount; ++i) {
        // Just take the first channel of input (mono downmix)
        float sample = fIn[i * channelsIn] * vol;
        
        // Output to all channels
        for (int c = 0; c < channelsOut; ++c) {
            fOut[i * channelsOut + c] = sample;
        }
    }
}

// Escape string for JSON
std::string escape_json(const std::string& s) {
    std::ostringstream o;
    for (auto c = s.cbegin(); c != s.cend(); c++) {
        if (*c == '"' || *c == '\\' || ('\x00' <= *c && *c <= '\x1f')) {
            o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)*c;
        } else {
            o << *c;
        }
    }
    return o.str();
}

extern "C" {

    __declspec(dllexport) bool InitEngine() {
        if (g_isContextInitialized) return true;
        
        ma_context_config ctxConfig = ma_context_config_init();
        ma_backend backends[] = { ma_backend_wasapi };
        
        if (ma_context_init(backends, 1, &ctxConfig, &g_context) != MA_SUCCESS) {
            return false;
        }
        g_isContextInitialized = true;
        return true;
    }

    __declspec(dllexport) const char* GetDeviceListJson() {
        if (!g_isContextInitialized) InitEngine();

        ma_device_info* pPlaybackInfos;
        ma_uint32 playbackCount;
        ma_device_info* pCaptureInfos;
        ma_uint32 captureCount;

        if (ma_context_get_devices(&g_context, &pPlaybackInfos, &playbackCount, &pCaptureInfos, &captureCount) != MA_SUCCESS) {
            return "{\"inputs\":[],\"outputs\":[]}";
        }

        g_captureDevices.assign(pCaptureInfos, pCaptureInfos + captureCount);
        g_playbackDevices.assign(pPlaybackInfos, pPlaybackInfos + playbackCount);

        std::ostringstream json;
        json << "{\"inputs\":[";
        for (ma_uint32 i = 0; i < captureCount; ++i) {
            json << "{\"id\":" << i << ",\"name\":\"" << escape_json(pCaptureInfos[i].name) << "\"}";
            if (i < captureCount - 1) json << ",";
        }
        json << "],\"outputs\":[";
        for (ma_uint32 i = 0; i < playbackCount; ++i) {
            json << "{\"id\":" << i << ",\"name\":\"" << escape_json(pPlaybackInfos[i].name) << "\"}";
            if (i < playbackCount - 1) json << ",";
        }
        json << "]}";

        g_deviceJsonCache = json.str();
        return g_deviceJsonCache.c_str();
    }

    __declspec(dllexport) bool StartStream(int inputId, int outputId, int sampleRate, int bufferSize, bool exclusive) {
        if (g_isStreamRunning) return false;
        if (!g_isContextInitialized) InitEngine();

        if (inputId < 0 || inputId >= g_captureDevices.size() || 
            outputId < 0 || outputId >= g_playbackDevices.size()) {
            return false; // Invalid IDs
        }

        ma_device_config deviceConfig = ma_device_config_init(ma_device_type_duplex);
        deviceConfig.capture.pDeviceID = &g_captureDevices[inputId].id;
        deviceConfig.capture.format    = ma_format_f32;
        deviceConfig.capture.channels  = 1; // Force mono input
        deviceConfig.capture.shareMode = exclusive ? ma_share_mode_exclusive : ma_share_mode_shared;

        deviceConfig.playback.pDeviceID = &g_playbackDevices[outputId].id;
        deviceConfig.playback.format    = ma_format_f32;
        deviceConfig.playback.channels  = 2; // Force stereo output
        deviceConfig.playback.shareMode = exclusive ? ma_share_mode_exclusive : ma_share_mode_shared;

        deviceConfig.sampleRate = sampleRate;
        deviceConfig.dataCallback = data_callback;
        
        // Configure buffer size for low latency
        deviceConfig.periodSizeInFrames = bufferSize > 0 ? bufferSize : 128;
        // The periods setting controls the number of chunks. For lowest latency, we want small number of periods.
        deviceConfig.periods = 2; // Double buffering

        if (ma_device_init(&g_context, &deviceConfig, &g_device) != MA_SUCCESS) {
            // Try fallback to shared mode if exclusive failed
            if (exclusive) {
                deviceConfig.capture.shareMode = ma_share_mode_shared;
                deviceConfig.playback.shareMode = ma_share_mode_shared;
                if (ma_device_init(&g_context, &deviceConfig, &g_device) != MA_SUCCESS) {
                    return false;
                }
            } else {
                return false;
            }
        }

        g_underruns = 0;
        
        if (ma_device_start(&g_device) != MA_SUCCESS) {
            ma_device_uninit(&g_device);
            return false;
        }

        g_isStreamRunning = true;
        return true;
    }

    __declspec(dllexport) void StopStream() {
        if (!g_isStreamRunning) return;
        ma_device_stop(&g_device);
        ma_device_uninit(&g_device);
        g_isStreamRunning = false;
    }

    __declspec(dllexport) bool IsStreamRunning() {
        return g_isStreamRunning.load();
    }

    __declspec(dllexport) void GetStats(float* latencyMs, int* underruns) {
        if (!g_isStreamRunning) {
            if (latencyMs) *latencyMs = 0.0f;
            if (underruns) *underruns = 0;
            return;
        }

        if (latencyMs) {
            // Miniaudio provides latency estimation
            float latCapture = (float)g_device.capture.internalPeriodSizeInFrames / g_device.sampleRate * 1000.0f;
            float latPlayback = (float)g_device.playback.internalPeriodSizeInFrames / g_device.sampleRate * 1000.0f;
            
            // Add WASAPI overhead estimate
            *latencyMs = latCapture + latPlayback + (g_device.capture.shareMode == ma_share_mode_shared ? 10.0f : 2.0f);
        }
        
        if (underruns) {
            *underruns = g_underruns.load();
        }
    }

    __declspec(dllexport) void SetVolume(float volume) {
        g_volume = volume;
    }
}

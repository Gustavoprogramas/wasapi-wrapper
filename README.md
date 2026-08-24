# MicBoost

MicBoost is a low-latency audio processing engine designed to bypass standard Windows audio overhead. It routes audio directly from a microphone input to a playback device using an optimized C++ WASAPI wrapper, offering near-zero latency.

This is especially useful for routing your microphone through a virtual audio cable into applications like Discord or OBS without the typical delay introduced by standard software routing.

## Features

- **Ultra-Low Latency:** Written in C++ using `miniaudio`, interfacing directly with the Windows WASAPI backend in duplex mode.
- **Python GUI:** A clean and modern interface built with `customtkinter` to manage the audio stream without dealing with command-line tools.
- **Zero Python GIL Overhead:** Audio processing runs completely in a native C++ background thread.
- **Hardware Agnostic:** Automatically handles mono-to-stereo upmixing and format conversions seamlessly.
- **System Optimizer:** Elevates process priority and configures Windows power plans for uninterrupted real-time audio processing.

## Prerequisites

- Windows 10/11
- Python 3.9+
- CMake (for building the native engine)
- Visual Studio / MSVC Compiler (for building the native engine)

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/micboost.git
   cd micboost
   ```

2. **Build the Native Engine:**
   ```bash
   cd engine
   cmake -B build -S .
   cmake --build build --config Release
   ```
   *This compiles the `audio_engine.dll` required for the application to function.*

3. **Set up the Python Environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

1. **Virtual Audio Cable (Optional but Recommended):**
   To route the processed audio into other applications (like Discord), you need a virtual audio driver such as [VB-Cable](https://vb-audio.com/Cable/). Install it before running MicBoost.

2. **Run the Application:**
   ```bash
   python main.py
   ```

3. **Configuration:**
   - Select your physical microphone (e.g., Fifine AM8) as the **Input**.
   - Select the Virtual Cable (e.g., `CABLE Input`) as the **Output**.
   - Set the **Buffer Size** to the lowest stable value (typically 64 or 128 samples).
   - Click **Start**.

4. **In your target application (e.g., Discord):**
   - Select `CABLE Output` as your microphone.

## License

This project is open-source and available under the MIT License.

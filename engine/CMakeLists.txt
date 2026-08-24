cmake_minimum_required(VERSION 3.15)
project(MicBoostEngine)

set(CMAKE_CXX_STANDARD 14)

# Create a shared library (DLL)
add_library(audio_engine SHARED audio_engine.cpp)

# Miniaudio doesn't need to be linked against anything on Windows usually, 
# but WASAPI might require Ole32, etc. CMake handles standard Windows libraries.
target_compile_definitions(audio_engine PRIVATE MINIAUDIO_IMPLEMENTATION)

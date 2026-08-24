"""Diagnostico completo de audio - testa todas as APIs e formatos."""
import sounddevice as sd
import sys

print("=" * 60)
print("  DIAGNOSTICO DE AUDIO - MicBoost")
print("=" * 60)

# Lista TODAS as APIs
print("\n--- Host APIs disponiveis ---")
for i, api in enumerate(sd.query_hostapis()):
    print(f"  [{i}] {api['name']} (devices: {api['devices']})")

# Lista TODOS os dispositivos com 'fifine' ou 'Microphone'
print("\n--- Todos os dispositivos de entrada ---")
all_devs = sd.query_devices()
input_devs = []
for i, dev in enumerate(all_devs):
    if dev['max_input_channels'] > 0:
        api = sd.query_hostapis(dev['hostapi'])
        print(f"  [{i}] {dev['name']} | API: {api['name']} | "
              f"ch={dev['max_input_channels']} sr={dev['default_samplerate']}")
        input_devs.append(i)

print("\n--- Todos os dispositivos de saida ---")
for i, dev in enumerate(all_devs):
    if dev['max_output_channels'] > 0:
        api = sd.query_hostapis(dev['hostapi'])
        print(f"  [{i}] {dev['name']} | API: {api['name']} | "
              f"ch={dev['max_output_channels']} sr={dev['default_samplerate']}")

# Tenta abrir cada dispositivo de entrada
print("\n--- Testando abertura de cada dispositivo de entrada ---")
for dev_idx in input_devs:
    dev = all_devs[dev_idx]
    api = sd.query_hostapis(dev['hostapi'])
    ch = dev['max_input_channels']
    sr = dev['default_samplerate']
    
    for bs in [0, 256, 512]:
        for lat in ['low', 'high']:
            for dtype in ['float32', 'int16']:
                try:
                    stream = sd.InputStream(
                        device=dev_idx,
                        channels=ch,
                        samplerate=sr,
                        blocksize=bs,
                        dtype=dtype,
                        latency=lat,
                    )
                    stream.start()
                    import time
                    time.sleep(0.2)
                    actual_lat = stream.latency * 1000
                    stream.stop()
                    stream.close()
                    print(f"  OK [{dev_idx}] {dev['name']} | {api['name']} | "
                          f"{dtype} bs={bs} lat={lat} -> {actual_lat:.1f}ms")
                    # Found one that works, skip remaining combos for this device
                    break
                except Exception as e:
                    err = str(e)
                    if 'UNSUPPORTED' in err:
                        reason = "UNSUPPORTED_FORMAT"
                    elif 'Invalid' in err:
                        reason = "Invalid param"
                    elif 'IN_USE' in err:
                        reason = "IN_USE"
                    else:
                        reason = err[:60]
                    # Only print first failure per combo
                    continue
            else:
                continue
            break
        else:
            continue
        break
    else:
        print(f"  FAIL [{dev_idx}] {dev['name']} | {api['name']} | Nenhum formato funcionou")

print("\nDiagnostico concluido!")

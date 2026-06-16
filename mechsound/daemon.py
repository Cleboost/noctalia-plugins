#!/usr/bin/env python3
"""
mechsound daemon — mixer logiciel multi-sons, zéro latence, zéro backlog.

- Callback sounddevice : mixe tous les sons actifs en temps réel.
- Chaque touche ajoute un son à la liste active (overlap naturel).
- Si trop de sons en retard (>MAX_ACTIVE), on drop les plus vieux.
- Pipeline : evtest | python3 daemon.py <sound_dir> <volume> [play_keyup]
"""

import sys
import os
import wave
import threading
import re
import array

sound_dir  = sys.argv[1] if len(sys.argv) > 1 else "."
volume     = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
play_keyup = sys.argv[3].lower() != "false" if len(sys.argv) > 3 else True

# Indiquer à PipeWire que c'est un son de notification (non ducké par la musique)
import os
os.environ.setdefault("PIPEWIRE_PROPS",
    'media.role=notification media.name=mechsound')

TARGET_RATE = 48000
MAX_ACTIVE  = 6   # sons simultanés max avant de dropper les plus vieux

import numpy as np
import sounddevice as sd

# ── Device PipeWire ───────────────────────────────────────────────────────────
pw_device = None
for i, d in enumerate(sd.query_devices()):
    if d['max_output_channels'] > 0 and 'pipewire' in d['name'].lower():
        pw_device = i
        break

if pw_device is None:
    sys.stderr.write("mechsound: device PipeWire introuvable\n")
    sys.exit(1)

sys.stderr.write(f"mechsound: device PipeWire = {pw_device}\n")

# ── Préchargement WAV → numpy float32 ────────────────────────────────────────
cache: dict = {}

for fn in sorted(os.listdir(sound_dir)):
    if not fn.endswith(".wav"):
        continue
    path = os.path.join(sound_dir, fn)
    try:
        with wave.open(path, "rb") as wf:
            raw      = wf.readframes(wf.getnframes())
            channels = wf.getnchannels()
            # Convertir en float32 mono
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if channels > 1:
                arr = arr.reshape(-1, channels).mean(axis=1)
            arr *= volume
            cache[fn] = arr
    except Exception as e:
        sys.stderr.write(f"warn: {fn}: {e}\n")

sys.stderr.write(f"mechsound: {len(cache)} sons chargés\n")
sys.stderr.flush()

# ── Mixer logiciel ────────────────────────────────────────────────────────────
# active_sounds : liste de [array_float32, position_courante]
active_sounds = []
mix_lock = threading.Lock()

def audio_callback(outdata, frames, time_info, status):
    """Callback temps réel : mixe tous les sons actifs dans outdata."""
    buf = np.zeros(frames, dtype=np.float32)

    with mix_lock:
        done = []
        for i, (data, pos) in enumerate(active_sounds):
            remaining = len(data) - pos
            if remaining <= 0:
                done.append(i)
                continue
            n = min(frames, remaining)
            buf[:n] += data[pos:pos + n]
            active_sounds[i][1] = pos + n

        # Retirer les sons terminés (en ordre inverse pour ne pas décaler les index)
        for i in reversed(done):
            active_sounds.pop(i)

    # Clipping doux pour éviter la saturation quand plusieurs sons se chevauchent
    np.clip(buf, -1.0, 1.0, out=buf)
    outdata[:, 0] = buf

# Ouvrir le stream audio une seule fois
stream = sd.OutputStream(
    samplerate=TARGET_RATE,
    channels=1,
    dtype='float32',
    blocksize=64,           # ~1.3ms par bloc
    latency='low',          # hint PipeWire pour réduire son quantum
    device=pw_device,
    callback=audio_callback,
)
stream.start()
sys.stderr.write("mechsound: stream audio ouvert\n")
sys.stderr.flush()

# ── Lecture d'un son ──────────────────────────────────────────────────────────
def play(fn: str) -> None:
    data = cache.get(fn)
    if data is None:
        return
    with mix_lock:
        if len(active_sounds) >= MAX_ACTIVE:
            # Drop le son le plus avancé (le plus vieux) pour éviter le backlog
            active_sounds.pop(0)
        active_sounds.append([data, 0])

# ── Mapping touche → fichier ──────────────────────────────────────────────────
def get_sound(code: str, is_up: bool) -> str | None:
    suffix = "-up" if is_up else ""
    if code == "KEY_SPACE":
        return f"spacebar{suffix}.wav"
    if code in ("KEY_ENTER", "KEY_KPENTER"):
        return f"enter{suffix}.wav"
    if code == "KEY_BACKSPACE":
        return f"backspace{suffix}.wav"
    if code.startswith("KEY_"):
        return f"fallback{suffix}.wav"
    return None

# ── Lecture stdin (evtest) ────────────────────────────────────────────────────
EV_RE = re.compile(r"\(KEY_([A-Z0-9_]+)\).*value (\d)")

sys.stdout.write("ready\n")
sys.stdout.flush()

# Lecture stdin non-bufférisée via os.read — réagit dès le premier octet disponible.
# "for line in sys.stdin" et readline() bufférisent par blocs côté Python/libc.
import os as _os
_fd  = sys.stdin.fileno()
_buf = b""

try:
    while True:
        try:
            chunk = _os.read(_fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        _buf += chunk
        while b"\n" in _buf:
            idx  = _buf.index(b"\n")
            line = _buf[:idx].decode("utf-8", errors="replace")
            _buf = _buf[idx + 1:]

            if "EV_KEY" not in line:
                continue
            m = EV_RE.search(line)
            if not m:
                continue

            code  = "KEY_" + m.group(1)
            value = m.group(2)

            if value == "1":
                fn = get_sound(code, False)
            elif value == "0" and play_keyup:
                fn = get_sound(code, True)
            else:
                fn = None

            if fn:
                play(fn)
finally:
    stream.stop()
    stream.close()

"""
Genera e salva i 3 scenari UAV in data/scenarios/.

Ogni scenario = drone + foresta (background) + un evento (tank | gunshot | missile_launch).

Uso:
  conda activate audio_env
  python build_scenarios.py
  python build_scenarios.py --duration 20
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from scipy import signal
from scipy.io import wavfile

DATA_DIR = Path(__file__).resolve().parent / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"
SAMPLES = DATA_DIR / "samples"
SR = 22050
DEFAULT_RPM = 6000

DRONE_PATH = SAMPLES / "drone" / "uas_drone_pass_dcpoke.wav"
DURATION_S = 18.0


# ── Mix & preprocess ──────────────────────────────────────────────────────
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)


def _scale_to_rms(x: np.ndarray, target_rms: float) -> np.ndarray:
    r = _rms(x)
    return x if r < 1e-12 else x * (target_rms / r)


def _loop_to_length(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    reps = int(np.ceil(n / len(x)))
    return np.tile(x, reps)[:n]


def load_mono(path: Path, sr: int = SR, duration: float | None = None) -> np.ndarray:
    y, _ = librosa.load(path, sr=sr, duration=duration, mono=True)
    return y


def mix_uav_event(
    event_path: Path,
    drone_path: Path,
    forest_path: Path | None = None,
    duration: float = 18.0,
    *,
    event_snr_db: float = -10.0,
    forest_snr_db: float = -20.0,
    drone_level: float = 1.0,
    event_offset_s: float | None = None,
    loop_event: bool = False,
) -> tuple[np.ndarray, int]:
    n = int(duration * SR)
    drone = _loop_to_length(load_mono(drone_path, SR), n)
    event = load_mono(event_path, SR)
    if loop_event:
        event = _loop_to_length(event, n)
    else:
        event = event.astype(np.float32)

    drone_r = _rms(drone)
    event_tgt = drone_r * (10 ** (event_snr_db / 20.0))
    event_s = _scale_to_rms(event, event_tgt)

    mix = (drone_level * drone).astype(np.float32)
    if loop_event:
        mix = mix + event_s
    else:
        off = int((event_offset_s if event_offset_s is not None else duration * 0.35) * SR)
        end = min(off + len(event_s), n)
        if off < n:
            mix[off:end] += event_s[: end - off]

    if forest_path and forest_path.exists():
        forest = _loop_to_length(load_mono(forest_path, SR), n)
        forest_tgt = drone_r * (10 ** (forest_snr_db / 20.0))
        mix = mix + _scale_to_rms(forest, forest_tgt)

    peak = np.max(np.abs(mix))
    if peak > 0.99:
        mix = mix * (0.95 / peak)
    return mix.astype(np.float32), SR


def cancel_rotor_noise(
    audio: np.ndarray, sr: int, rpm: float = DEFAULT_RPM, n_harmonics: int = 8, Q: float = 30.0,
) -> np.ndarray:
    fundamental = (rpm / 60.0) * 2
    filtered = audio.astype(np.float64).copy()
    for h in range(1, n_harmonics + 1):
        freq = fundamental * h
        if freq >= sr / 2 - 50:
            break
        b, a = signal.iirnotch(w0=freq, Q=Q, fs=sr)
        filtered = signal.filtfilt(b, a, filtered)
    return filtered.astype(np.float32)


def spectral_subtract_drone(
    mixture: np.ndarray, drone_ref: np.ndarray, sr: int, alpha: float = 0.45, floor: float = 0.12,
) -> np.ndarray:
    n_fft = 2048
    hop = n_fft // 4

    def stft_mag(y):
        S = librosa.stft(y, n_fft=n_fft, hop_length=hop)
        return np.abs(S), S

    mag_mix, S_mix = stft_mag(mixture)
    mag_ref, _ = stft_mag(_loop_to_length(drone_ref, len(mixture)))
    mag_clean = np.maximum(mag_mix - alpha * mag_ref, floor * mag_mix)
    S_clean = mag_clean * np.exp(1j * np.angle(S_mix))
    return librosa.istft(S_clean, hop_length=hop, length=len(mixture)).astype(np.float32)


def bandpass_tank(audio: np.ndarray, sr: int, low_hz: float = 70.0, high_hz: float = 1400.0) -> np.ndarray:
    b, a = signal.butter(4, [low_hz / (sr / 2), high_hz / (sr / 2)], btype="band")
    return signal.filtfilt(b, a, audio).astype(np.float32)


def _cancel_wind_noise(audio: np.ndarray, sr: int) -> np.ndarray:
    b, a = signal.butter(4, 200 / (sr / 2), btype="high")
    return signal.filtfilt(b, a, audio)


def preprocess_uav_listen(
    mixture: np.ndarray,
    sr: int,
    drone_ref: np.ndarray | None = None,
    rpm: float = DEFAULT_RPM,
) -> np.ndarray:
    x = cancel_rotor_noise(mixture, sr, rpm=rpm)
    if drone_ref is not None:
        x = spectral_subtract_drone(x, drone_ref, sr)
    x = bandpass_tank(x, sr)
    peak = np.max(np.abs(x))
    if peak > 1e-9:
        x = (x / peak) * 0.9
    return x.astype(np.float32)


def preprocess_for_impulsive(
    mixture: np.ndarray,
    sr: int,
    drone_ref: np.ndarray | None = None,
    rpm: float = DEFAULT_RPM,
) -> np.ndarray:
    x = cancel_rotor_noise(mixture, sr, rpm=rpm)
    if drone_ref is not None:
        x = spectral_subtract_drone(x, drone_ref, sr)
    x = _cancel_wind_noise(x, sr)
    peak = np.max(np.abs(x))
    if peak > 1e-9:
        x = (x / peak) * 0.9
    return x.astype(np.float32)


def find_forest_ambience() -> Path | None:
    forest_dir = SAMPLES / "forest"
    if forest_dir.is_dir():
        files = sorted(
            p for p in forest_dir.iterdir()
            if p.suffix.lower() in (".wav", ".flac", ".mp3", ".ogg")
            and not p.name.startswith("._")
        )
        if files:
            return files[0]

    meta = DATA_DIR / "ESC-50/meta/esc50.csv"
    audio_dir = DATA_DIR / "ESC-50/audio"
    if not meta.exists():
        return None
    for cat in ("chirping_birds", "wind", "crickets"):
        with meta.open(newline="") as f:
            for row in csv.DictReader(f):
                if row["category"] == cat:
                    p = audio_dir / row["filename"]
                    if p.exists():
                        return p
    return None


# ── Scenario build ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ScenarioSpec:
    id: str
    target: str
    event_path: Path
    event_snr_db: float
    loop_event: bool
    mix_wav: str
    pre_wav: str


ALL_SCENARIOS = (
    ScenarioSpec(
        "tank",
        "tank",
        SAMPLES / "tank" / "kakaist-tank-moving-sfx-319878.mp3",
        -12.0,
        True,
        "scenario_tank_mix.wav",
        "scenario_tank_preprocessed.wav",
    ),
    ScenarioSpec(
        "gunshot",
        "gunshot",
        SAMPLES / "gunshot" / "demo_gunshot_128293.wav",
        -2.0,
        False,
        "scenario_gunshot_mix.wav",
        "scenario_gunshot_preprocessed.wav",
    ),
    ScenarioSpec(
        "missile_launch",
        "missile_launch",
        SAMPLES / "missile_launch" / "ucas_launch_x47b_qubodup.flac",
        4.0,
        False,
        "scenario_missile_mix.wav",
        "scenario_missile_preprocessed.wav",
    ),
)


def build_scenario(spec: ScenarioSpec, forest: Path | None, duration: float) -> tuple[Path, Path]:
    if not spec.event_path.exists():
        raise FileNotFoundError(f"Evento mancante: {spec.event_path}")
    if not DRONE_PATH.exists():
        raise FileNotFoundError(f"Drone mancante: {DRONE_PATH}")

    mix, sr = mix_uav_event(
        spec.event_path,
        DRONE_PATH,
        forest,
        duration=duration,
        event_snr_db=spec.event_snr_db,
        forest_snr_db=-20.0,
        loop_event=spec.loop_event,
    )
    drone_ref = load_mono(DRONE_PATH, sr, duration=duration)
    if spec.target == "tank":
        pre = preprocess_uav_listen(mix, sr, drone_ref)
    else:
        pre = preprocess_for_impulsive(mix, sr, drone_ref)

    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    mix_p = SCENARIO_DIR / spec.mix_wav
    pre_p = SCENARIO_DIR / spec.pre_wav
    wavfile.write(str(mix_p), sr, mix)
    wavfile.write(str(pre_p), sr, pre)
    return mix_p, pre_p


def build_all(duration: float = DURATION_S) -> list[Path]:
    forest = find_forest_ambience()
    print("=== Build scenari → data/scenarios/ ===")
    print(f"  drone:      {DRONE_PATH.name}")
    print(f"  background: {forest.name if forest else '(nessuno)'}\n")

    written = []
    for spec in ALL_SCENARIOS:
        mix_p, pre_p = build_scenario(spec, forest, duration)
        written.extend([mix_p, pre_p])
        print(f"  [{spec.id}] {spec.event_path.name} (SNR {spec.event_snr_db:+.0f} dB)")
        print(f"    {mix_p.name}")
        print(f"    {pre_p.name}")
    print(f"\n  Salvati {len(written)} file in {SCENARIO_DIR}/")
    return written


def main():
    p = argparse.ArgumentParser(description="Genera 3 scenari UAV (drone + foresta + evento)")
    p.add_argument("--duration", type=float, default=DURATION_S, help="durata mix in secondi")
    args = p.parse_args()
    build_all(args.duration)


if __name__ == "__main__":
    main()

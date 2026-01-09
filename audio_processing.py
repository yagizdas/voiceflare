"""
Audio processing utilities for Discord voice bot.
Handles audio buffering, resampling, format conversion, and WAV file operations.
"""

import os
import time
import wave
import threading
import numpy as np
from scipy.signal import resample_poly
from typing import Optional, Tuple
from collections import deque


def write_wav(path: str, pcm_s16le: bytes, sample_rate: int, channels: int) -> None:
    """
    Write PCM audio data to a WAV file.
    
    Args:
        path: Output file path
        pcm_s16le: Raw PCM data (signed 16-bit little-endian)
        sample_rate: Sample rate in Hz
        channels: Number of audio channels (1=mono, 2=stereo)
    """
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_s16le)


def wait_for_file_ready(path: str, timeout_s: float = 5.0, min_bytes: int = 800) -> None:
    """
    Wait until a file exists, has minimum size, and can be opened for reading.
    Useful for TTS engines that may return before the OS flushes the file.
    
    Args:
        path: File path to wait for
        timeout_s: Maximum time to wait in seconds
        min_bytes: Minimum file size in bytes
        
    Raises:
        RuntimeError: If file is not ready within timeout
    """
    t0 = time.time()
    last_size = -1
    stable_count = 0

    while time.time() - t0 < timeout_s:
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                if size >= min_bytes:
                    # Check that size is stable (file writing done)
                    if size == last_size:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_size = size

                    # Try opening (ensures not locked)
                    with open(path, "rb") as f:
                        f.read(16)

                    if stable_count >= 2:
                        return
            except OSError:
                pass
        time.sleep(0.05)

    raise RuntimeError(f"WAV file not ready within timeout: {path}")


def guess_channels_from_pcm_len(pcm: bytes) -> int:
    """
    Heuristic to guess number of audio channels from PCM data length.
    Discord typically provides stereo (2 channel) PCM.
    
    Args:
        pcm: Raw PCM data
        
    Returns:
        Estimated number of channels (1 or 2)
        
    Note:
        This is imperfect. Prefer real metadata when available.
    """
    # Stereo chunks are typically divisible by 4 (2 channels × 2 bytes/sample)
    return 2 if (len(pcm) % 4 == 0) else 1


def to_mono_i16(pcm_s16le: bytes, channels: int) -> np.ndarray:
    """
    Convert PCM audio to mono int16 numpy array.
    
    Args:
        pcm_s16le: Raw PCM data (signed 16-bit little-endian, interleaved if stereo)
        channels: Number of channels in the input
        
    Returns:
        Mono audio as int16 numpy array
    """
    x = np.frombuffer(pcm_s16le, dtype=np.int16)
    
    if channels <= 1:
        return x
    
    # Interleaved stereo: [L0, R0, L1, R1, ...]
    try:
        x = x.reshape(-1, channels)
    except ValueError:
        # Handle odd chunk boundaries by truncating
        usable = (x.size // channels) * channels
        x = x[:usable].reshape(-1, channels)
    
    # Average channels to create mono
    mono = x.mean(axis=1)
    return mono.astype(np.int16)


def resample_48k_to_16k_mono_f32(pcm_48k_s16le: bytes, channels: int) -> np.ndarray:
    """
    Resample 48kHz PCM to 16kHz mono float32 (for Whisper STT).
    
    Args:
        pcm_48k_s16le: Input PCM at 48kHz (signed 16-bit little-endian)
        channels: Number of channels in input (1 or 2)
        
    Returns:
        Resampled audio at 16kHz as float32 numpy array in range [-1, 1]
    """
    # Convert to mono int16
    audio_i16_mono = to_mono_i16(pcm_48k_s16le, channels=channels)
    
    # Resample 48kHz → 16kHz (ratio = 1:3)
    audio_16k_i16 = resample_poly(audio_i16_mono, up=1, down=3).astype(np.int16)
    
    # Convert to float32 normalized to [-1, 1]
    audio_f32 = audio_16k_i16.astype(np.float32) / 32768.0
    
    return audio_f32


class UserBuffer:
    """
    Thread-safe audio buffer for a single user.
    Manages audio chunking, preroll, and utterance detection.
    """
    
    def __init__(self, preroll_max_chunks: int = 25):
        """
        Initialize user audio buffer.
        
        Args:
            preroll_max_chunks: Maximum number of chunks to keep in preroll buffer
        """
        self.lock = threading.Lock()
        
        # Main audio buffer
        self.chunks: list[bytes] = []
        
        # Preroll buffer (circular buffer of recent audio before speaking starts)
        self.preroll: deque[bytes] = deque(maxlen=preroll_max_chunks)
        
        # Speaking state
        self.speaking = False
        self.stop_ts: Optional[float] = None
        self.last_audio_ts = 0.0
        
        # Remember latest observed channel count
        self.last_channels: int = 1
        
        # Prevent repeated preroll prepends
        self._prepended_preroll_for_current_utterance = False
    
    def add_pcm(self, pcm: bytes, channels: int) -> None:
        """
        Add PCM audio chunk to buffer.
        
        Args:
            pcm: Raw PCM audio data
            channels: Number of audio channels
        """
        with self.lock:
            self.last_audio_ts = time.time()
            self.last_channels = channels
            
            # Always update preroll buffer
            self.preroll.append(pcm)
            
            # Only accumulate main chunks while speaking
            if self.speaking:
                self.chunks.append(pcm)
    
    def start_speaking(self) -> None:
        """Mark the start of a speaking utterance."""
        with self.lock:
            self.speaking = True
            self.stop_ts = None
            
            # Prepend preroll once at start of utterance
            if not self._prepended_preroll_for_current_utterance and len(self.preroll) > 0:
                self.chunks = list(self.preroll) + self.chunks
                self._prepended_preroll_for_current_utterance = True
    
    def stop_speaking(self) -> None:
        """Mark the end of a speaking utterance."""
        with self.lock:
            self.speaking = False
            self.stop_ts = time.time()
    
    def duration_seconds(self, sample_rate: int = 48000) -> float:
        """
        Calculate total duration of buffered audio.
        
        Args:
            sample_rate: Audio sample rate in Hz
            
        Returns:
            Duration in seconds
        """
        with self.lock:
            total_bytes = sum(len(c) for c in self.chunks)
        
        # int16 = 2 bytes per sample
        samples = total_bytes / 2
        return float(samples) / float(sample_rate)
    
    def finalize(self) -> Tuple[bytes, int]:
        """
        Finalize and extract buffered audio data.
        
        Returns:
            Tuple of (concatenated PCM bytes, channel count)
        """
        with self.lock:
            pcm = b"".join(self.chunks)
            channels = self.last_channels
            self.chunks.clear()
            self.stop_ts = None
            self._prepended_preroll_for_current_utterance = False
            return pcm, channels
    
    def clear(self) -> None:
        """Clear the buffer without finalizing."""
        with self.lock:
            self.chunks.clear()
            self.stop_ts = None
            self._prepended_preroll_for_current_utterance = False

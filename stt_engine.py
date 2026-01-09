"""
Speech-to-Text engine wrapper using Faster Whisper.
Handles audio transcription with configurable parameters.
"""

from faster_whisper import WhisperModel
import numpy as np
from typing import Optional
from config_loader import STTConfig


class SpeechToTextEngine:
    """Wrapper for Faster Whisper speech-to-text model."""
    
    def __init__(self, config: STTConfig):
        """
        Initialize STT engine with configuration.
        
        Args:
            config: STT configuration object
        """
        self.config = config
        self.model = WhisperModel(
            config.model_size,
            device=config.device,
            compute_type=config.compute_type
        )
        print(f"[STT] Loaded Whisper model: {config.model_size} on {config.device}")
    
    def transcribe(self, audio_f32_16k: np.ndarray) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio_f32_16k: Audio data as float32 numpy array at 16kHz, mono, range [-1, 1]
            
        Returns:
            Transcribed text
        """
        config = self.config
        
        segments, _info = self.model.transcribe(
            audio_f32_16k,
            language=config.language,
            vad_filter=config.vad_filter,
            vad_parameters=dict(min_silence_duration_ms=config.vad_min_silence_duration_ms),
            beam_size=config.beam_size,
            temperature=0.0,
            without_timestamps=False,
            condition_on_previous_text=False,
            repetition_penalty=config.repetition_penalty,
            initial_prompt=config.initial_prompt,
            word_timestamps=False
        )
        
        # Concatenate all segments
        text = " ".join(seg.text for seg in segments).strip()
        return text

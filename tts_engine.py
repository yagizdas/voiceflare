"""
Text-to-Speech engine wrappers.
Supports multiple TTS backends: Piper TTS and Windows SAPI.
"""

import subprocess
from abc import ABC, abstractmethod
from typing import Optional
from config_loader import TTSConfig


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""
    
    @abstractmethod
    def synth_to_wav(self, text: str, out_path: str) -> None:
        """
        Synthesize text to a WAV file.
        
        Args:
            text: Text to synthesize
            out_path: Output WAV file path
        """
        pass


class PiperTTS(TTSEngine):
    """Piper TTS engine implementation (high-quality neural TTS)."""
    
    def __init__(self, executable_path: str, model_path: str):
        """
        Initialize Piper TTS.
        
        Args:
            executable_path: Path to piper executable
            model_path: Path to Piper ONNX model file
        """
        self.piper = executable_path
        self.model = model_path
        print(f"[TTS] Initialized Piper TTS with model: {model_path}")
    
    def synth_to_wav(self, text: str, out_path: str) -> None:
        """Synthesize text using Piper TTS."""
        subprocess.run(
            [self.piper, "--model", self.model, "--output_file", out_path],
            input=text,
            text=True,
            check=True,
            capture_output=True,
        )


class WindowsSAPITTS(TTSEngine):
    """Windows built-in SAPI TTS engine (no extra dependencies)."""
    
    def __init__(self):
        """Initialize Windows SAPI TTS."""
        print("[TTS] Initialized Windows SAPI TTS")
    
    def synth_to_wav(self, text: str, out_path: str) -> None:
        """Synthesize text using Windows SAPI."""
        # Escape quotes in text for PowerShell
        escaped_text = text.replace('"', '`"')
        
        ps_script = f"""
Add-Type -AssemblyName System.Speech;
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;
$speak.SetOutputToWaveFile("{out_path}");
$speak.Speak("{escaped_text}");
$speak.Dispose();
"""
        
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            check=True,
            capture_output=True,
            text=True,
        )


def create_tts_engine(config: TTSConfig) -> TTSEngine:
    """
    Factory function to create appropriate TTS engine based on configuration.
    
    Args:
        config: TTS configuration
        
    Returns:
        Initialized TTS engine instance
        
    Raises:
        ValueError: If engine type is unsupported or configuration is invalid
    """
    if config.engine == "piper":
        if config.piper is None:
            raise ValueError("Piper TTS selected but piper configuration is missing")
        return PiperTTS(
            executable_path=config.piper.executable_path,
            model_path=config.piper.model_path
        )
    elif config.engine == "windows_sapi":
        return WindowsSAPITTS()
    else:
        raise ValueError(f"Unsupported TTS engine: {config.engine}")

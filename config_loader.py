"""
Configuration loader module for Discord bot.
Handles loading and validating configuration from YAML files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class DiscordConfig:
    token: str
    command_prefix: str


@dataclass
class XAIConfig:
    api_key: str
    model: str
    timeout: int
    temperature: float
    max_tokens: int


@dataclass
class PromptConfig:
    system: str
    user_template: str


@dataclass
class PromptsConfig:
    primary: PromptConfig
    alternative: PromptConfig
    alternative_probability: int


@dataclass
class UserConfig:
    name: str
    target_name: str
    friendly_fire_group: Optional[str] = None


@dataclass
class STTConfig:
    model_size: str
    device: str
    compute_type: str
    language: str
    beam_size: int
    vad_filter: bool
    vad_min_silence_duration_ms: int
    repetition_penalty: float
    initial_prompt: str


@dataclass
class PiperTTSConfig:
    executable_path: str
    model_path: str


@dataclass
class TTSConfig:
    engine: str
    piper: Optional[PiperTTSConfig] = None


@dataclass
class AudioConfig:
    min_clip_seconds: float
    silence_finalize_ms: int
    preroll_max_chunks: int
    sample_rate: int
    target_sample_rate: int


@dataclass
class FFmpegConfig:
    path: str


@dataclass
class AudioFilesConfig:
    startup: str
    shutdown: str


@dataclass
class DebugConfig:
    dump_wav_files: bool
    dump_directory: str
    log_level: str


@dataclass
class ConnectionConfig:
    max_restart_attempts: int
    restart_cooldown_seconds: int


class Config:
    """Main configuration class containing all bot settings."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to the configuration YAML file
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please copy config.example.yaml to config.yaml and fill in your values."
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
        
        # Load Discord config
        self.discord = DiscordConfig(
            token=self._get_env_or_config(raw_config['discord']['token'], 'DISCORD_TOKEN'),
            command_prefix=raw_config['discord']['command_prefix']
        )
        
        # Load XAI config
        xai = raw_config['xai']
        self.xai = XAIConfig(
            api_key=self._get_env_or_config(xai['api_key'], 'XAI_API_KEY'),
            model=xai['model'],
            timeout=xai['timeout'],
            temperature=xai['temperature'],
            max_tokens=xai['max_tokens']
        )
        
        # Load prompts config
        prompts = raw_config['prompts']
        self.prompts = PromptsConfig(
            primary=PromptConfig(
                system=prompts['primary']['system'],
                user_template=prompts['primary']['user_template']
            ),
            alternative=PromptConfig(
                system=prompts['alternative']['system'],
                user_template=prompts['alternative']['user_template']
            ),
            alternative_probability=prompts['alternative_probability']
        )
        
        # Load keyphrases
        self.keyphrases: List[str] = raw_config['keyphrases']
        
        # Load users config
        self.users: Dict[int, UserConfig] = {}
        for user_id_str, user_data in raw_config['users'].items():
            user_id = int(user_id_str)
            self.users[user_id] = UserConfig(
                name=user_data['name'],
                target_name=user_data['target_name'],
                friendly_fire_group=user_data.get('friendly_fire_group')
            )
        
        # Load friendly fire groups
        self.friendly_fire_groups: Dict[str, List[str]] = raw_config.get('friendly_fire_groups', {})
        
        # Load keyword victims mapping
        self.keyword_victims: Dict[str, str] = raw_config.get('keyword_victims', {})
        
        # Load STT config
        stt = raw_config['stt']
        self.stt = STTConfig(
            model_size=stt['model_size'],
            device=stt['device'],
            compute_type=stt['compute_type'],
            language=stt['language'],
            beam_size=stt['beam_size'],
            vad_filter=stt['vad_filter'],
            vad_min_silence_duration_ms=stt['vad_min_silence_duration_ms'],
            repetition_penalty=stt['repetition_penalty'],
            initial_prompt=stt['initial_prompt']
        )
        
        # Load TTS config
        tts = raw_config['tts']
        piper_config = None
        if tts['engine'] == 'piper' and 'piper' in tts:
            piper_config = PiperTTSConfig(
                executable_path=tts['piper']['executable_path'],
                model_path=tts['piper']['model_path']
            )
        
        self.tts = TTSConfig(
            engine=tts['engine'],
            piper=piper_config
        )
        
        # Load audio config
        audio = raw_config['audio']
        self.audio = AudioConfig(
            min_clip_seconds=audio['min_clip_seconds'],
            silence_finalize_ms=audio['silence_finalize_ms'],
            preroll_max_chunks=audio['preroll_max_chunks'],
            sample_rate=audio['sample_rate'],
            target_sample_rate=audio['target_sample_rate']
        )
        
        # Load ffmpeg config
        self.ffmpeg = FFmpegConfig(path=raw_config['ffmpeg']['path'])
        
        # Load audio files config
        audio_files = raw_config['audio_files']
        self.audio_files = AudioFilesConfig(
            startup=audio_files['startup'],
            shutdown=audio_files['shutdown']
        )
        
        # Load debug config
        debug = raw_config['debug']
        self.debug = DebugConfig(
            dump_wav_files=debug['dump_wav_files'],
            dump_directory=debug['dump_directory'],
            log_level=debug['log_level']
        )
        
        # Load connection config
        connection = raw_config['connection']
        self.connection = ConnectionConfig(
            max_restart_attempts=connection['max_restart_attempts'],
            restart_cooldown_seconds=connection['restart_cooldown_seconds']
        )
    
    def _get_env_or_config(self, config_value: str, env_var: str) -> str:
        """
        Get value from environment variable or config file.
        Environment variable takes precedence.
        
        Args:
            config_value: Value from config file
            env_var: Environment variable name
            
        Returns:
            The resolved value
        """
        env_value = os.getenv(env_var)
        if env_value:
            return env_value
        
        # Check if config value looks like a placeholder
        if config_value.startswith("YOUR_") or config_value == "":
            raise ValueError(
                f"Missing required configuration: {env_var}\n"
                f"Please set the {env_var} environment variable or update config.yaml"
            )
        
        return config_value
    
    def get_user_by_id(self, user_id: int) -> Optional[UserConfig]:
        """Get user configuration by Discord user ID."""
        return self.users.get(user_id)
    
    def check_friendly_fire(self, phrase: str, user_id: int) -> bool:
        """
        Check if phrase triggers friendly fire for the given user.
        
        Args:
            phrase: The detected keyphrase
            user_id: Discord user ID
            
        Returns:
            True if friendly fire detected, False otherwise
        """
        user = self.get_user_by_id(user_id)
        if not user or not user.friendly_fire_group:
            return False
        
        group_keywords = self.friendly_fire_groups.get(user.friendly_fire_group, [])
        return phrase in group_keywords
    
    def get_victim_for_keyword(self, keyword: str) -> str:
        """Get default victim name for a keyword."""
        return self.keyword_victims.get(keyword, "Friend")


# Global config instance (loaded on first import)
_config: Optional[Config] = None


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load or reload configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Config instance
    """
    global _config
    _config = Config(config_path)
    return _config


def get_config() -> Config:
    """
    Get the current configuration instance.
    
    Returns:
        Config instance
        
    Raises:
        RuntimeError: If config hasn't been loaded yet
    """
    global _config
    if _config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return _config

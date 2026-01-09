"""
Discord Voice Bot with AI Response Generation
A modular Discord bot that listens to voice chat, transcribes speech,
detects keywords, and responds with AI-generated audio.
"""

import asyncio
import os
import re
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import discord
from discord.ext import commands, voice_recv

# Local modules
from config_loader import load_config, get_config
from audio_processing import (
    UserBuffer, resample_48k_to_16k_mono_f32,
    guess_channels_from_pcm_len, write_wav, wait_for_file_ready
)
from stt_engine import SpeechToTextEngine
from tts_engine import create_tts_engine, TTSEngine
from response_generator import ResponseGenerator


# -------------------------
# Configuration & Setup
# -------------------------

# Load configuration
try:
    config = load_config()
except FileNotFoundError as e:
    print(f"ERROR: {e}")
    exit(1)
except Exception as e:
    print(f"ERROR loading configuration: {e}")
    exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.debug.log_level),
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# Suppress noisy logs from voice_recv and opus
logging.getLogger("discord.ext.voice_recv.reader").setLevel(logging.WARNING)
logging.getLogger("discord.ext.voice_recv.router").setLevel(logging.WARNING)
logging.getLogger("discord.opus").setLevel(logging.WARNING)

# Setup FFmpeg path
os.environ["PATH"] = config.ffmpeg.path + ";" + os.environ["PATH"]

# Initialize engines
stt_engine = SpeechToTextEngine(config.stt)
tts_engine = create_tts_engine(config.tts)
response_generator = ResponseGenerator(config)

print("[INIT] All engines initialized successfully")


# -------------------------
# Data Models
# -------------------------

@dataclass
class ClipJob:
    """Audio clip ready for STT processing."""
    user_id: int
    display_name: str
    pcm_48k: bytes
    channels: int
    guild_id: int


# -------------------------
# Queues
# -------------------------

job_queue: asyncio.Queue[ClipJob] = asyncio.Queue()
tts_queue: asyncio.Queue[Tuple[int, str]] = asyncio.Queue()


# -------------------------
# Utility Functions
# -------------------------

def normalize_text(s: str) -> str:
    """
    Normalize text for keyword matching.
    
    Args:
        s: Input text
        
    Returns:
        Normalized lowercase text with only alphanumeric characters
    """
    s = s.lower()
    # Remove punctuation, keep only letters, numbers, and basic unicode
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# -------------------------
# Discord Voice Sink
# -------------------------

class SpeakingSink(voice_recv.AudioSink):
    """
    Custom audio sink that receives per-user PCM audio and speaking events.
    Manages audio buffering and finalization for STT processing.
    """
    
    def __init__(self, job_queue: asyncio.Queue[ClipJob], guild_id: int):
        super().__init__()
        self.job_queue = job_queue
        self.guild_id = guild_id
        self.buffers: Dict[int, UserBuffer] = {}
        self._tick_task: Optional[asyncio.Task] = None
    
    def wants_opus(self) -> bool:
        return False
    
    def _get_or_create_buffer(self, user_id: int) -> UserBuffer:
        """Get or create a UserBuffer for the given user ID."""
        ub = self.buffers.get(user_id)
        if ub is None:
            ub = UserBuffer(preroll_max_chunks=config.audio.preroll_max_chunks)
            self.buffers[user_id] = ub
        return ub
    
    def write(self, user: discord.User | discord.Member, voice_data: voice_recv.VoiceData) -> None:
        """
        Called frequently from background thread when audio packets arrive.
        Must be fast and thread-safe.
        """
        try:
            pcm = getattr(voice_data, "pcm", None)
            if not pcm:
                return
            
            # Validate PCM size (typical Opus frames: 3840-23040 bytes for stereo int16)
            if len(pcm) < 100 or len(pcm) > 50000:
                return
            
            # Get channel count from metadata or guess
            channels = None
            fmt = getattr(voice_data, "format", None)
            if fmt is not None:
                channels = getattr(fmt, "channels", None)
            
            if not channels:
                channels = guess_channels_from_pcm_len(pcm)
            
            if channels < 1 or channels > 2:
                return
            
            ub = self._get_or_create_buffer(user.id)
            ub.add_pcm(pcm, channels=int(channels))
            
        except Exception:
            # Silently skip corrupted packets (network issues are common)
            pass
    
    def cleanup(self) -> None:
        """Clean up all user buffers."""
        for ub in self.buffers.values():
            ub.clear()
    
    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: discord.Member):
        """Called when a user starts speaking."""
        ub = self._get_or_create_buffer(member.id)
        ub.start_speaking()
    
    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: discord.Member):
        """Called when a user stops speaking."""
        ub = self.buffers.get(member.id)
        if ub:
            ub.stop_speaking()
    
    def start_finalize_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the background loop that finalizes audio clips."""
        if self._tick_task is None:
            self._tick_task = loop.create_task(self._finalize_loop())
    
    async def _finalize_loop(self) -> None:
        """
        Background loop that checks for completed utterances and
        queues them for STT processing.
        """
        while True:
            now = time.time()
            
            to_finalize: list[Tuple[int, UserBuffer]] = []
            for uid, ub in list(self.buffers.items()):
                stop_ts = ub.stop_ts
                if stop_ts is None:
                    continue
                
                # Check if silence duration threshold reached
                if (now - stop_ts) * 1000.0 >= config.audio.silence_finalize_ms:
                    # Check if clip meets minimum duration
                    if ub.duration_seconds() >= config.audio.min_clip_seconds:
                        to_finalize.append((uid, ub))
                    else:
                        ub.clear()
            
            # Finalize clips and queue for processing
            for uid, ub in to_finalize:
                pcm, channels = ub.finalize()
                job = ClipJob(
                    user_id=uid,
                    display_name=str(uid),
                    pcm_48k=pcm,
                    channels=channels,
                    guild_id=self.guild_id,
                )
                await self.job_queue.put(job)
            
            await asyncio.sleep(0.2)


# -------------------------
# Bot Setup
# -------------------------

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix=config.discord.command_prefix, intents=intents)

# Global state for voice connection management
_current_sink: Optional[SpeakingSink] = None
_current_vc: Optional[voice_recv.VoiceRecvClient] = None
_current_guild_id: Optional[int] = None
_last_restart = 0.0
_restart_attempts = 0


# -------------------------
# Voice Connection Management
# -------------------------

def on_listen_end(err: Exception | None):
    """
    Callback when voice listening ends (either normally or due to error).
    Implements automatic restart with exponential backoff.
    """
    global _last_restart, _restart_attempts
    
    if not err:
        # Successful completion
        _restart_attempts = 0
        return
    
    error_type = type(err).__name__
    now = time.time()
    time_since_last = now - _last_restart
    
    # Track restart attempts within a time window
    if time_since_last < config.connection.restart_cooldown_seconds:
        _restart_attempts += 1
    else:
        _restart_attempts = 1
    
    # Calculate exponential backoff delay
    min_delay = min(2 ** (_restart_attempts - 1), 30.0)
    
    if time_since_last < min_delay:
        logging.warning(
            f"Restart throttled (attempt #{_restart_attempts}). "
            f"Waiting {min_delay - time_since_last:.1f}s more..."
        )
        delay = min_delay - time_since_last
        bot.loop.call_later(delay, restart_listen)
        return
    
    # Check max restart attempts
    if _restart_attempts >= config.connection.max_restart_attempts:
        logging.error(
            f"Max restart attempts ({config.connection.max_restart_attempts}) reached. "
            "Manual intervention required."
        )
        return
    
    _last_restart = now
    
    if "OpusError" in error_type:
        logging.warning(f"Opus error detected (#{_restart_attempts}): {repr(err)}")
    else:
        logging.warning(f"Listen error (#{_restart_attempts}) {error_type}: {repr(err)}")
    
    bot.loop.call_soon_threadsafe(restart_listen)


def restart_listen():
    """Restart the voice listener with a new sink."""
    global _current_sink, _current_vc, _current_guild_id, _restart_attempts
    
    vc = _current_vc
    guild_id = _current_guild_id
    
    if vc is None or guild_id is None:
        logging.info("No active VC/sink to restart")
        _restart_attempts = 0
        return
    
    try:
        # Cleanup old sink
        if _current_sink is not None:
            try:
                _current_sink.cleanup()
            except Exception as cleanup_err:
                logging.warning(f"Cleanup warning: {repr(cleanup_err)}")
        
        time.sleep(0.1)
        
        # Create and start new sink
        sink = SpeakingSink(job_queue=job_queue, guild_id=guild_id)
        _current_sink = sink
        vc.listen(sink, after=on_listen_end)
        sink.start_finalize_loop(asyncio.get_running_loop())
        
        _restart_attempts = 0
        logging.info("Listener restarted successfully")
        
    except Exception as e:
        logging.error(f"Restart failed: {type(e).__name__} - {repr(e)}")
        _restart_attempts += 1
        
        if _restart_attempts >= config.connection.max_restart_attempts:
            logging.critical("Max restart attempts reached. Giving up.")
            return
        
        retry_delay = min(2 ** (_restart_attempts - 1), 30.0)
        logging.info(f"Retrying restart in {retry_delay:.1f}s (attempt #{_restart_attempts})")
        asyncio.get_running_loop().call_later(retry_delay, restart_listen)


# -------------------------
# Background Workers
# -------------------------

async def stt_worker():
    """
    Background worker that processes audio clips from the queue,
    runs STT, detects keywords, and generates responses.
    """
    loop = asyncio.get_running_loop()
    bad_fillers = {"mm", "hmm", "uh", "um", "huh", "ah", "eh", "oh"}
    
    while True:
        job = await job_queue.get()
        try:
            # Validate PCM data
            if not job.pcm_48k or len(job.pcm_48k) < 100:
                logging.debug(f"Skipping empty/tiny clip from user {job.user_id}")
                continue
            
            # Get display name from guild member
            guild = bot.get_guild(job.guild_id)
            display_name = job.display_name
            if guild:
                member = guild.get_member(job.user_id)
                if member:
                    display_name = member.display_name
            
            # Debug: dump WAV if enabled
            if config.debug.dump_wav_files:
                os.makedirs(config.debug.dump_directory, exist_ok=True)
                dump_path = os.path.join(
                    config.debug.dump_directory,
                    f"clip_{job.guild_id}_{job.user_id}_{int(time.time())}_{job.channels}ch.wav",
                )
                write_wav(dump_path, job.pcm_48k, sample_rate=48000, channels=job.channels)
            
            # Resample and transcribe
            audio_f32_16k = resample_48k_to_16k_mono_f32(job.pcm_48k, job.channels)
            text = await loop.run_in_executor(None, stt_engine.transcribe, audio_f32_16k)
            
            logging.info(f"[STT] ({job.channels}ch) {display_name}: {text}")
            
            # Normalize and filter
            norm = normalize_text(text)
            if not norm or norm in bad_fillers:
                continue
            
            # Check for keyword matches
            matched_phrase = None
            for phrase in config.keyphrases:
                if phrase.lower() in norm:
                    matched_phrase = phrase
                    break
            
            if not matched_phrase:
                continue
            
            # Get user configuration
            user_config = config.get_user_by_id(job.user_id)
            if not user_config:
                logging.warning(f"No user config found for ID {job.user_id}")
                continue
            
            # Check friendly fire
            if config.check_friendly_fire(matched_phrase.lower(), job.user_id):
                logging.info(
                    f"Friendly fire detected for {display_name} ({job.user_id}) "
                    f"with phrase '{matched_phrase}'. Skipping..."
                )
                continue
            
            # Generate response
            victim_name = config.get_victim_for_keyword(matched_phrase)
            announcement = response_generator.generate_announcement(
                speaker_name=user_config.name,
                target_name=user_config.target_name,
                phrase=matched_phrase,
                victim_name=victim_name
            )
            
            logging.info(f"[MATCH] Generated: {announcement}")
            
            # Synthesize to audio
            out_path = f"tts_{job.guild_id}_{job.user_id}_{int(time.time())}.wav"
            await loop.run_in_executor(None, tts_engine.synth_to_wav, announcement, out_path)
            await loop.run_in_executor(None, wait_for_file_ready, out_path)
            
            logging.debug(f"[TTS] WAV size: {os.path.getsize(out_path)} bytes")
            
            # Queue for playback
            await tts_queue.put((job.guild_id, out_path))
            
        except Exception as e:
            logging.error(f"STT worker error: {repr(e)}", exc_info=True)
        finally:
            job_queue.task_done()


async def tts_player():
    """
    Background worker that plays TTS audio files in voice channels.
    """
    while True:
        guild_id, wav_path = await tts_queue.get()
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                continue
            
            vc = guild.voice_client
            if not vc:
                continue
            
            # Wait for any current audio to finish
            while vc.is_playing():
                await asyncio.sleep(0.1)
            
            # Play the TTS audio
            audio = discord.FFmpegPCMAudio(wav_path, executable="ffmpeg")
            
            def after_play(err):
                if err:
                    logging.error(f"Playback error: {repr(err)}")
            
            vc.play(audio, after=after_play)
            
            # Wait for playback to complete
            while vc.is_playing():
                await asyncio.sleep(0.1)
            
        except Exception as e:
            logging.error(f"TTS player error: {repr(e)}", exc_info=True)
        finally:
            # Clean up WAV file
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception:
                pass
            tts_queue.task_done()


# -------------------------
# Bot Events
# -------------------------

@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord."""
    logging.info(f"Logged in as {bot.user}")
    
    # Start background workers
    bot.loop.create_task(stt_worker())
    bot.loop.create_task(tts_player())
    
    logging.info("Background workers started")


# -------------------------
# Bot Commands
# -------------------------

@bot.command()
async def join(ctx: commands.Context):
    """Join the voice channel of the command author."""
    global _current_sink, _current_vc, _current_guild_id
    
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ You need to join a voice channel first.")
        return
    
    # Connect to voice channel
    vc: voice_recv.VoiceRecvClient = await ctx.author.voice.channel.connect(
        cls=voice_recv.VoiceRecvClient,
        self_deaf=False,
    )
    
    _current_vc = vc
    _current_guild_id = ctx.guild.id
    
    await asyncio.sleep(0.5)  # Allow SSRC mapping to settle
    
    # Create and start sink
    sink = SpeakingSink(job_queue=job_queue, guild_id=ctx.guild.id)
    _current_sink = sink
    
    vc.listen(sink, after=on_listen_end)
    sink.start_finalize_loop(asyncio.get_running_loop())
    
    # Play startup sound if configured
    if os.path.exists(config.audio_files.startup):
        startup_audio = discord.FFmpegPCMAudio(
            config.audio_files.startup,
            executable="ffmpeg"
        )
        vc.play(startup_audio)
        while vc.is_playing():
            await asyncio.sleep(0.1)
    
    logging.info(f"Joined voice channel: {ctx.author.voice.channel.name}")
    await ctx.send(f"✅ Joined {ctx.author.voice.channel.name}")


@bot.command()
async def leave(ctx: commands.Context):
    """Leave the current voice channel."""
    if not ctx.voice_client:
        await ctx.send("❌ I'm not in a voice channel.")
        return
    
    # Play shutdown sound if configured
    if os.path.exists(config.audio_files.shutdown):
        shutdown_audio = discord.FFmpegPCMAudio(
            config.audio_files.shutdown,
            executable="ffmpeg"
        )
        ctx.voice_client.play(shutdown_audio)
        while ctx.voice_client.is_playing():
            await asyncio.sleep(0.1)
    
    await ctx.voice_client.disconnect()
    logging.info("Left voice channel")
    await ctx.send("✅ Left voice channel")


# -------------------------
# Main Entry Point
# -------------------------

if __name__ == "__main__":
    if not config.discord.token:
        logging.error("Discord token not configured!")
        exit(1)
    
    logging.info("Starting bot...")
    bot.run(config.discord.token)

# VoiceFlare: Discord Voice Bot with xAI Responses

A modular Discord bot that listens to voice channels, transcribes speech using Whisper, detects configurable keywords, and responds with AI-generated audio using XAI (Grok) and Text-to-Speech.

DISCLAIMER: This bot is developed solely for fun, and should be kept as a friends-only tool. Do NOT use this tool without the consent of others involved. I do not take responsibility for any illegal use! 

## Features

- 🎙️ **Real-time Voice Transcription**: Uses Faster Whisper for accurate speech-to-text
- 🤖 **AI Response Generation**: Leverages XAI (Grok) API for contextual responses
- 🔊 **Text-to-Speech**: Supports Piper TTS (high-quality neural) and Windows SAPI
- ⚙️ **Fully Configurable**: All settings, prompts, and users managed via YAML config
- 📦 **Modular Architecture**: Clean separation of concerns for easy customization
- 🔄 **Auto-recovery**: Automatic reconnection with exponential backoff
- 🎯 **Keyword Detection**: Customizable trigger phrases with friendly-fire protection

## Project Structure

```
discordbot/
├── bot.py                    # Main bot application
├── config.yaml               # Your configuration (copy from example)
├── config.example.yaml       # Configuration template
├── config_loader.py          # Configuration management
├── audio_processing.py       # Audio buffering and conversion
├── stt_engine.py            # Speech-to-text wrapper
├── tts_engine.py            # Text-to-speech engines
├── response_generator.py    # AI response generation
├── requirements.txt         # Python dependencies
├── ffmpeg/                  # FFmpeg binaries
├── piper/                   # Piper TTS (optional)
└── *.wav                    # Startup/shutdown sounds (optional)
```

## Requirements

- Python 3.10+
- Discord Bot Token
- XAI API Key (for Grok)
- FFmpeg (included in project)
- Optional: Piper TTS for high-quality voices

## Installation

### 1. Clone or Download

```bash
cd discordbot
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```


### 2. Install Piper and FFMPEG

This project utilizes Piper for speech recognition and FFMPEG for audio processing.

You can download Piper through this [link](https://github.com/rhasspy/piper)
and FFMPEG from [here](https://www.ffmpeg.org/).

### 3. Configuration

Copy the example configuration:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and fill in:

- **Discord Token**: Get from [Discord Developer Portal](https://discord.com/developers/applications)
- **XAI API Key**: Get from [X.AI](https://x.ai/)
- **User Mappings**: Add Discord user IDs and their associated names
- **Keywords**: Define trigger phrases
- **Prompts**: Customize AI behavior

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Enable these Privileged Gateway Intents:
   - Server Members Intent
   - Message Content Intent
5. Copy the bot token to your `config.yaml`
6. Invite the bot to your server using OAuth2 URL generator with these permissions:
   - View Channels
   - Send Messages
   - Connect
   - Speak

## Configuration Guide

### User Configuration

Each user needs a mapping in `config.yaml`:

```yaml
users:
  123456789012345678:  # Discord User ID
    name: "John"                    # Display name for announcements
    target_name: "Target"           # Name used in AI responses
    friendly_fire_group: "group1"   # Optional: prevent self-triggers
```

To get Discord User IDs:
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click a user → Copy User ID

### Keyword Configuration

Define trigger phrases:

```yaml
keyphrases:
  - "keyword1"
  - "keyword2"
  - "hello bot"
```

### Friendly Fire Groups

Prevent users from triggering on certain keywords:

```yaml
friendly_fire_groups:
  group1:
    - "keyword1"  # Users in group1 won't trigger on keyword1
  group2:
    - "keyword2"
```

### AI Prompts

Customize the AI behavior:

```yaml
prompts:
  primary:
    system: "You are a creative response generator..."
    user_template: "Generate a response for {speaker_name}..."
  
  alternative:
    system: "You are a calm mediator..."
    user_template: "Generate a calming response..."
  
  alternative_probability: 30  # % chance to use alternative prompt
```

### TTS Configuration

Choose between Piper (neural TTS) or Windows SAPI:

```yaml
tts:
  engine: "piper"  # or "windows_sapi"
  
  piper:
    executable_path: "piper/piper.exe"
    model_path: "piper/models/en_US-lessac-medium.onnx"
```

## Usage

### Start the Bot

```bash
python bot.py
```

### Discord Commands

- `!join` - Bot joins your voice channel and starts listening
- `!leave` - Bot leaves the voice channel

### How It Works

1. Bot joins your voice channel
2. Listens to all users speaking
3. Transcribes speech using Whisper
4. Detects configured keywords
5. Generates AI response using XAI
6. Plays response as audio using TTS

## Troubleshooting

### Bot not responding to voice

- Ensure bot has "Connect" and "Speak" permissions
- Check that `config.yaml` has correct user IDs
- Verify keywords are lowercase in config
- Check console logs for STT output

### Audio quality issues

- Try different Whisper model sizes: `tiny`, `base`, `small`, `medium`, `large`
- Adjust `min_clip_seconds` in config (default: 1.5)
- Enable debug mode to save audio clips for inspection

### Connection drops

- Check `max_restart_attempts` in config
- Verify network stability
- Look for Opus errors in logs

### Debug Mode

Enable debugging in `config.yaml`:

```yaml
debug:
  dump_wav_files: true
  dump_directory: "debug_wavs"
  log_level: "DEBUG"
```

This saves all processed audio clips for inspection.

## Customization

### Adding New TTS Engines

1. Create a new class in `tts_engine.py` inheriting from `TTSEngine`
2. Implement `synth_to_wav(text, out_path)` method
3. Add to `create_tts_engine()` factory function
4. Update `config.example.yaml` with new engine config

### Custom Response Logic

Modify `response_generator.py` to change how AI responses are generated:

- Edit `generate_announcement()` for different response formats
- Modify `_xai_response()` to use different AI models
- Adjust `_parse_xai_response()` for custom text processing

### Different STT Models

Change in `config.yaml`:

```yaml
stt:
  model_size: "medium"  # tiny, base, small, medium, large
  device: "cuda"         # cuda for GPU acceleration
  language: "en"         # Language code
```

## License

This project is provided as-is for personal and educational use.

## Credits

- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv) - Voice receiving
- [Faster Whisper](https://github.com/guillaumekln/faster-whisper) - Speech recognition
- [XAI SDK](https://github.com/xai-org/xai-python) - AI generation
- [Piper TTS](https://github.com/rhasspy/piper) - Neural text-to-speech

## Support

For issues and questions:
1. Check the Troubleshooting section
2. Review logs with `log_level: "DEBUG"`
3. Verify configuration against `config.example.yaml`

## Contributing

Contributions are welcome! Please:
1. Keep code modular and documented
2. Follow existing code style
3. Test changes thoroughly
4. Update documentation as needed

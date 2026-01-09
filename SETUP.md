# Quick Setup Guide

## First Time Setup (5 minutes)

### 1. Copy Configuration Template
```bash
cp config.example.yaml config.yaml
```

### 2. Get Discord Bot Token
1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Go to "Bot" → Click "Add Bot"
4. Enable these intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Click "Reset Token" → Copy the token
6. Paste into `config.yaml` under `discord: token:`

### 3. Get XAI API Key
1. Go to https://x.ai/
2. Sign up / Log in
3. Get your API key
4. Paste into `config.yaml` under `xai: api_key:`

### 4. Add Your Discord User ID
1. Open Discord
2. Settings → Advanced → Enable "Developer Mode"
3. Right-click your name → "Copy User ID"
4. Add to `config.yaml`:
```yaml
users:
  YOUR_USER_ID_HERE:  # Replace with your copied ID
    name: "YourName"
    target_name: "SomeTarget"
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

### 6. Run the Bot
```bash
python bot.py
```

### 7. Invite Bot to Server
1. Go back to Discord Developer Portal
2. OAuth2 → URL Generator
3. Select scopes: `bot`
4. Select permissions:
   - ✅ View Channels
   - ✅ Send Messages  
   - ✅ Connect
   - ✅ Speak
5. Copy the generated URL
6. Open in browser → Select your server

### 8. Test It
1. Join a voice channel in Discord
2. Type `!join` in a text channel
3. Say one of your configured keyphrases
4. Bot should respond with audio!

## Minimal config.yaml Example

```yaml
discord:
  token: "YOUR_DISCORD_TOKEN_HERE"
  command_prefix: "!"

xai:
  api_key: "YOUR_XAI_KEY_HERE"
  model: "grok-4-1-fast-reasoning"
  timeout: 3600
  temperature: 0.1
  max_tokens: 128

prompts:
  primary:
    system: "You are a helpful assistant. Keep responses short."
    user_template: "{speaker_name} said something. Respond briefly."
  alternative:
    system: "You are calm and friendly."
    user_template: "Say something nice to {speaker_name}."
  alternative_probability: 30

keyphrases:
  - "hello bot"
  - "hey assistant"

users:
  123456789012345678:  # Your Discord User ID
    name: "User"
    target_name: "Friend"

friendly_fire_groups: {}
keyword_victims: {}

stt:
  model_size: "small"
  device: "cpu"
  compute_type: "int8"
  language: "en"
  beam_size: 5
  vad_filter: true
  vad_min_silence_duration_ms: 500
  repetition_penalty: 1.1
  initial_prompt: "Transcribe accurately."

tts:
  engine: "windows_sapi"  # No extra setup needed on Windows

audio:
  min_clip_seconds: 1.5
  silence_finalize_ms: 600
  preroll_max_chunks: 25
  sample_rate: 48000
  target_sample_rate: 16000

ffmpeg:
  path: "ffmpeg/bin"

audio_files:
  startup: "startup.wav"
  shutdown: "engine_stop.wav"

debug:
  dump_wav_files: false
  dump_directory: "debug_wavs"
  log_level: "INFO"

connection:
  max_restart_attempts: 10
  restart_cooldown_seconds: 30
```

## Troubleshooting

### "Configuration file not found"
→ Run `cp config.example.yaml config.yaml`

### "Discord token not configured"
→ Make sure you pasted your token in `config.yaml` (not the example file)

### Bot joins but doesn't respond
→ Check that you added your Discord User ID to the `users` section

### "No module named 'yaml'"
→ Run `pip install PyYAML`

### Bot can't hear voice
→ Make sure you enabled "Server Members Intent" and "Message Content Intent"

## Next Steps

- Customize keyphrases in `config.yaml`
- Adjust AI prompts for your use case
- Add more users with their IDs
- Try different Whisper models (`tiny`, `small`, `medium`)
- Use Piper TTS for better voice quality

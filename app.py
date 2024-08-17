#!/usr/bin/env python3
import asyncio
import io
import re
import sys
import tempfile
import traceback
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from queue import Queue
from sclib import SoundcloudAPI, Track

# dot env load
load_dotenv()

# get token
discord_bot_token = os.getenv("DISCORD_BOT_TOKEN", None)
ffmpeg_path = os.getenv("FFMPEG_PATH", None)

if not any([discord_bot_token, ffmpeg_path]):
    exit(1)

# Now playing
now_playing: bool = False

# play list
music_queue = Queue()

# discord
intents = discord.Intents.default()  # intents active
intents.messages = True  # set react to message event
intents.guilds = True  # set react to server(guild) event
intents.message_content = True  # set read message

# / + query
client = commands.Bot(command_prefix="/toshiaki_", intents=intents)

# play music
async def start_playback(message: discord.Message):
    global now_playing
    while now_playing:
        if music_queue.qsize() == 0:
            await asyncio.sleep(2)
            continue

        music_data = music_queue.get()
        try:
            service = music_data["service"]

            if service == "soundcloud":
                api = SoundcloudAPI()
                track = api.resolve(music_data["url"])
                assert type(track) is Track

                with tempfile.NamedTemporaryFile(mode="w+b", prefix="music_", suffix=".mp3") as tf:
                    track.write_mp3_to(tf)
                    tf.seek(0)

                    audio_source = discord.FFmpegPCMAudio(executable=ffmpeg_path, source=tf.name)

                    trace_name=f"{track.artist} - {track.title}"
                    await client.change_presence(activity=discord.Activity(name=trace_name, type=discord.ActivityType.playing))

                    message.guild.voice_client.play(audio_source)

                    while (message.guild.voice_client and message.guild.voice_client.is_playing()):
                        await asyncio.sleep(1)

                    if message.guild.voice_client:
                        message.guild.voice_client.stop()

        except Exception as ex:
            t, v, tb = sys.exc_info()
            print(traceback.format_exception(t,v,tb))
            print(traceback.format_tb(ex.__traceback__))

@client.event
async def on_ready():
    pass


@client.command(name="join")
async def join(message: discord.Message):
    # メッセージの送信者がbotだった場合は無視する
    if message.author.bot:
        return

    # not developer
    if message.author.name != "m10i":
       return

    if message.author.voice is None:
        return

    await message.author.voice.channel.connect()
    await message.channel.send("接続しました")


@client.command(name="leave")
async def leave(message: discord.Message):
    # メッセージの送信者がbotだった場合は無視する
    if message.author.bot:
        return

    global now_playing
    now_playing = False
    await message.guild.voice_client.disconnect()
    await message.channel.send("切断しました")


## add music from SoundCloud
@client.command(name="add")
async def search(message: discord.Message, query):
    url:str|None = None

    if (re.match("^https://soundcloud.com/([\-/\w]+)", query)):
        url = query

    if url is None:
        return

    queue = None
    try:
        api = SoundcloudAPI()
        track = api.resolve(url)
        assert type(track) is Track

        queue = {
            "service": "soundcloud",
            "url": url,
            "artist": track.artist,
            "title": track.title
        }
        print("[INFO]", url)
    except Exception as ex:
        t, v, tb = sys.exc_info()
        print(traceback.format_exception(t,v,tb))
        print(traceback.format_tb(ex.__traceback__))

    if queue is not None:
        music_queue.put(queue)
        #await message.channel.send(f"音楽が追加されました : {queue['artist']} - {queue['title']}")

        global now_playing
        if now_playing == False:
            now_playing = True
            await start_playback(message=message)

## play music
@client.command(name="play")
async def play(message: discord.Message):
    if message.guild.voice_client is None:
        await message.channel.send("ボイスチャンネルに接続していません")
        return

    global now_playing
    if now_playing == False:
        now_playing = True
        await start_playback(message=message)

client.run(discord_bot_token)

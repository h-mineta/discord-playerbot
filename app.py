#!/usr/bin/env python3
from discord.ext import commands
from dotenv import load_dotenv
from pprint import pprint
from queue import Queue
from sclib import SoundcloudAPI, Track
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio
import discord
import logging
import os
import re
import spotipy
import sys
import tempfile
import traceback

# dot env load
load_dotenv()

# get env
discord_bot_name = os.getenv("DISCORD_BOT_NAME", "Music Player Bot")
discord_bot_token = os.getenv("DISCORD_BOT_TOKEN", None)
discord_bot_command_prefix = os.getenv("DISCORD_BOT_COMMAND_PREFIX", "/")
ffmpeg_path = os.getenv("FFMPEG_PATH", None)

if not all([
    discord_bot_name,
    discord_bot_token,
    discord_bot_command_prefix,
    ffmpeg_path
    ]):
    exit(1)

# logging
discord.utils.setup_logging(level=logging.INFO, root=False)

# discord
intents = discord.Intents.default()  # intents active
intents.messages = True  # set react to message event
intents.guilds = True  # set react to server(guild) event
intents.message_content = True  # set read message

bot = commands.Bot(command_prefix=discord_bot_command_prefix, intents=intents)

class DiscordMusicPlayer(commands.Cog):
    # Now playing
    now_playing: bool = False

    # play list
    music_queue = Queue()

    bot: commands.Bot

    # コンストラクタ。
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.soundcloud_client = SoundcloudAPI()

    # play music
    async def start_playback(self, ctx: discord.Message):
        while self.now_playing:
            if self.music_queue.qsize() == 0 or ctx.guild.voice_client is None:
                await asyncio.sleep(2)
                continue

            music_data = self.music_queue.get()
            try:
                service = music_data["service"]

                if service == "soundcloud":
                    track = self.soundcloud_client.resolve(music_data["url"])
                    assert type(track) is Track

                    with tempfile.NamedTemporaryFile(mode="w+b", prefix="music_soundcloud_", suffix=".mp3") as tf:
                        track.write_mp3_to(tf)
                        tf.seek(0)

                        audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable=ffmpeg_path, source=tf.name), volume=1.5)

                        trace_name=f"{track.artist} - {track.title}"
                        await self.bot.change_presence(activity=discord.Activity(name=trace_name, type=discord.ActivityType.playing))

                        ctx.guild.voice_client.play(audio_source)

                        while (ctx.guild.voice_client and ctx.guild.voice_client.is_playing()):
                            await asyncio.sleep(1)

                        if ctx.guild.voice_client:
                            ctx.guild.voice_client.stop()

                        await self.bot.change_presence(activity=discord.Activity(name="", type=discord.ActivityType.playing))

                elif service == "spotify":
                    with tempfile.NamedTemporaryFile(mode="w+b", prefix="music_spofity_", suffix=".mp3") as tf:
                        pass

            except Exception as ex:
                t, v, tb = sys.exc_info()
                print(traceback.format_exception(t,v,tb))
                print(traceback.format_tb(ex.__traceback__))


    async def on_ready(self):
        pass


    @commands.command(name="join")
    async def join(self, ctx: discord.Message):
        # メッセージの送信者がbotだった場合は無視する
        if ctx.author.bot:
            return

        if ctx.author.voice is None:
            await ctx.channel.send("ボイスチャンネルに入ってから呼んでください")
            return

        await ctx.author.voice.channel.connect()
        await ctx.channel.send("接続しました")


    @commands.command(name="leave")
    async def leave(self, ctx: discord.Message):
        # メッセージの送信者がbotだった場合は無視する
        if ctx.author.bot:
            return

        global now_playing
        now_playing = False
        await ctx.guild.voice_client.disconnect()
        await ctx.channel.send("切断しました")


    ## add music
    @commands.command(name="add")
    async def add_music(self, ctx: discord.Message, *args):
        query = " ".join(args)
        if query == "":
            return

        print("[DEBUG]", query)

        data_unit: dict = None
        try:
            if (re.match("^https://soundcloud.com/([\-/\w]+)", query)):
                track = self.soundcloud_client.resolve(query)
                assert type(track) is Track

                data_unit = {
                    "service": "soundcloud",
                    "url": track.uri,
                    "artist": track.artist,
                    "title": track.title
                }
                print("[INFO]", "SoundClound", track.uri)


        except Exception as ex:
            t, v, tb = sys.exc_info()
            print(traceback.format_exception(t,v,tb))
            print(traceback.format_tb(ex.__traceback__))

        if data_unit is not None:
            self.music_queue.put(data_unit)
            #await message.channel.send(f"音楽が追加されました : {queue['artist']} - {queue['title']}")

            if self.now_playing == False:
                self.now_playing = True
                await self.start_playback(ctx=ctx)


    ## play music
    @commands.command(name="play")
    async def play(self, ctx: discord.Message):
        if ctx.guild.voice_client is None:
            await ctx.channel.send("ボイスチャンネルに接続していません")
            return

        if self.now_playing == False:
            self.now_playing = True
            await self.start_playback(ctx=ctx)


    ## stop music
    @commands.command(name="stop")
    async def stop(self, ctx: discord.Message):
        if ctx.guild.voice_client is None:
            await ctx.channel.send("ボイスチャンネルに接続していません")
            return

        if self.now_playing == True:
            ctx.guild.voice_client.stop()


async def main():
    discord_music_player = DiscordMusicPlayer(bot)

    async with bot:
        await bot.add_cog(discord_music_player)
        await bot.start(discord_bot_token)

if __name__ == "__main__":
    asyncio.run(main())

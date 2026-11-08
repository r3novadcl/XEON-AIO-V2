import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import (
    LayoutView, Container, Section, TextDisplay, Separator,
    Thumbnail, ActionRow, Button, Select
)
import lavalink
import aiosqlite
import re
import math
import random
import asyncio
import inspect
import time

ACCENT_COLOR = 0x010101

from utils.config import LAVALINK_NODES

NODE_DOWN_FAST_FAIL = 30.0
NODE_RATE_COOLDOWN  = 60.0
RESTORE_STAGGER     = 3.0
MIGRATE_STAGGER     = 1.0

MAIN_NODE_NAME   = LAVALINK_NODES[0]["name"] if LAVALINK_NODES else ""
MAIN_NODE_REGION = "main"

URL_REGEX     = re.compile(r"https?://(?:www\.)?.+")
YOUTUBE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/.+"
)

SPOTIFY_URL_REGEX    = re.compile(r"(?:https?://)?open\.spotify\.com/.+", re.I)
DEEZER_URL_REGEX     = re.compile(r"(?:https?://)?(?:www\.)?deezer\.com/.+", re.I)
APPLE_URL_REGEX      = re.compile(r"(?:https?://)?music\.apple\.com/.+", re.I)
SOUNDCLOUD_URL_REGEX = re.compile(r"(?:https?://)?(?:www\.)?soundcloud\.com/.+", re.I)

SUPPORTED_URL_PATTERNS = (
    YOUTUBE_REGEX, SPOTIFY_URL_REGEX, DEEZER_URL_REGEX,
    APPLE_URL_REGEX, SOUNDCLOUD_URL_REGEX,
)

SOURCE_ALIASES = {
    "spotify:":    "spsearch:",
    "sp:":         "spsearch:",
    "soundcloud:": "scsearch:",
    "sc:":         "scsearch:",
    "deezer:":     "dzsearch:",
    "dz:":         "dzsearch:",
    "apple:":      "amsearch:",
    "am:":         "amsearch:",
}

KNOWN_SEARCH_PREFIXES = ("ytsearch:", "spsearch:", "dzsearch:", "scsearch:", "amsearch:")

MAX_QUEUE_DISPLAY = 10
DEFAULT_VOLUME    = 100

DB_DIR  = "db"
DB_PATH = os.path.join(DB_DIR, "music_247.db")

from XEON.emojis import E as _EMGR

_MUSIC_KEY_MAP = {
    "MUSIC": "MUSIC_NOTE", "PLAY": "PLAY", "PAUSE": "PAUSE",
    "SKIP": "SKIP", "PREVIOUS": "BACKWARD", "STOP": "STOP",
    "LOOP": "LOOP", "SHUFFLE": "SHUFFLE", "QUEUE": "QUEUE",
    "VOLUME": "LYRICS", "CHECK": "SUCCESS", "CROSS": "ERROR",
    "ARROW": "ARROW", "TIMER": "TIMER", "AUTHOR": "AUTHOR",
    "LIVE": "LIVE", "LOADING": "LOADING_ALT", "WARN": "WARNING",
    "YOUTUBE": "YOUTUBE", "HEART": "HEART", "AUTOPLAY": "AUTOPLAY",
    "TRASH": "TRASH", "NEXT": "NEXT_TRACK", "SORT": "FILTER",
    "DENIED": "ERROR", "ENABLED": "SUCCESS",
    "REWIND": "REWIND", "FORWARD": "FORWARD",
}

class _EmojiProxy:
    def __getitem__(self, key):
        return _EMGR[_MUSIC_KEY_MAP.get(key, key)]

    def get(self, key, default=None):
        value = self[key]
        if value in (None, "", "❔") and default is not None:
            return default
        return value

    def __contains__(self, key):
        return _MUSIC_KEY_MAP.get(key, key) in _EMGR

EMOJI = _EmojiProxy()

EMOJI_FALLBACK = {
    "MUSIC": "🎵", "PLAY": "▶️", "PAUSE": "⏸️", "SKIP": "⏭️",
    "PREVIOUS": "⏮️", "STOP": "⏹️", "LOOP": "🔁", "SHUFFLE": "🔀",
    "QUEUE": "📜", "VOLUME": "🔊", "CHECK": "✅", "CROSS": "❌",
    "ARROW": "▶️", "TIMER": "⏱️", "AUTHOR": "👤", "LIVE": "🔴",
    "LOADING": "🔄", "WARN": "⚠️", "YOUTUBE": "▶️", "HEART": "💚",
    "AUTOPLAY": "🔄", "TRASH": "🗑️", "NEXT": "⏭️", "SORT": "🔀",
    "DENIED": "❌", "ENABLED": "✅",
}

def E(key: str) -> str:
    return EMOJI.get(key, EMOJI_FALLBACK.get(key, ""))

def safe_emoji(key: str):
    raw = EMOJI.get(key, "")
    if raw.startswith("<"):
        try:
            return discord.PartialEmoji.from_str(raw)
        except Exception:
            pass
    return EMOJI_FALLBACK.get(key, "▶️")

def format_duration(ms: int) -> str:
    if not ms or ms <= 0:
        return "00:00"
    s = int(ms / 1000)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def format_duration_pretty(ms: int) -> str:
    if not ms or ms <= 0:
        return "0s"
    s = int(ms / 1000)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def build_simple_container(text: str, footer: str = None) -> Container:
    items = [TextDisplay(text)]
    if footer:
        items.append(Separator())
    return Container(*items, accent_color=ACCENT_COLOR)

def build_denied_container(reason: str) -> Container:
    return Container(
        TextDisplay(
            f"### {E('WARN')} Process Denied\n"
            f"{E('DENIED')} {reason}"
        ),
        accent_color=ACCENT_COLOR,
    )

def build_unavailable_container() -> Container:
    return Container(
        TextDisplay(
            "**Music server unavailable**\n"
            "- All music nodes are offline right now.\n"
            "- Nothing is wrong with your setup.\n"
            "- Please try again in a minute."
        ),
        accent_color=ACCENT_COLOR,
    )

def build_connecting_container() -> Container:
    return Container(
        TextDisplay(
            "**Connecting to the music server**\n"
            "- Hold on, this usually takes a few seconds."
        ),
        accent_color=ACCENT_COLOR,
    )

def build_enabled_container(title: str, body: str) -> Container:
    return Container(
        TextDisplay(
            f"### {E('ENABLED')} {title}\n"
            f"{E('ARROW')} {body}"
        ),
        accent_color=ACCENT_COLOR,
    )

class LavalinkVoiceClient(discord.VoiceProtocol):

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client    = client
        self.channel   = channel
        self._guild    = channel.guild
        self._destroyed = False

        if not hasattr(client, "lavalink") or client.lavalink is None:
            raise RuntimeError("Lavalink client not initialized on bot!")

        self.lavalink: lavalink.Client = client.lavalink

    async def on_voice_server_update(self, data: dict):
        lavalink_data = {
            "t": "VOICE_SERVER_UPDATE",
            "d": {
                "guild_id"  : str(self._guild.id),
                "token"     : data["token"],
                "endpoint"  : data["endpoint"],
            }
        }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data: dict):
        channel_id = data.get("channel_id")

        if not channel_id:
            self.cleanup()
            player = self.lavalink.player_manager.get(self._guild.id)
            if player:
                player.channel_id = None
            return

        channel = self._guild.get_channel(int(channel_id))
        if channel:
            self.channel = channel

        lavalink_data = {
            "t": "VOICE_STATE_UPDATE",
            "d": {
                "guild_id"  : str(self._guild.id),
                "user_id"   : str(self.client.user.id),
                "channel_id": channel_id,
                "session_id": data.get("session_id", ""),
            }
        }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(
        self, *,
        timeout   : float,
        reconnect : bool,
        self_deaf : bool = True,
        self_mute : bool = False,
    ) -> None:
        self.lavalink.player_manager.create(guild_id=self._guild.id)
        await self._guild.change_voice_state(
            channel   = self.channel,
            self_mute = self_mute,
            self_deaf = self_deaf,
        )

    async def disconnect(self, *, force: bool = False) -> None:
        player = self.lavalink.player_manager.get(self._guild.id)

        if not force and player and not player.is_connected:
            return

        await self._guild.change_voice_state(channel=None)

        self.cleanup()

        if not self._destroyed:
            self._destroyed = True
            try:
                await self.lavalink.player_manager.destroy(self._guild.id)
            except Exception:
                pass

    async def move_to(self, channel: discord.abc.Connectable):
        await self._guild.change_voice_state(channel=channel)
        self.channel = channel

class AddedToQueueView(LayoutView):
    def __init__(self, cog, guild_id: int, track, requester: discord.Member):
        super().__init__(timeout=180)
        self.cog       = cog
        self.guild_id  = guild_id
        self.track     = track
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_items()
        t     = self.track
        thumb = self.cog._get_thumbnail(t)

        body = (
            f"### {E('QUEUE')} Added to Queue\n\n"
            f"{E('YOUTUBE')} [**{t.title}**]({t.uri}) — {t.author}\n"
            f"**Duration:** `{format_duration(t.duration)}`\n"
            f"**Requested by** {self.requester.mention} "
            f"(`{self.requester.name}`)"
        )

        section = Section(
            TextDisplay(body),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=thumb),
                description="Track Thumbnail",
            ),
        )

        playnext_btn = Button(
            emoji     = safe_emoji("NEXT"),
            label     = "Play Next",
            style     = discord.ButtonStyle.secondary,
            custom_id = f"atq_playnext_{t.identifier[:40]}",
        )
        playnext_btn.callback = self._play_next

        remove_btn = Button(
            emoji     = safe_emoji("TRASH"),
            label     = "Remove",
            style     = discord.ButtonStyle.danger,
            custom_id = f"atq_remove_{t.identifier[:40]}",
        )
        remove_btn.callback = self._remove

        container = Container(
            section,
            Separator(),
            ActionRow(playnext_btn, remove_btn),
            accent_color=ACCENT_COLOR,
        )
        self.add_item(container)

    async def _play_next(self, interaction: discord.Interaction):
        if not await self.cog._check_voice(interaction):
            return
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        if not player:
            return await interaction.response.defer()

        for i, qt in enumerate(player.queue):
            if qt.identifier == self.track.identifier:
                player.queue.pop(i)
                player.queue.insert(0, qt)
                break

        v = LayoutView(timeout=None)
        v.add_item(build_enabled_container(
            "Play Next",
            f"**{self.track.title}** will play next.",
        ))
        await interaction.response.send_message(view=v, ephemeral=True)

    async def _remove(self, interaction: discord.Interaction):
        if not await self.cog._check_voice(interaction):
            return
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        if not player:
            return await interaction.response.defer()

        for i, qt in enumerate(player.queue):
            if qt.identifier == self.track.identifier:
                player.queue.pop(i)
                break

        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(
            f"{E('TRASH')} Removed **{self.track.title}** from queue."
        ))
        await interaction.response.edit_message(view=v)

class MusicControlView(LayoutView):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def build(self, player):
        self.clear_items()
        track = player.current

        if not track:
            self.add_item(build_simple_container(
                f"{E('CROSS')} Nothing is playing right now.",
                footer="Use the play command to start",
            ))
            return self

        thumb = self.cog._get_thumbnail(track)
        req   = self.cog.bot.get_user(track.requester)
        req_s = req.name if req else "Unknown"
        loop_label = {0: "Off", 1: "Track", 2: "Queue"}.get(player.loop, "Off")
        duration = "Live" if track.stream else format_duration_pretty(track.duration)

        body = (
            f"### {E('MUSIC')} Now Playing\n"
            f"### **{track.title[:200]}**\n"
            f"{E('ARROW')} **Author:** `{track.author}`\n"
            f"{E('ARROW')} **Duration:** `{duration}`\n"
            f"{E('ARROW')} **Loop:** `{loop_label}`\n"
            f"{E('ARROW')} **Source:** [Open track]({track.uri})"
        )

        section = Section(
            TextDisplay(body),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=thumb),
                description="Track Thumbnail",
            ),
        )

        ap_on = self.cog.autoplay_states.get(self.guild_id, False)
        on    = discord.ButtonStyle.success
        off   = discord.ButtonStyle.secondary

        def btn(key, callback, cid, style=off, fallback=None):
            raw = EMOJI.get(key, "")
            emoji = safe_emoji(key) if raw else fallback
            b = Button(emoji=emoji, style=style, custom_id=cid)
            b.callback = callback
            return b

        row1 = ActionRow(
            btn("AUTOPLAY", self.cog.btn_autoplay, "mc_autoplay", on if ap_on else off),
            btn("PREVIOUS", self.cog.btn_previous, "mc_previous"),
            btn("PAUSE" if not player.paused else "PLAY", self.cog.btn_playpause, "mc_playpause", on if not player.paused else off),
            btn("SKIP", self.cog.btn_skip, "mc_skip"),
            btn("LOOP", self.cog.btn_loop, "mc_loop", on if player.loop else off),
        )
        row2 = ActionRow(
            btn("SHUFFLE", self.cog.btn_shuffle, "mc_shuffle"),
            btn("REWIND", self.cog.btn_rewind, "mc_rewind", fallback="⏪"),
            btn("STOP", self.cog.btn_stop, "mc_stop", discord.ButtonStyle.danger),
            btn("FORWARD", self.cog.btn_forward, "mc_forward", fallback="⏩"),
            btn("HEART", self.cog.btn_heart, "mc_heart"),
        )

        container = Container(
            section,
            TextDisplay(f"Requested by: {req_s}"),
            Separator(),
            row1,
            row2,
            accent_color=ACCENT_COLOR,
        )
        self.add_item(container)
        return self

class QueueView(LayoutView):
    def __init__(self, cog, guild_id: int, page: int = 0):
        super().__init__(timeout=180)
        self.cog      = cog
        self.guild_id = guild_id
        self.page     = page

    def build(self, player):
        self.clear_items()

        queue       = list(player.queue)
        total_pages = max(1, math.ceil(len(queue) / MAX_QUEUE_DISPLAY))
        self.page   = max(0, min(self.page, total_pages - 1))

        start = self.page * MAX_QUEUE_DISPLAY
        chunk = queue[start:start + MAX_QUEUE_DISPLAY]

        if not queue:
            q_text = f"{E('CROSS')} The queue is empty."
        else:
            lines  = [
                f"`{i:02d}.` [{t.title[:45]}]({t.uri})"
                for i, t in enumerate(chunk, start=start + 1)
            ]
            q_text = "\n".join(lines)

        req = None
        if player.current and player.current.requester:
            req = self.cog.bot.get_user(player.current.requester)
        req_s = f"`{req.name}`" if req else "Unknown"

        body = f"### {E('QUEUE')} Music Queue [{len(queue)}]\n\n{q_text}"

        prev_btn = Button(
            emoji=safe_emoji("PREVIOUS"), style=discord.ButtonStyle.secondary,
            custom_id="qv_prev", disabled=(self.page <= 0),
        )
        prev_btn.callback = self._prev_page

        del_btn = Button(
            emoji=safe_emoji("TRASH"), style=discord.ButtonStyle.danger,
            custom_id="qv_clear",
        )
        del_btn.callback = self._clear_queue

        next_btn = Button(
            emoji=safe_emoji("SKIP"), style=discord.ButtonStyle.secondary,
            custom_id="qv_next", disabled=(self.page >= total_pages - 1),
        )
        next_btn.callback = self._next_page

        sort_btn = Button(
            emoji=safe_emoji("SORT"), style=discord.ButtonStyle.secondary,
            custom_id="qv_sort",
        )
        sort_btn.callback = self._shuffle_queue

        page_btn = Button(
            label     = f"{self.page + 1}/{total_pages}",
            style     = discord.ButtonStyle.secondary,
            custom_id = "qv_page",
            disabled  = True,
        )

        components = [
            TextDisplay(body),
            Separator(),
            TextDisplay(f"Page {self.page + 1}/{total_pages} | Requested by {req_s}"),
            Separator(),
            ActionRow(prev_btn, del_btn, next_btn, sort_btn, page_btn),
        ]

        if chunk:
            opts = [
                discord.SelectOption(
                    label       = f"{start + i}. {t.title[:80]}",
                    value       = str(start + i - 1),
                    description = f"Duration: {format_duration(t.duration)}",
                )
                for i, t in enumerate(chunk[:25], start=1)
            ]
            sel = Select(
                placeholder = "↪ Select to Play Next",
                options     = opts,
                custom_id   = "qv_sel",
            )
            sel.callback = self._select_playnext
            components.append(ActionRow(sel))

        self.add_item(Container(*components, accent_color=ACCENT_COLOR))
        return self

    async def _prev_page(self, interaction: discord.Interaction):
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        self.page -= 1
        self.build(player)
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction):
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        self.page += 1
        self.build(player)
        await interaction.response.edit_message(view=self)

    async def _clear_queue(self, interaction: discord.Interaction):
        if not await self.cog._check_voice(interaction):
            return
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        player.queue.clear()
        self.build(player)
        await interaction.response.edit_message(view=self)

    async def _shuffle_queue(self, interaction: discord.Interaction):
        if not await self.cog._check_voice(interaction):
            return
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        random.shuffle(player.queue)
        self.build(player)
        await interaction.response.edit_message(view=self)

    async def _select_playnext(self, interaction: discord.Interaction):
        if not await self.cog._check_voice(interaction):
            return
        player = self.cog.lavalink.player_manager.get(self.guild_id)
        idx = int(interaction.data["values"][0])
        if 0 <= idx < len(player.queue):
            t = player.queue.pop(idx)
            player.queue.insert(0, t)
        self.build(player)
        await interaction.response.edit_message(view=self)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot                  = bot
        self.lavalink             : lavalink.Client = None
        self.now_playing_messages : dict[int, discord.Message] = {}
        self.autoplay_states      : dict[int, bool]            = {}
        self.mode_247             : dict[int, bool]            = {}
        self.recent_tracks        : dict[int, list]            = {}
        self._last_announced      : dict[int, str]             = {}
        self._track_retry_counts  : dict[int, dict[str, int]]  = {}
        self._node_ready          = asyncio.Event()
        self._node_down_until     : float                      = 0.0
        self._node_cooldowns      : dict[str, float]           = {}
        self.history              : dict[int, list]            = {}
        self._restore_lock        = asyncio.Lock()
        self._was_all_down        = False
        self.db_path              = DB_PATH
        bot.loop.create_task(self._init_lavalink())

    def cog_unload(self):
        if self.lavalink:
            try:
                self.lavalink._event_hooks.clear()
            except Exception:
                pass

    async def _init_db(self):
        os.makedirs(DB_DIR, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS mode_247 (
                    guild_id         INTEGER PRIMARY KEY,
                    voice_channel_id INTEGER NOT NULL,
                    text_channel_id  INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS liked (
                    user_id  INTEGER NOT NULL,
                    uri      TEXT NOT NULL,
                    title    TEXT,
                    author   TEXT,
                    duration INTEGER,
                    PRIMARY KEY (user_id, uri)
                )
                """
            )
            await db.commit()

    async def _db_set_247(self, guild_id: int, voice_channel_id: int, text_channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO mode_247 (guild_id, voice_channel_id, text_channel_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    voice_channel_id = excluded.voice_channel_id,
                    text_channel_id  = excluded.text_channel_id
                """,
                (guild_id, voice_channel_id, text_channel_id),
            )
            await db.commit()

    async def _db_remove_247(self, guild_id: int):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM mode_247 WHERE guild_id = ?", (guild_id,))
                await db.commit()
        except Exception as e:
            print(f"[Music] Failed to remove 24/7 db row for {guild_id}: {e}")

    async def _db_get_all_247(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT guild_id, voice_channel_id, text_channel_id FROM mode_247"
            ) as cur:
                return await cur.fetchall()

    async def _restore_247(self):
        if self._restore_lock.locked():
            return
        async with self._restore_lock:
            await self._restore_247_inner()

    async def _restore_247_inner(self):
        try:
            rows = await self._db_get_all_247()
        except Exception as e:
            print(f"[Music] Failed to read 24/7 db: {e}")
            return

        if not rows:
            return

        print(f"[Music] Restoring 24/7 mode for {len(rows)} guild(s)...")
        for index, (guild_id, voice_channel_id, text_channel_id) in enumerate(rows):
            if index:
                await asyncio.sleep(RESTORE_STAGGER)
            if not self._node_ready.is_set():
                print("[Music] Nodes went offline during 24/7 restore, stopping.")
                return
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            vc = guild.get_channel(voice_channel_id)
            if not vc or not isinstance(vc, discord.VoiceChannel):
                await self._db_remove_247(guild_id)
                continue

            perms = vc.permissions_for(guild.me)
            if not perms.connect or not perms.speak:
                print(f"[Music] Missing perms to rejoin VC in guild {guild_id}, skipping.")
                continue

            try:
                player = self.lavalink.player_manager.create(guild_id, region=MAIN_NODE_REGION)
                player.store("channel", text_channel_id)
                if not guild.voice_client:

                    try:
                        await guild.change_voice_state(channel=None)
                        await asyncio.sleep(1)
                    except Exception:
                        pass
                    await vc.connect(
                        cls=LavalinkVoiceClient,
                        self_deaf=True,
                        timeout=15.0,
                        reconnect=True,
                    )
                self.mode_247[guild_id] = True
                print(f"[Music] Auto-reconnected to VC in guild {guild_id} (24/7 mode)")
            except Exception as e:
                print(f"[Music] Failed to auto-reconnect in guild {guild_id}: {e}")

    async def _init_lavalink(self):
        await self._init_db()
        await self.bot.wait_until_ready()

        if not hasattr(self.bot, "lavalink") or self.bot.lavalink is None:
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            print(f"[Music] Lavalink client created for bot ID {self.bot.user.id}")

        self.lavalink = self.bot.lavalink

        try:
            for k in list(self.lavalink._event_hooks.keys()):
                self.lavalink._event_hooks[k] = [
                    h for h in self.lavalink._event_hooks[k]
                    if not isinstance(getattr(h, "__self__", None), Music)
                ]
        except Exception:
            pass

        self.lavalink.add_event_hooks(self)

        for node in LAVALINK_NODES:
            try:
                existing = [
                    n for n in self.lavalink.node_manager.nodes
                    if n.name == node["name"]
                ]
                if existing:
                    print(f"[Music] Node '{node['name']}' already exists, skipping.")
                    continue

                node_kwargs = dict(
                    host     = node["host"],
                    port     = node["port"],
                    password = node["password"],
                    region   = node["region"],
                    name     = node["name"],
                    ssl      = node.get("ssl", False),
                )

                try:
                    params = inspect.signature(self.lavalink.add_node).parameters
                    if "reconnect_attempts" in params:
                        node_kwargs["reconnect_attempts"] = 5
                except (TypeError, ValueError):
                    pass
                self.lavalink.add_node(**node_kwargs)
                print(f"[Music] Added node '{node['name']}' ({node['host']}:{node['port']})")
            except Exception as e:
                print(f"[Music] Failed to add node '{node['name']}': {e}")

        print("[Music] Waiting for Lavalink node to connect...")
        for attempt in range(60):
            if self.lavalink.node_manager.available_nodes:
                self._node_ready.set()
                print(f"[Music] Node connected after {attempt + 1}s!")
                await self._restore_247()
                return
            await asyncio.sleep(1)

        print("[Music] WARNING: No Lavalink nodes connected after 60s!")
        self._was_all_down = True
        print("[Music] Check: host/port/password/ssl settings, firewall, node server running")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after : discord.VoiceState,
    ):
        if member.id != self.bot.user.id:
            return
        if before.channel and not after.channel:
            guild_id = member.guild.id
            if self.lavalink:
                player = self.lavalink.player_manager.get(guild_id)
                if player:
                    player.channel_id = None
            self.mode_247.pop(guild_id, None)
            self.bot.loop.create_task(self._db_remove_247(guild_id))

    @lavalink.listener(lavalink.events.NodeConnectedEvent)
    async def on_node_connected(self, event):
        self._node_ready.set()
        self._node_down_until = 0.0
        print(f"[Music] Node '{event.node.name}' connected!")

        if self._was_all_down:
            self._was_all_down = False
            self.bot.loop.create_task(self._restore_247())

    @lavalink.listener(lavalink.events.NodeDisconnectedEvent)
    async def on_node_disconnected(self, event):
        dead_node = event.node
        print(f"[Music] Node '{dead_node.name}' disconnected!")

        still_up = self.lavalink.node_manager.available_nodes
        if not still_up:
            self._node_ready.clear()
            self._was_all_down = True
            print("[Music] WARNING: all Lavalink nodes are offline!")
            return

        print(f"[Music] {len(still_up)} node(s) still online — migrating affected players.")

        for player in list(self.lavalink.player_manager.players.values()):
            if player.node != dead_node:
                continue
            new_node = self.lavalink.node_manager.find_ideal_node()
            if not new_node:
                continue
            try:
                await player.change_node(new_node)
                print(f"[Music] Migrated guild {player.guild_id} -> node '{new_node.name}'")
                await asyncio.sleep(MIGRATE_STAGGER)
            except Exception as e:
                print(f"[Music] Failed to migrate guild {player.guild_id}: {e}")

    @lavalink.listener(lavalink.events.TrackStartEvent)
    async def on_track_start(self, event: lavalink.events.TrackStartEvent):
        player   = event.player
        guild_id = int(player.guild_id)
        track    = event.track

        if self._last_announced.get(guild_id) == track.identifier:
            await self._update_now_playing(guild_id)
            await self._update_vc_status(guild_id, track)
            return

        self._last_announced[guild_id] = track.identifier

        hist = self.history.setdefault(guild_id, [])
        hist.append(track)
        if len(hist) > 20:
            hist.pop(0)

        recent = self.recent_tracks.setdefault(guild_id, [])
        recent.append(track.identifier)
        if len(recent) > 5:
            recent.pop(0)

        await self._send_now_playing(guild_id, player)
        await self._update_vc_status(guild_id, track)

    @lavalink.listener(lavalink.events.TrackEndEvent)
    async def on_track_end(self, event: lavalink.events.TrackEndEvent):
        self._last_announced.pop(int(event.player.guild_id), None)

    @lavalink.listener(lavalink.events.TrackExceptionEvent)
    async def on_track_exception(self, event: lavalink.events.TrackExceptionEvent):

        reason = getattr(event, "cause", None) or "unknown playback error"
        print(f"[Music] Track exception in {event.player.guild_id}: {reason}")
        await self._handle_track_failure(event.player, event.track, str(reason))

    @lavalink.listener(lavalink.events.TrackStuckEvent)
    async def on_track_stuck(self, event: lavalink.events.TrackStuckEvent):
        print(f"[Music] Track stuck in {event.player.guild_id}, retrying...")
        await self._handle_track_failure(event.player, event.track, "track got stuck")

    async def _handle_track_failure(self, player, track, reason: str):
        """
        A track started but failed (node error / stuck / that node's source
        plugin couldn't actually stream it). Instead of just letting the
        queue end here, try the same song again — on another source, on
        another node — before giving up on it.
        """
        guild_id  = int(player.guild_id)
        retry_key = f"{track.title}|{track.author}".lower()
        retries   = self._track_retry_counts.setdefault(guild_id, {})

        if retries.get(retry_key, 0) >= 2:
            retries.pop(retry_key, None)
            channel_id = player.fetch("channel")
            guild      = self.bot.get_guild(guild_id)
            if guild and channel_id:
                ch = guild.get_channel(channel_id)
                if ch:
                    v = LayoutView(timeout=None)
                    v.add_item(build_denied_container(
                        f"Couldn't play **{track.title}** on any source/node "
                        f"(`{reason}`) — skipping."
                    ))
                    try:
                        await ch.send(view=v)
                    except Exception:
                        pass
            await player.skip()
            return

        retries[retry_key] = retries.get(retry_key, 0) + 1

        term = f"{track.title} {track.author}".strip()
        res  = await self._resilient_get_tracks(f"ytsearch:{term}")
        if not res or not res.tracks:
            retries.pop(retry_key, None)
            await player.skip()
            return

        replacement = res.tracks[0]
        player.add(requester=track.requester, track=replacement)

        player.queue.insert(0, player.queue.pop())
        if not player.is_playing:
            await player.play()

    @lavalink.listener(lavalink.events.QueueEndEvent)
    async def on_queue_end(self, event: lavalink.events.QueueEndEvent):
        player   = event.player
        guild_id = int(player.guild_id)
        self._last_announced.pop(guild_id, None)

        if self.autoplay_states.get(guild_id, False):
            if await self._try_autoplay(guild_id, player):
                return

        if self.mode_247.get(guild_id, False):
            await self._clear_vc_status(guild_id)
            msg = self.now_playing_messages.pop(guild_id, None)
            if msg:
                try:
                    v = LayoutView(timeout=None)
                    v.add_item(build_simple_container(
                        f"{E('CHECK')} Queue ended — staying in VC (24/7 mode).",
                        footer="Use play command to start again",
                    ))
                    await msg.edit(view=v)
                except discord.HTTPException:
                    pass
            return

        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass

        await self._clear_vc_status(guild_id)

        msg = self.now_playing_messages.pop(guild_id, None)
        if msg:
            try:
                v = LayoutView(timeout=None)
                v.add_item(build_simple_container(
                    f"{E('CHECK')} Queue ended — disconnected.",
                    footer="Thanks for listening!",
                ))
                await msg.edit(view=v)
            except discord.HTTPException:
                pass

    async def _resilient_get_tracks(self, search: str):
        """
        Resolve `search` into a lavalink LoadResult, working around a node
        that errors, is missing the relevant plugin, or has no results.

        - Direct links (a URL) are retried across every available node,
          since only the node itself changes what can resolve a link.
        - Plain search queries (e.g. "ytsearch:believer") are first retried
          across every node with the SAME source: if nothing comes back,
          the bare term is retried under every other known source prefix
          across every node too — so "&play <song>" still finds something
          even if the node it lands on can't search YouTube.

        Returns the first non-empty, non-error LoadResult, or None if
        nothing worked anywhere.
        """
        now   = time.monotonic()
        nodes = [
            n for n in self.lavalink.node_manager.available_nodes
            if self._node_cooldowns.get(n.name, 0.0) <= now
        ]
        if not nodes:
            nodes = list(self.lavalink.node_manager.available_nodes)
        if not nodes:
            return None
        nodes.sort(key=lambda n: 0 if n.name == MAIN_NODE_NAME else 1)

        is_direct_link = bool(URL_REGEX.match(search)) and not search.startswith(KNOWN_SEARCH_PREFIXES)

        if is_direct_link:
            candidates = [search]
        else:
            used_prefix = next((p for p in KNOWN_SEARCH_PREFIXES if search.startswith(p)), "ytsearch:")
            bare_term   = search[len(used_prefix):] if search.startswith(used_prefix) else search
            candidates  = [f"{used_prefix}{bare_term}"] + [
                f"{p}{bare_term}" for p in KNOWN_SEARCH_PREFIXES if p != used_prefix
            ]

        for candidate in candidates:
            for node in nodes:
                try:
                    res = await node.get_tracks(candidate)
                except Exception as e:
                    print(f"[Search] '{node.name}' errored on '{candidate}': {e}")
                    text = str(e).lower()
                    if "429" in text or "rate limit" in text or "ratelimit" in text:
                        self._node_cooldowns[node.name] = time.monotonic() + NODE_RATE_COOLDOWN
                        print(f"[Search] '{node.name}' rate limited, skipping it for {int(NODE_RATE_COOLDOWN)}s.")
                    continue
                if res and res.tracks and res.load_type != lavalink.LoadType.ERROR:
                    return res

        return None

    async def _try_autoplay(self, guild_id: int, player) -> bool:
        recent = self.recent_tracks.get(guild_id, [])
        if not recent:
            return False
        seed = recent[-1]
        try:
            mix = f"https://www.youtube.com/watch?v={seed}&list=RD{seed}"
            res = await self._resilient_get_tracks(mix)
            if not res or not res.tracks:
                return False
            added = 0
            for t in res.tracks:
                if t.identifier in recent:
                    continue
                player.add(requester=self.bot.user.id, track=t)
                added += 1
                if added >= 5:
                    break
            if added > 0 and not player.is_playing:
                await player.play()
            return added > 0
        except Exception as e:
            print(f"[Autoplay] Error: {e}")
            return False

    async def _update_vc_status(self, guild_id: int, track):
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        ch = guild.voice_client.channel
        if not ch:
            return
        status = f"{_EMGR['MYMUSIC']} {track.title[:450]}"
        try:
            await self.bot.http.request(
                discord.http.Route(
                    "PUT", "/channels/{channel_id}/voice-status",
                    channel_id=ch.id,
                ),
                json={"status": status},
            )
        except Exception as e:
            print(f"[VC Status] {e}")

    async def _clear_vc_status(self, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        for vc in guild.voice_channels:
            try:
                await self.bot.http.request(
                    discord.http.Route(
                        "PUT", "/channels/{channel_id}/voice-status",
                        channel_id=vc.id,
                    ),
                    json={"status": ""},
                )
            except Exception:
                pass

    def _get_thumbnail(self, track) -> str:
        if not track:
            return self.bot.user.display_avatar.url
        try:

            artwork = getattr(track, "artwork_url", None)
            if artwork:
                return artwork
            if getattr(track, "source_name", None) == "youtube":
                return f"https://img.youtube.com/vi/{track.identifier}/maxresdefault.jpg"
            return self.bot.user.display_avatar.url
        except Exception:
            return self.bot.user.display_avatar.url

    async def _send_now_playing(self, guild_id: int, player):
        channel_id = player.fetch("channel")
        guild      = self.bot.get_guild(guild_id)
        if not guild or not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        view = MusicControlView(self, guild_id).build(player)

        old = self.now_playing_messages.get(guild_id)
        if old:
            try:
                await old.delete()
            except discord.HTTPException:
                pass

        try:
            msg = await channel.send(view=view)
            self.now_playing_messages[guild_id] = msg
        except discord.HTTPException as e:
            print(f"[Now Playing] Send failed: {e}")

    async def _update_now_playing(self, guild_id: int):
        player = self.lavalink.player_manager.get(guild_id)
        msg    = self.now_playing_messages.get(guild_id)
        if not player or not msg:
            return
        view = MusicControlView(self, guild_id).build(player)
        try:
            await msg.edit(view=view)
        except discord.HTTPException:
            pass

    async def _check_voice(self, ctx_or_inter) -> bool:
        if isinstance(ctx_or_inter, discord.Interaction):
            user    = ctx_or_inter.user
            guild   = ctx_or_inter.guild
            respond = lambda v: ctx_or_inter.response.send_message(view=v, ephemeral=True)
        else:
            user    = ctx_or_inter.author
            guild   = ctx_or_inter.guild
            respond = lambda v: ctx_or_inter.send(view=v)

        if not user.voice or not user.voice.channel:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("You must be in a voice channel."))
            await respond(v)
            return False

        if guild.voice_client and guild.voice_client.channel != user.voice.channel:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("You must be in the same VC as me."))
            await respond(v)
            return False

        return True

    async def _wait_for_node(self, ctx) -> bool:
        """
        True once at least one Lavalink node is ready. If the pool is down we
        send a single clean notice, and for the next NODE_DOWN_FAST_FAIL
        seconds further commands fail instantly (no waiting, no extra
        messages) so spamming a command can't hammer the Discord API.
        """
        if self._node_ready.is_set():
            return True

        if time.monotonic() < self._node_down_until:
            v = LayoutView(timeout=None)
            v.add_item(build_unavailable_container())
            await ctx.send(view=v)
            return False

        v = LayoutView(timeout=None)
        v.add_item(build_connecting_container())
        wait_msg = await ctx.send(view=v)
        try:
            await asyncio.wait_for(self._node_ready.wait(), timeout=20)
        except asyncio.TimeoutError:
            self._node_down_until = time.monotonic() + NODE_DOWN_FAST_FAIL
            v = LayoutView(timeout=None)
            v.add_item(build_unavailable_container())
            try:
                await wait_msg.edit(view=v)
            except discord.HTTPException:
                pass
            return False
        try:
            await wait_msg.delete()
        except Exception:
            pass
        return True

    async def _ensure_voice(self, ctx) -> bool:
        if not await self._wait_for_node(ctx):
            return False

        if not ctx.author.voice or not ctx.author.voice.channel:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("You need to join a voice channel first."))
            await ctx.send(view=v)
            return False

        vc     = ctx.author.voice.channel
        player = self.lavalink.player_manager.create(ctx.guild.id, region=MAIN_NODE_REGION)

        if not ctx.guild.voice_client:
            perms = vc.permissions_for(ctx.guild.me)
            if not perms.connect or not perms.speak:
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container(
                    "I need **Connect** and **Speak** permissions in that channel."
                ))
                await ctx.send(view=v)
                return False

            player.store("channel", ctx.channel.id)

            try:
                await vc.connect(cls=LavalinkVoiceClient, self_deaf=True)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[Connect] Error: {e}")
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container(f"Failed to connect to VC: `{e}`"))
                await ctx.send(view=v)
                return False
        else:
            if ctx.guild.voice_client.channel != vc:
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container("You must be in my voice channel."))
                await ctx.send(view=v)
                return False

        return True

    @commands.hybrid_command(name="join", aliases=["j", "connect"], description="Join your current voice channel.")
    @commands.guild_only()
    async def join_cmd(self, ctx):
        if not await self._wait_for_node(ctx):
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("You need to join a voice channel first."))
            return await ctx.send(view=v)

        vc = ctx.author.voice.channel

        if ctx.guild.voice_client:
            if ctx.guild.voice_client.channel == vc:
                v = LayoutView(timeout=None)
                v.add_item(build_simple_container(
                    f"{E('CHECK')} Already connected to {vc.mention}."
                ))
                return await ctx.send(view=v)

            v = LayoutView(timeout=None)
            v.add_item(build_denied_container(
                "I'm already connected to another voice channel."
            ))
            return await ctx.send(view=v)

        perms = vc.permissions_for(ctx.guild.me)
        if not perms.connect or not perms.speak:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container(
                "I need **Connect** and **Speak** permissions in that channel."
            ))
            return await ctx.send(view=v)

        player = self.lavalink.player_manager.create(ctx.guild.id, region=MAIN_NODE_REGION)
        player.store("channel", ctx.channel.id)

        try:
            await vc.connect(cls=LavalinkVoiceClient, self_deaf=True)
        except Exception as e:
            print(f"[Join] Error: {e}")
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container(f"Failed to connect to VC: `{e}`"))
            return await ctx.send(view=v)

        v = LayoutView(timeout=None)
        v.add_item(build_enabled_container(
            "Joined Voice Channel",
            f"Connected to {vc.mention}. I'll stay here until `stop`/`dc` is used "
            f"or I'm disconnected — enable `{ctx.prefix}247` too if you also want "
            f"me to auto-reconnect here after a restart.",
        ))
        await ctx.send(view=v)

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song or add it to the queue.")
    @commands.guild_only()
    @app_commands.describe(query="A song name, or a YouTube/Spotify/Apple Music/Deezer/SoundCloud link.")
    async def play(self, ctx, *, query: str = None):
        if not query:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container(
                f"Provide a song name or a link.\n"
                f"Usage: `{ctx.prefix}play <song / url>` — prefix a search with "
                f"`spotify:`, `deezer:`, `apple:` or `sc:` to search that platform "
                f"instead of YouTube."
            ))
            return await ctx.send(view=v)

        if not await self._ensure_voice(ctx):
            return

        player = self.lavalink.player_manager.get(ctx.guild.id)
        player.store("channel", ctx.channel.id)

        if not URL_REGEX.match(query):
            lowered   = query.lower()
            alias_key = next((k for k in SOURCE_ALIASES if lowered.startswith(k)), None)
            if alias_key:
                term   = query[len(alias_key):].strip()
                search = f"{SOURCE_ALIASES[alias_key]}{term}"
            else:
                search = f"ytsearch:{query}"
        else:
            if not any(p.match(query) for p in SUPPORTED_URL_PATTERNS):
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container(
                    "Unsupported link. I can play YouTube, Spotify, Apple Music, "
                    "Deezer and SoundCloud links, or a plain search."
                ))
                return await ctx.send(view=v)
            search = query

        loading = LayoutView(timeout=None)
        loading.add_item(build_simple_container(
            f"{E('LOADING')} Searching for **{query}**…"
        ))
        loading_msg = await ctx.send(view=loading)

        results = await self._resilient_get_tracks(search)

        if not results or not results.tracks:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container(
                f"No results found for **{query}** on any connected node/source."
            ))
            return await loading_msg.edit(view=v)

        if results.load_type == lavalink.LoadType.PLAYLIST:
            for t in results.tracks:
                player.add(requester=ctx.author.id, track=t)

            v = LayoutView(timeout=None)
            v.add_item(Container(
                TextDisplay(
                    f"### {E('QUEUE')} Playlist Added\n\n"
                    f"Added **{len(results.tracks)}** tracks from "
                    f"**{results.playlist_info.name}**\n"
                    f"**Requested by** {ctx.author.mention}"
                ),
                accent_color=ACCENT_COLOR,
            ))
            await loading_msg.edit(view=v)

        else:
            track = results.tracks[0]
            player.add(requester=ctx.author.id, track=track)

            if player.is_playing:
                view = AddedToQueueView(self, ctx.guild.id, track, ctx.author)
                await loading_msg.edit(view=view)
            else:
                try:
                    await loading_msg.delete()
                except discord.HTTPException:
                    pass

        if not player.is_playing:
            try:
                await player.play()
            except Exception as e:
                print(f"[Play] {e}")
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container(f"Playback failed: `{e}`"))
                await ctx.send(view=v)

    @commands.hybrid_command(name="skip", aliases=["s", "next"], description="Skip the current track.")
    @commands.guild_only()
    async def skip(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or not player.is_playing:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Nothing is playing."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        await player.skip()
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('SKIP')} Track skipped."))
        await ctx.send(view=v)

    @commands.hybrid_command(name="stop", aliases=["dc", "disconnect"], description="Stop playback and leave the voice channel.")
    @commands.guild_only()
    async def stop(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Not connected."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return

        self.mode_247[ctx.guild.id] = False
        await self._db_remove_247(ctx.guild.id)
        self._last_announced.pop(ctx.guild.id, None)
        player.queue.clear()
        await player.stop()

        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)

        await self._clear_vc_status(ctx.guild.id)

        msg = self.now_playing_messages.pop(ctx.guild.id, None)
        if msg:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass

        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('STOP')} Stopped and disconnected."))
        await ctx.send(view=v)

    @commands.hybrid_command(name="pause", description="Pause the current track.")
    @commands.guild_only()
    async def pause(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or not player.is_playing:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Nothing is playing."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        await player.set_pause(True)
        await self._update_now_playing(ctx.guild.id)
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('PAUSE')} Paused."))
        await ctx.send(view=v)

    @commands.hybrid_command(name="resume", aliases=["unpause"], description="Resume the paused track.")
    @commands.guild_only()
    async def resume(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Nothing to resume."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        await player.set_pause(False)
        await self._update_now_playing(ctx.guild.id)
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('PLAY')} Resumed."))
        await ctx.send(view=v)

    @commands.hybrid_command(name="volume", aliases=["vol"], description="Set or view the playback volume.")
    @commands.guild_only()
    @app_commands.describe(vol="Volume percentage (0-100).")
    async def volume(self, ctx, vol: int = None):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Not connected."))
            return await ctx.send(view=v)
        if vol is None:
            v = LayoutView(timeout=None)
            v.add_item(build_simple_container(
                f"{E('VOLUME')} Current volume: **{player.volume}%**"
            ))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        vol = max(0, min(150, vol))
        await player.set_volume(vol)
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('VOLUME')} Volume set to **{vol}%**"))
        await ctx.send(view=v)

    @commands.hybrid_command(name="loop", aliases=["repeat"], description="Toggle loop mode for the current track.")
    @commands.guild_only()
    async def loop(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or not player.is_playing:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Nothing is playing."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        player.set_loop(0 if player.loop else 1)
        await self._update_now_playing(ctx.guild.id)
        state = "enabled" if player.loop else "disabled"
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('LOOP')} Loop **{state}**."))
        await ctx.send(view=v)

    @commands.hybrid_command(name="shuffle", description="Shuffle the current queue.")
    @commands.guild_only()
    async def shuffle(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or not player.queue:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Queue is empty."))
            return await ctx.send(view=v)
        if not await self._check_voice(ctx):
            return
        random.shuffle(player.queue)
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('SHUFFLE')} Queue shuffled!"))
        await ctx.send(view=v)

    @commands.hybrid_command(name="queue", aliases=["q"], description="Show the current music queue.")
    @commands.guild_only()
    async def queue_cmd(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or (not player.queue and not player.current):
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Queue is empty."))
            return await ctx.send(view=v)
        view = QueueView(self, ctx.guild.id).build(player)
        await ctx.send(view=view)

    @commands.hybrid_command(name="nowplaying", aliases=["nplay", "nowp"], description="Show the currently playing track.")
    @commands.guild_only()
    async def nowplaying(self, ctx):
        player = self.lavalink.player_manager.get(ctx.guild.id) if self.lavalink else None
        if not player or not player.current:
            v = LayoutView(timeout=None)
            v.add_item(build_denied_container("Nothing is playing."))
            return await ctx.send(view=v)
        view = MusicControlView(self, ctx.guild.id).build(player)
        msg  = await ctx.send(view=view)
        self.now_playing_messages[ctx.guild.id] = msg

    @commands.hybrid_command(name="247", aliases=["24/7", "stay"], description="Toggle 24/7 mode (bot stays connected).")
    @commands.guild_only()
    async def mode_247_cmd(self, ctx):
        current = self.mode_247.get(ctx.guild.id, False)

        if not current:
            vc = None
            if ctx.guild.voice_client:
                vc = ctx.guild.voice_client.channel
            elif ctx.author.voice and ctx.author.voice.channel:
                vc = ctx.author.voice.channel

            if not vc:
                v = LayoutView(timeout=None)
                v.add_item(build_denied_container(
                    "Join a voice channel first (or use the join command)."
                ))
                return await ctx.send(view=v)

            if not ctx.guild.voice_client:
                perms = vc.permissions_for(ctx.guild.me)
                if not perms.connect or not perms.speak:
                    v = LayoutView(timeout=None)
                    v.add_item(build_denied_container(
                        "I need **Connect** and **Speak** permissions in that channel."
                    ))
                    return await ctx.send(view=v)

                player = self.lavalink.player_manager.create(ctx.guild.id, region=MAIN_NODE_REGION)
                player.store("channel", ctx.channel.id)

                try:
                    await vc.connect(cls=LavalinkVoiceClient, self_deaf=True)
                except Exception as e:
                    print(f"[247] Connect error: {e}")
                    v = LayoutView(timeout=None)
                    v.add_item(build_denied_container(f"Failed to connect to VC: `{e}`"))
                    return await ctx.send(view=v)

            self.mode_247[ctx.guild.id] = True
            await self._db_set_247(ctx.guild.id, vc.id, ctx.channel.id)

            v = LayoutView(timeout=None)
            v.add_item(build_enabled_container(
                "24/7 Mode",
                f"Bot will stay in {vc.mention} even when the queue ends, "
                f"and will auto-reconnect here after a restart.",
            ))
        else:
            self.mode_247[ctx.guild.id] = False
            await self._db_remove_247(ctx.guild.id)

            v = LayoutView(timeout=None)
            v.add_item(Container(
                TextDisplay(
                    f"### {E('CROSS')} 24/7 Mode\n"
                    f"{E('ARROW')} 24/7 mode disabled."
                ),
                accent_color=ACCENT_COLOR,
            ))

        await ctx.send(view=v)

    @commands.hybrid_command(name="autoplay", aliases=["ap"], description="Toggle autoplay of related tracks.")
    @commands.guild_only()
    async def autoplay_cmd(self, ctx):
        current = self.autoplay_states.get(ctx.guild.id, False)
        self.autoplay_states[ctx.guild.id] = not current
        v = LayoutView(timeout=None)
        if not current:
            v.add_item(build_enabled_container(
                "Autoplay", "Similar tracks will auto-add when queue ends."
            ))
        else:
            v.add_item(Container(
                TextDisplay(
                    f"### {E('CROSS')} Autoplay\n"
                    f"{E('ARROW')} Autoplay disabled."
                ),
                accent_color=ACCENT_COLOR,
            ))
        await ctx.send(view=v)
        await self._update_now_playing(ctx.guild.id)

    async def btn_playpause(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player:
            return await interaction.response.defer()
        await player.set_pause(not player.paused)
        view = MusicControlView(self, interaction.guild.id).build(player)
        await interaction.response.edit_message(view=view)
        self.now_playing_messages[interaction.guild.id] = interaction.message

    async def btn_skip(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player or not player.is_playing:
            return await interaction.response.defer()
        await player.skip()
        await interaction.response.defer()

    async def btn_previous(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player:
            return await interaction.response.defer()
        history = self.history.get(interaction.guild.id, [])
        if player.current and player.position > 5000:
            await player.seek(0)
            return await interaction.response.defer()
        if len(history) < 2:
            if player.current:
                await player.seek(0)
            return await interaction.response.defer()
        current = history.pop()
        previous = history.pop()
        if current:
            player.queue.insert(0, current)
        self._last_announced.pop(interaction.guild.id, None)
        await interaction.response.defer()
        await player.play(track=previous)

    async def btn_rewind(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if player and player.current:
            await player.seek(max(player.position - 10000, 0))
        await interaction.response.defer()

    async def btn_forward(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if player and player.current and not player.current.stream:
            await player.seek(min(player.position + 10000, max(player.current.duration - 1000, 0)))
        await interaction.response.defer()

    async def btn_heart(self, interaction: discord.Interaction):
        player = self.lavalink.player_manager.get(interaction.guild.id)
        track = player.current if player else None
        if not track:
            return await interaction.response.defer()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO liked (user_id, uri, title, author, duration) VALUES (?, ?, ?, ?, ?)",
                (interaction.user.id, track.uri, track.title, track.author, track.duration),
            )
            await db.commit()
        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(f"{E('HEART')} Added **{track.title[:100]}** to your liked songs."))
        await interaction.response.send_message(view=v, ephemeral=True)

    async def btn_stop(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player:
            return await interaction.response.defer()

        self.mode_247[interaction.guild.id] = False
        await self._db_remove_247(interaction.guild.id)
        self._last_announced.pop(interaction.guild.id, None)
        player.queue.clear()
        await player.stop()

        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)

        await self._clear_vc_status(interaction.guild.id)
        self.now_playing_messages.pop(interaction.guild.id, None)

        v = LayoutView(timeout=None)
        v.add_item(build_simple_container(
            f"{E('STOP')} Stopped and disconnected.",
            footer="Thanks for listening!",
        ))
        await interaction.response.edit_message(view=v)

    async def btn_loop(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player:
            return await interaction.response.defer()
        player.set_loop(0 if player.loop else 1)
        view = MusicControlView(self, interaction.guild.id).build(player)
        await interaction.response.edit_message(view=view)

    async def btn_shuffle(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        player = self.lavalink.player_manager.get(interaction.guild.id)
        if not player or not player.queue:
            return await interaction.response.defer()
        random.shuffle(player.queue)
        await interaction.response.defer()

    async def btn_autoplay(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return
        current = self.autoplay_states.get(interaction.guild.id, False)
        self.autoplay_states[interaction.guild.id] = not current
        player = self.lavalink.player_manager.get(interaction.guild.id)
        view   = MusicControlView(self, interaction.guild.id).build(player)
        await interaction.response.edit_message(view=view)

async def setup(bot):
    await bot.add_cog(Music(bot))

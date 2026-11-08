from __future__ import annotations

import asyncio
import difflib
import re
import sys
import time
from collections import defaultdict, deque
from datetime import timedelta, timezone, datetime
from pathlib import Path

import discord
from discord.ext import commands
from utils.config import OWNER_IDS
from discord.ui import (
    LayoutView, Container, Section, TextDisplay, Separator,
    Thumbnail, ActionRow, Button, Select
)
import aiosqlite

sys.path.insert(0, str(Path(__file__).parent.parent))


ACCENT_COLOR = 0x000000

DB_PATH = "db/automod.db"


from XEON.emojis import E as _EMGR

_KEY_MAP = {
    "CHECK": "SUCCESS", "CROSS": "ERROR", "ENABLED": "ENABLED",
    "DISABLED": "DISABLED", "GEARS": "LOADING", "INFO": "INFO",
    "SHIELD": "AUTOMOD", "ARROW": "ARROW", "WARN": "WARNING",
    "LOCK": "LOCK", "CONFIG": "ARROW", "BAT": "ARROW",
    "TIMER": "ARROW", "MUTE": "MUTE", "TRASH": "TRASH",
}

def E(key: str) -> str:
    return _EMGR[_KEY_MAP.get(key, key)]


ALL_FILTERS = [
    "Anti Spam",
    "Anti Caps",
    "Anti Link",
    "Anti Invites",
    "Anti Mass Mention",
    "Anti Emoji Spam",
    "Anti NSFW Link",
    "Anti Attachment Spam",
    "Anti Zalgo Spam",
    "Similar Message Spam",
    "Character Limit Spam",
    "New Line Spam",
    "Blacklist Word",
]

FILTER_DESCRIPTIONS = {
    "Anti Spam":            "Detects rapid messages from a user.",
    "Anti Caps":            "Detects messages with excessive capital letters.",
    "Anti Link":            "Detects unauthorized links.",
    "Anti Invites":         "Detects Discord server invites.",
    "Anti Mass Mention":    "Detects messages with too many mentions.",
    "Anti Emoji Spam":      "Detects messages with too many emojis.",
    "Anti NSFW Link":       "Detects NSFW links and keywords.",
    "Anti Attachment Spam": "Detects messages with too many attachments.",
    "Anti Zalgo Spam":      "Detects messages with excessive Zalgo text.",
    "Similar Message Spam": "Detects users sending very similar messages.",
    "Character Limit Spam": "Detects messages that exceed a character limit.",
    "New Line Spam":        "Detects messages with excessive blank lines.",
    "Blacklist Word":       "Detects messages containing blacklisted words.",
}

DEFAULT_HEAT = {
    "Anti Spam":            15,
    "Anti Caps":            50,
    "Anti Link":            100,
    "Anti Invites":         100,
    "Anti Mass Mention":    100,
    "Anti Emoji Spam":      50,
    "Anti NSFW Link":       100,
    "Anti Attachment Spam": 50,
    "Anti Zalgo Spam":      100,
    "Similar Message Spam": 35,
    "Character Limit Spam": 100,
    "New Line Spam":        50,
    "Blacklist Word":       100,
}

HEAT_LIMIT = 100.0
HEAT_DECAY = 5.0
CONFIG_TTL = 5.0

RULES_TEXT = {
    "Anti Spam":            "Rapid messages build heat; punished at 100 heat and the burst is deleted.\nPunishment: Auto Mute",
    "Anti Caps":            "Triggers if >70% of message is capital letters (min 45 chars).\nPunishment: Auto Mute",
    "Anti Link":            "Triggers if message contains an unauthorized link.\nPunishment: Auto Mute",
    "Anti Invites":         "Triggers if message contains a Discord server invite.\nPunishment: Auto Mute",
    "Anti Mass Mention":    "Triggers if message contains 5+ mentions.\nPunishment: Auto Mute",
    "Anti Emoji Spam":      "Triggers if message contains more than 5 emojis.\nPunishment: Auto Mute",
    "Anti NSFW Link":       "Blocks messages with NSFW keywords.\nPunishment: Delete (fixed)",
    "Anti Attachment Spam": "Triggers if message has too many attachments.\nPunishment: Auto Mute",
    "Anti Zalgo Spam":      "Deletes messages with excessive Zalgo text.\nPunishment: Delete",
    "Similar Message Spam": "Triggers if a user sends near-identical messages.\nPunishment: Auto Mute",
    "Character Limit Spam": "Triggers if message exceeds the character limit.\nPunishment: Auto Mute",
    "New Line Spam":        "Deletes messages with excessive blank lines.\nPunishment: Delete",
    "Blacklist Word":       "Deletes messages with blacklisted words.\nPunishment: Auto Mute",
}

PUNISHMENT_TYPES = ["Auto Mute", "Kick", "Ban", "Delete"]

_MUTE_DURATIONS = {
    "Anti Spam":            12,
    "Anti Caps":            1,
    "Anti Link":            7,
    "Anti Invites":         12,
    "Anti Mass Mention":    3,
    "Anti Emoji Spam":      1,
    "Anti Attachment Spam": 5,
    "Anti Zalgo Spam":      0,
    "Similar Message Spam": 5,
    "Character Limit Spam": 2,
    "New Line Spam":        0,
    "Blacklist Word":       5,
}

FILTERS_ROW1 = ALL_FILTERS[:7]
FILTERS_ROW2 = ALL_FILTERS[7:]


async def init_db():
    Path("db").mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS automod (
                guild_id INTEGER PRIMARY KEY,
                enabled  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS automod_filters (
                guild_id   INTEGER,
                filter     TEXT,
                enabled    INTEGER DEFAULT 0,
                punishment TEXT DEFAULT 'Auto Mute',
                heat       REAL DEFAULT 15,
                PRIMARY KEY (guild_id, filter)
            );
            CREATE TABLE IF NOT EXISTS automod_ignored (
                guild_id INTEGER,
                type     TEXT,
                id       INTEGER,
                PRIMARY KEY (guild_id, type, id)
            );
            CREATE TABLE IF NOT EXISTS automod_logging (
                guild_id    INTEGER PRIMARY KEY,
                log_channel INTEGER
            );
            CREATE TABLE IF NOT EXISTS automod_blacklist (
                guild_id INTEGER,
                word     TEXT,
                PRIMARY KEY (guild_id, word)
            );
        """)
        await db.commit()


async def is_enabled(guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT enabled FROM automod WHERE guild_id=?", (guild_id,)) as c:
            r = await c.fetchone()
            return r is not None and r[0] == 1


async def get_filter_row(guild_id: int, filter_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT enabled, punishment, heat FROM automod_filters WHERE guild_id=? AND filter=?",
            (guild_id, filter_name)
        ) as c:
            return await c.fetchone()


async def filter_enabled(guild_id: int, filter_name: str) -> bool:
    row = await get_filter_row(guild_id, filter_name)
    return row is not None and row[0] == 1


async def get_all_filter_data(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT filter, enabled, punishment, heat FROM automod_filters WHERE guild_id=?",
            (guild_id,)
        ) as c:
            rows = await c.fetchall()
    existing = {r[0]: {"enabled": bool(r[1]), "punishment": r[2], "heat": r[3]} for r in rows}
    result = {}
    for f in ALL_FILTERS:
        result[f] = existing.get(f, {
            "enabled": False,
            "punishment": "Auto Mute",
            "heat": DEFAULT_HEAT.get(f, 15),
        })
    return result


async def set_filter(guild_id: int, filter_name: str, enabled: bool = None,
                     punishment: str = None, heat: float = None):
    async with aiosqlite.connect(DB_PATH) as db:
        row = await get_filter_row(guild_id, filter_name)
        if row is None:
            cur_enabled    = bool(enabled) if enabled is not None else False
            cur_punishment = punishment or "Auto Mute"
            cur_heat       = heat if heat is not None else DEFAULT_HEAT.get(filter_name, 15)
        else:
            cur_enabled    = enabled    if enabled is not None    else bool(row[0])
            cur_punishment = punishment if punishment is not None else row[1]
            cur_heat       = heat       if heat is not None       else row[2]

        await db.execute(
            "INSERT OR REPLACE INTO automod_filters (guild_id, filter, enabled, punishment, heat) "
            "VALUES (?,?,?,?,?)",
            (guild_id, filter_name, int(cur_enabled), cur_punishment, cur_heat)
        )
        await db.commit()
    invalidate_config(guild_id)


async def get_ignored(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT type, id FROM automod_ignored WHERE guild_id=?", (guild_id,)
        ) as c:
            rows = await c.fetchall()
    channels = {r[1] for r in rows if r[0] == "channel"}
    roles    = {r[1] for r in rows if r[0] == "role"}
    return channels, roles


async def get_log_channel(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT log_channel FROM automod_logging WHERE guild_id=?", (guild_id,)
        ) as c:
            r = await c.fetchone()
            return r[0] if r else None


_CONFIG_CACHE: dict[int, tuple[float, dict]] = {}


async def get_guild_config(guild_id: int) -> dict:
    hit = _CONFIG_CACHE.get(guild_id)
    if hit and time.monotonic() - hit[0] < CONFIG_TTL:
        return hit[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT enabled FROM automod WHERE guild_id=?", (guild_id,)) as c:
            row = await c.fetchone()
        enabled = bool(row and row[0] == 1)
        filters = {}
        ignored_channels, ignored_roles, blacklist = set(), set(), []
        if enabled:
            async with db.execute(
                "SELECT filter, enabled, punishment, heat FROM automod_filters WHERE guild_id=?",
                (guild_id,),
            ) as c:
                for name, on, punishment, heat in await c.fetchall():
                    if on == 1:
                        value = heat if heat and heat >= 1 else DEFAULT_HEAT.get(name, 15)
                        filters[name] = (punishment or "Auto Mute", float(value))
            async with db.execute(
                "SELECT type, id FROM automod_ignored WHERE guild_id=?", (guild_id,)
            ) as c:
                for kind, ident in await c.fetchall():
                    (ignored_channels if kind == "channel" else ignored_roles).add(ident)
            if "Blacklist Word" in filters:
                async with db.execute(
                    "SELECT word FROM automod_blacklist WHERE guild_id=?", (guild_id,)
                ) as c:
                    blacklist = [r[0].lower() for r in await c.fetchall()]
    config = {
        "enabled": enabled,
        "filters": filters,
        "ignored_channels": ignored_channels,
        "ignored_roles": ignored_roles,
        "blacklist": blacklist,
    }
    _CONFIG_CACHE[guild_id] = (time.monotonic(), config)
    return config


def invalidate_config(guild_id: int):
    _CONFIG_CACHE.pop(guild_id, None)


async def get_blacklist(guild_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT word FROM automod_blacklist WHERE guild_id=?", (guild_id,)
        ) as c:
            return [r[0] for r in await c.fetchall()]


def _toggle_emoji(state: bool) -> str:
    return E("ENABLED") if state else E("DISABLED")


def _build_filter_text(filter_data: dict) -> str:
    def line(f):
        return f"{E('ARROW')} **{f} :** {_toggle_emoji(filter_data[f]['enabled'])}"
    block1 = "\n".join(line(f) for f in FILTERS_ROW1)
    block2 = "\n".join(line(f) for f in FILTERS_ROW2)
    return f"**Filters [1]:**\n{block1}\n\n**Filters [2]:**\n{block2}"


def _build_settings_text(filter_data: dict) -> str:
    lines = []
    for f in ALL_FILTERS:
        d = filter_data[f]
        pun = d["punishment"]
        heat = d["heat"]
        max_note = " *(Max)*" if heat >= 100 else ""
        status = _toggle_emoji(d["enabled"])
        lines.append(
            f"{E('ARROW')} **{f}** {status}\n"
            f"   └ Punishment: `{pun}` • Heat: `{heat}`{max_note}"
        )
    return "\n\n".join(lines)


def build_container(bot, title: str, body: str, footer: str = None,
                    thumbnail_url: str = None) -> Container:
    thumb_url = thumbnail_url or bot.user.display_avatar.url
    section = Section(
        TextDisplay(f"### {title}\n{body}"),
        accessory=Thumbnail(
            media=discord.UnfurledMediaItem(url=thumb_url),
            description="AutoMod"
        )
    )
    components = [section]
    return Container(*components, accent_color=ACCENT_COLOR)


def build_simple_container(text: str, footer: str = None) -> Container:
    components = [TextDisplay(text)]
    return Container(*components, accent_color=ACCENT_COLOR)


def is_authorized(ctx) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if ctx.author.id == ctx.guild.owner_id:
        return True
    return ctx.author.guild_permissions.administrator


def role_check(ctx) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if ctx.author.id == ctx.guild.owner_id:
        return True
    return ctx.author.top_role.position >= ctx.guild.me.top_role.position


class FilterToggleSelect(Select):
    def __init__(self, guild_id: int, filter_data: dict, author_id: int):
        self.guild_id = guild_id
        self.author_id = author_id

        options = [
            discord.SelectOption(
                label=f,
                description=FILTER_DESCRIPTIONS.get(f, "")[:90],
                value=f,
                default=filter_data[f]["enabled"],
            )
            for f in ALL_FILTERS
        ]
        super().__init__(
            placeholder="Select filters to enable…",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="automod_filter_select",
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id and interaction.user.id not in OWNER_IDS:
            denied = build_simple_container(
                f"{E('CROSS')} You cannot interact with this panel."
            )
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        selected = set(self.values)
        for f in ALL_FILTERS:
            await set_filter(self.guild_id, f, enabled=(f in selected))

        new_data = await get_all_filter_data(self.guild_id)
        view: "AutoModMainView" = self.view
        view.refresh(new_data)
        await interaction.response.edit_message(view=view)


class AutoModMainView(LayoutView):
    def __init__(self, bot, guild_id: int, filter_data: dict, prefix: str, author_id: int, active: bool):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.filter_data = filter_data
        self.prefix = prefix
        self.author_id = author_id
        self.active = active
        self._build()

    def _build(self):
        self.clear_items()

        body = (
            f"*Configure individual filters below. Use `{self.prefix}automod settings` "
            f"to view heat values & punishments, or `{self.prefix}automod rules` for "
            f"detailed trigger info.*\n\n"
            + _build_filter_text(self.filter_data)
        )

        section = Section(
            TextDisplay(f"### {E('CONFIG')} AutoMod Configuration\n{body}"),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url),
                description="AutoMod"
            )
        )

        select = FilterToggleSelect(self.guild_id, self.filter_data, self.author_id)

        settings_btn = Button(label="View Settings", style=discord.ButtonStyle.secondary, custom_id="am_view_settings")
        settings_btn.callback = self._open_settings

        rules_btn = Button(label="Show Rules", style=discord.ButtonStyle.secondary, custom_id="am_show_rules")
        rules_btn.callback = self._show_rules

        done_btn = Button(label="Setup Done", style=discord.ButtonStyle.success, custom_id="am_setup_done")
        done_btn.callback = self._setup_done

        status = "Enabled" if self.active else "Disabled"
        container = Container(
            section,
            Separator(),
            ActionRow(select),
            ActionRow(settings_btn, rules_btn, done_btn),
            accent_color=ACCENT_COLOR
        )
        self.add_item(container)

    def refresh(self, new_data):
        self.filter_data = new_data
        self._build()

    async def _open_settings(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id and interaction.user.id not in OWNER_IDS:
            denied = build_simple_container(f"{E('CROSS')} Not your menu.")
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        data = await get_all_filter_data(self.guild_id)
        settings_view = AutoModSettingsView(self.bot, self.guild_id, data, self.prefix, self.author_id)
        await interaction.response.send_message(view=settings_view, ephemeral=True)

    async def _show_rules(self, interaction: discord.Interaction):
        rules = "\n\n".join(
            f"{E('ARROW')} **{f}**\n{RULES_TEXT.get(f, '')}"
            for f in ALL_FILTERS
        )
        container = build_container(
            self.bot,
            title=f"{E('INFO')} AutoMod Rules",
            body=rules[:3800],
            footer="Trigger rules for each filter"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await interaction.response.send_message(view=v, ephemeral=True)

    async def _setup_done(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id and interaction.user.id not in OWNER_IDS:
            denied = build_simple_container(f"{E('CROSS')} Not your menu.")
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        self.stop()
        done = build_simple_container(
            f"{E('CHECK')} **AutoMod setup complete!** Your server is now protected.",
            footer="Use .automod manage to reconfigure anytime"
        )
        v = LayoutView(timeout=None)
        v.add_item(done)
        await interaction.response.edit_message(view=v)


class FilterConfigSelect(Select):
    def __init__(self, guild_id: int, filter_data: dict, author_id: int):
        self.guild_id = guild_id
        self.author_id = author_id

        options = [
            discord.SelectOption(
                label=f,
                description=f"Pun: {filter_data[f]['punishment']} • Heat: {filter_data[f]['heat']}",
                value=f,
            )
            for f in ALL_FILTERS if f != "Anti NSFW Link"
        ]
        super().__init__(
            placeholder="Select a filter to configure…",
            options=options,
            custom_id="automod_config_select",
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id and interaction.user.id not in OWNER_IDS:
            denied = build_simple_container(f"{E('CROSS')} Not your menu.")
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        modal = FilterConfigModal(self.guild_id, self.values[0], self.author_id)
        await interaction.response.send_modal(modal)


class FilterConfigModal(discord.ui.Modal):
    def __init__(self, guild_id: int, filter_name: str, author_id: int):
        super().__init__(title=f"Configure: {filter_name}"[:45])
        self.guild_id = guild_id
        self.filter_name = filter_name
        self.author_id = author_id

        self.pun_input = discord.ui.TextInput(
            label="Punishment (Auto Mute / Kick / Ban / Delete)",
            placeholder="Auto Mute",
            default="Auto Mute",
            required=True,
            max_length=15,
        )
        self.heat_input = discord.ui.TextInput(
            label="Heat Value (number)",
            placeholder="e.g. 15",
            required=True,
            max_length=8,
        )
        self.add_item(self.pun_input)
        self.add_item(self.heat_input)

    async def on_submit(self, interaction: discord.Interaction):
        pun_raw = self.pun_input.value.strip().lower()
        valid = {
            "auto mute": "Auto Mute", "mute": "Auto Mute", "automute": "Auto Mute",
            "kick": "Kick", "ban": "Ban", "delete": "Delete", "del": "Delete",
        }
        pun = valid.get(pun_raw)
        if not pun:
            denied = build_simple_container(
                f"{E('CROSS')} Invalid punishment. Use: `Auto Mute`, `Kick`, `Ban`, `Delete`."
            )
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        try:
            heat = float(self.heat_input.value.strip())
        except ValueError:
            denied = build_simple_container(f"{E('CROSS')} Heat must be a number.")
            v = LayoutView(timeout=None)
            v.add_item(denied)
            return await interaction.response.send_message(view=v, ephemeral=True)

        await set_filter(self.guild_id, self.filter_name, punishment=pun, heat=heat)

        done = build_simple_container(
            f"{E('CHECK')} **{self.filter_name}** updated!\n"
            f"{E('ARROW')} Punishment: `{pun}`\n"
            f"{E('ARROW')} Heat: `{heat}`"
        )
        v = LayoutView(timeout=None)
        v.add_item(done)
        await interaction.response.send_message(view=v, ephemeral=True)


class AutoModSettingsView(LayoutView):
    def __init__(self, bot, guild_id: int, filter_data: dict, prefix: str, author_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.filter_data = filter_data
        self.prefix = prefix
        self.author_id = author_id
        self._build()

    def _build(self):
        self.clear_items()

        body = (
            f"*Configure punishment & heat for each filter. Tap **Configure Filter** "
            f"and pick one from the dropdown.*\n\n"
            + _build_settings_text(self.filter_data)
        )

        section = Section(
            TextDisplay(f"### {E('BAT')} AutoMod Master Settings\n{body}"),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url),
                description="AutoMod Settings"
            )
        )

        select = FilterConfigSelect(self.guild_id, self.filter_data, self.author_id)

        container = Container(
            section,
            Separator(),
            ActionRow(select),
            accent_color=ACCENT_COLOR
        )
        self.add_item(container)


class ConfirmLayoutView(LayoutView):
    def __init__(self, bot, ctx, title: str, body: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
        self.value = None

        section = Section(
            TextDisplay(f"### {title}\n{body}"),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=bot.user.display_avatar.url),
                description="Confirmation"
            )
        )

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.success, custom_id="am_confirm_yes")
        confirm_btn.callback = self._confirm

        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="am_confirm_no")
        cancel_btn.callback = self._cancel

        container = Container(
            section,
            Separator(),
            ActionRow(confirm_btn, cancel_btn),
            accent_color=ACCENT_COLOR
        )
        self.add_item(container)

    async def _confirm(self, interaction):
        self.value = True
        self.stop()
        await interaction.response.defer()

    async def _cancel(self, interaction):
        self.value = False
        self.stop()
        await interaction.response.defer()

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author and interaction.user.id not in OWNER_IDS:
            denied = build_simple_container(f"{E('CROSS')} Not your menu.")
            v = LayoutView(timeout=None)
            v.add_item(denied)
            await interaction.response.send_message(view=v, ephemeral=True)
            return False
        return True


async def _punish(member: discord.Member, channel: discord.TextChannel,
                  message, punishment: str, reason: str,
                  bot: commands.Bot, guild: discord.Guild, filter_name: str):
    try:
        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        action_taken = None

        if punishment == "Auto Mute":
            mins = _MUTE_DURATIONS.get(filter_name, 5)
            if mins > 0:
                await member.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(minutes=mins),
                    reason=reason,
                )
                action_taken = f"Muted for {mins}m"
            else:
                action_taken = "Message deleted"
        elif punishment == "Kick":
            await member.kick(reason=reason)
            action_taken = "Kicked"
        elif punishment == "Ban":
            await member.ban(reason=reason, delete_message_days=0)
            action_taken = "Banned"
        elif punishment == "Delete":
            action_taken = "Message deleted"

        if action_taken:
            notify = build_simple_container(
                f"{E('CHECK')} {member.mention} — **{action_taken}**\n"
                f"Reason: {reason}"
            )
            v = LayoutView(timeout=None)
            v.add_item(notify)
            try:
                await channel.send(view=v, delete_after=20)
            except discord.HTTPException:
                pass

        log_ch_id = await get_log_channel(guild.id)
        if log_ch_id:
            log_ch = guild.get_channel(log_ch_id)
            if log_ch:
                log_body = (
                    f"**User:** {member.mention} (`{member.id}`)\n"
                    f"**Channel:** {channel.mention}\n"
                    f"**Action:** {action_taken or 'Deleted'}\n"
                    f"**Reason:** {reason}\n"
                    f"**Time:** <t:{int(datetime.now(timezone.utc).timestamp())}:F>"
                )
                section = Section(
                    TextDisplay(f"### {E('SHIELD')} AutoMod — {filter_name}\n{log_body}"),
                    accessory=Thumbnail(
                        media=discord.UnfurledMediaItem(url=member.display_avatar.url),
                        description="Offender"
                    )
                )
                container = Container(
                    section,
                    accent_color=ACCENT_COLOR
                )
                v = LayoutView(timeout=None)
                v.add_item(container)
                try:
                    await log_ch.send(view=v)
                except discord.HTTPException:
                    pass

    except (discord.Forbidden, discord.HTTPException):
        pass


async def _should_check(message: discord.Message, filter_name: str) -> bool:
    if not message.guild or message.author.bot:
        return False
    if not await is_enabled(message.guild.id):
        return False
    if not await filter_enabled(message.guild.id, filter_name):
        return False
    if message.author.id == message.guild.owner_id:
        return False
    if message.author.id in OWNER_IDS:
        return False
    if message.author.guild_permissions.administrator:
        return False
    ignored_ch, ignored_rl = await get_ignored(message.guild.id)
    if message.channel.id in ignored_ch:
        return False
    if any(r.id in ignored_rl for r in message.author.roles):
        return False
    return True


def _not_enabled_view(ctx, bot) -> LayoutView:
    container = build_container(
        bot,
        title=f"{E('CROSS')} AutoMod Not Enabled",
        body=(
            f"AutoMod is not enabled on **{ctx.guild.name}**.\n\n"
            f"{E('ARROW')} Status: {E('DISABLED')} Disabled\n"
            f"{E('ARROW')} Enable with `{ctx.prefix}automod enable`"
        ),
        footer=f"{ctx.guild.name}"
    )
    v = LayoutView(timeout=None)
    v.add_item(container)
    return v


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._heat: dict[tuple, tuple[float, float]] = {}
        self._recent: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=12))
        self._invite_cache: dict[int, tuple[float, set]] = {}
        bot.loop.create_task(init_db())

    async def _access_denied(self, ctx):
        container = build_simple_container(
            f"### {E('LOCK')} Access Restricted\n"
            f"{E('ARROW')} You need **Administrator** permission or be the **Server Owner**.",
            footer=ctx.guild.name
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)


    @commands.group(
        name="automod",
        aliases=["am", "amod"],
        invoke_without_command=True
    )
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def automod(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)

        active = await is_enabled(ctx.guild.id)
        if not active:
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        filter_data = await get_all_filter_data(ctx.guild.id)
        view = AutoModMainView(
            self.bot, ctx.guild.id, filter_data, ctx.prefix, ctx.author.id, active
        )
        await ctx.send(view=view)

    @automod.command(name="help", aliases=["commands", "cmds"])
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def automod_help(self, ctx):
        try:
            from utils.category_help import send_category_help
            sent = await send_category_help(ctx, "automod", self.bot)
            if not sent:
                container = build_simple_container(
                    f"{E('CROSS')} AutoMod help category not found."
                )
                v = LayoutView(timeout=None)
                v.add_item(container)
                await ctx.send(view=v)
        except ImportError:
            container = build_simple_container(
                f"{E('CROSS')} Help system not available."
            )
            v = LayoutView(timeout=None)
            v.add_item(container)
            await ctx.send(view=v)

    @automod.command(name="enable")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_enable(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not role_check(ctx):
            container = build_simple_container(
                f"{E('CROSS')} Your top role must be ≥ my top role."
            )
            v = LayoutView(timeout=None)
            v.add_item(container)
            return await ctx.send(view=v)

        if await is_enabled(ctx.guild.id):
            container = build_simple_container(
                f"{E('INFO')} AutoMod is already enabled. "
                f"Use `{ctx.prefix}automod manage` to configure filters."
            )
            v = LayoutView(timeout=None)
            v.add_item(container)
            return await ctx.send(view=v)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO automod (guild_id, enabled) VALUES (?,1)", (ctx.guild.id,)
            )
            for f in ALL_FILTERS:
                await db.execute(
                    "INSERT OR IGNORE INTO automod_filters (guild_id, filter, enabled, punishment, heat) "
                    "VALUES (?,?,0,'Auto Mute',?)",
                    (ctx.guild.id, f, DEFAULT_HEAT.get(f, 15))
                )
            await db.commit()
            invalidate_config(ctx.guild.id)

        filter_data = await get_all_filter_data(ctx.guild.id)
        view = AutoModMainView(
            self.bot, ctx.guild.id, filter_data, ctx.prefix, ctx.author.id, True
        )
        await ctx.send(view=view)

    @automod.command(name="disable")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_disable(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        view = ConfirmLayoutView(
            self.bot, ctx,
            title=f"{E('WARN')} Disable AutoMod?",
            body=(
                f"This will **clear all filter settings**, ignored channels/roles, "
                f"and the blacklist for **{ctx.guild.name}**.\n\n"
                f"Are you sure?"
            )
        )
        msg = await ctx.send(view=view)
        await view.wait()

        if not view.value:
            cancel = build_simple_container(f"{E('CROSS')} Cancelled.")
            v = LayoutView(timeout=None)
            v.add_item(cancel)
            return await msg.edit(view=v)

        async with aiosqlite.connect(DB_PATH) as db:
            for tbl in ("automod", "automod_filters", "automod_ignored",
                        "automod_logging", "automod_blacklist"):
                await db.execute(f"DELETE FROM {tbl} WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
            invalidate_config(ctx.guild.id)

        done = build_simple_container(
            f"{E('CHECK')} **AutoMod disabled** for **{ctx.guild.name}**.\n"
            f"{E('ARROW')} Status: {E('DISABLED')}\n"
            f"{E('ARROW')} Re-enable with `{ctx.prefix}automod enable`"
        )
        v = LayoutView(timeout=None)
        v.add_item(done)
        await msg.edit(view=v)

    @automod.command(name="manage", aliases=["filters", "toggle"])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_manage(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        filter_data = await get_all_filter_data(ctx.guild.id)
        view = AutoModMainView(
            self.bot, ctx.guild.id, filter_data, ctx.prefix, ctx.author.id, True
        )
        await ctx.send(view=view)

    @automod.command(name="settings", aliases=["config", "panel"])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_settings(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        filter_data = await get_all_filter_data(ctx.guild.id)
        view = AutoModSettingsView(
            self.bot, ctx.guild.id, filter_data, ctx.prefix, ctx.author.id
        )
        await ctx.send(view=view)

    @automod.command(name="rules")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_rules(self, ctx):
        rules = "\n\n".join(
            f"{E('ARROW')} **{f}**\n{RULES_TEXT.get(f, '')}"
            for f in ALL_FILTERS
        )
        container = build_container(
            self.bot,
            title=f"{E('INFO')} AutoMod Rules",
            body=rules[:3800],
            footer="Trigger rules for each filter"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @automod.command(name="reset")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def automod_reset(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)

        view = ConfirmLayoutView(
            self.bot, ctx,
            title=f"{E('WARN')} Reset AutoMod Config?",
            body="This will erase **everything**: filters, settings, whitelist, blacklist, and logs."
        )
        msg = await ctx.send(view=view)
        await view.wait()

        if not view.value:
            cancel = build_simple_container(f"{E('CROSS')} Cancelled.")
            v = LayoutView(timeout=None)
            v.add_item(cancel)
            return await msg.edit(view=v)

        async with aiosqlite.connect(DB_PATH) as db:
            for tbl in ("automod", "automod_filters", "automod_ignored",
                        "automod_logging", "automod_blacklist"):
                await db.execute(f"DELETE FROM {tbl} WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
            invalidate_config(ctx.guild.id)

        done = build_simple_container(
            f"{E('CHECK')} AutoMod configuration reset for **{ctx.guild.name}**."
        )
        v = LayoutView(timeout=None)
        v.add_item(done)
        await msg.edit(view=v)

    @automod.command(name="logging", aliases=["log", "logs"])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automod_logging(self, ctx, channel: discord.TextChannel = None):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        if channel is None:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM automod_logging WHERE guild_id=?", (ctx.guild.id,))
                await db.commit()
                invalidate_config(ctx.guild.id)
            container = build_simple_container(
                f"{E('CHECK')} AutoMod logs channel **reset**."
            )
            v = LayoutView(timeout=None)
            v.add_item(container)
            return await ctx.send(view=v)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?,?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
            invalidate_config(ctx.guild.id)

        container = build_simple_container(
            f"{E('CHECK')} AutoMod logs will be sent to {channel.mention}"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)


    @automod.group(name="whitelist", aliases=["wl", "ignore"], invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def whitelist(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        pre = ctx.prefix
        container = build_container(
            self.bot,
            title=f"{E('SHIELD')} AutoMod Whitelist",
            body=(
                f"Whitelisted channels & roles bypass all automod filters.\n\n"
                f"**Add Channel:** `{pre}automod wl channel #ch`\n"
                f"**Add Role:** `{pre}automod wl role @role`\n"
                f"**View:** `{pre}automod wl show`\n"
                f"**Reset:** `{pre}automod wl reset`"
            ),
            footer="Whitelist management"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @whitelist.command(name="channel")
    @commands.guild_only()
    async def wl_channel(self, ctx, channel: discord.TextChannel):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM automod_ignored WHERE guild_id=? AND type='channel' AND id=?",
                (ctx.guild.id, channel.id)
            ) as c:
                if await c.fetchone():
                    container = build_simple_container(
                        f"{E('DISABLED')} {channel.mention} is already whitelisted."
                    )
                    v = LayoutView(timeout=None)
                    v.add_item(container)
                    return await ctx.send(view=v)
            await db.execute(
                "INSERT OR IGNORE INTO automod_ignored VALUES (?,'channel',?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()
            invalidate_config(ctx.guild.id)

        container = build_simple_container(
            f"{E('CHECK')} {channel.mention} added to the whitelist."
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @whitelist.command(name="role")
    @commands.guild_only()
    async def wl_role(self, ctx, role: discord.Role):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM automod_ignored WHERE guild_id=? AND type='role' AND id=?",
                (ctx.guild.id, role.id)
            ) as c:
                if await c.fetchone():
                    container = build_simple_container(
                        f"{E('DISABLED')} {role.mention} is already whitelisted."
                    )
                    v = LayoutView(timeout=None)
                    v.add_item(container)
                    return await ctx.send(view=v)
            await db.execute(
                "INSERT OR IGNORE INTO automod_ignored VALUES (?,'role',?)",
                (ctx.guild.id, role.id)
            )
            await db.commit()
            invalidate_config(ctx.guild.id)

        container = build_simple_container(
            f"{E('CHECK')} {role.mention} added to the whitelist."
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @whitelist.command(name="show", aliases=["list", "view"])
    @commands.guild_only()
    async def wl_show(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        ignored_ch, ignored_rl = await get_ignored(ctx.guild.id)
        ch_text = "\n".join(f"{E('ARROW')} <#{c}>" for c in ignored_ch) or "*None*"
        rl_text = "\n".join(f"{E('ARROW')} <@&{r}>" for r in ignored_rl) or "*None*"

        body = f"**Channels:**\n{ch_text}\n\n**Roles:**\n{rl_text}"
        container = build_container(
            self.bot,
            title=f"{E('SHIELD')} AutoMod Whitelist — {ctx.guild.name}",
            body=body,
            footer=f"{len(ignored_ch)} channels • {len(ignored_rl)} roles"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @whitelist.command(name="reset", aliases=["clear"])
    @commands.guild_only()
    async def wl_reset(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)

        view = ConfirmLayoutView(
            self.bot, ctx,
            title=f"{E('WARN')} Clear Whitelist?",
            body="Remove all whitelisted channels and roles?"
        )
        msg = await ctx.send(view=view)
        await view.wait()

        if not view.value:
            cancel = build_simple_container(f"{E('CROSS')} Cancelled.")
            v = LayoutView(timeout=None)
            v.add_item(cancel)
            return await msg.edit(view=v)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM automod_ignored WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
            invalidate_config(ctx.guild.id)

        done = build_simple_container(f"{E('CHECK')} Whitelist cleared.")
        v = LayoutView(timeout=None)
        v.add_item(done)
        await msg.edit(view=v)


    @automod.group(name="blacklist", aliases=["bl", "words"], invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def blacklist(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        pre = ctx.prefix
        container = build_container(
            self.bot,
            title=f"{E('SHIELD')} AutoMod Blacklist",
            body=(
                f"Manage blacklisted words. Messages containing these will be punished.\n\n"
                f"**Add:** `{pre}automod bl add <word>`\n"
                f"**Remove:** `{pre}automod bl remove <word>`\n"
                f"**List:** `{pre}automod bl list`"
            ),
            footer="Blacklist word management"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @blacklist.command(name="add")
    @commands.guild_only()
    async def bl_add(self, ctx, *, word: str):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)
        if not await is_enabled(ctx.guild.id):
            return await ctx.send(view=_not_enabled_view(ctx, self.bot))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO automod_blacklist (guild_id, word) VALUES (?,?)",
                (ctx.guild.id, word.lower())
            )
            await db.commit()
            invalidate_config(ctx.guild.id)

        container = build_simple_container(
            f"{E('CHECK')} Added `{word}` to the blacklist."
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @blacklist.command(name="remove", aliases=["del", "rm"])
    @commands.guild_only()
    async def bl_remove(self, ctx, *, word: str):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM automod_blacklist WHERE guild_id=? AND word=?",
                (ctx.guild.id, word.lower())
            )
            await db.commit()
            invalidate_config(ctx.guild.id)

        container = build_simple_container(
            f"{E('CHECK')} Removed `{word}` from the blacklist."
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)

    @blacklist.command(name="list", aliases=["show", "view"])
    @commands.guild_only()
    async def bl_list(self, ctx):
        if not is_authorized(ctx):
            return await self._access_denied(ctx)

        words = await get_blacklist(ctx.guild.id)
        body = (", ".join(f"`{w}`" for w in words) if words
                else "*No blacklisted words.*")

        container = build_container(
            self.bot,
            title=f"{E('SHIELD')} Blacklisted Words — {ctx.guild.name}",
            body=body,
            footer=f"{len(words)} word(s)"
        )
        v = LayoutView(timeout=None)
        v.add_item(container)
        await ctx.send(view=v)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self._scan(message, edited=False)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content == after.content:
            return
        if (discord.utils.utcnow() - after.created_at).total_seconds() > 300:
            return
        await self._scan(after, edited=True)

    _LINK_RE    = re.compile(r"https?://[^\s<>]+", re.I)
    _INVITE_RE  = re.compile(
        r"(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/([\w-]+)", re.I
    )
    _SAFE_LINK_RE = re.compile(
        r"(\.gif(\?|$)|^https?://(www\.)?(tenor\.com|giphy\.com|cdn\.discordapp\.com|"
        r"media\.discordapp\.net|open\.spotify\.com))", re.I
    )
    _EMOJI_RE   = re.compile(
        r"<a?:[a-zA-Z0-9_]+:[0-9]+>|"
        r"[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|"
        r"[\U0001F700-\U0001FAFF]|[\U00002700-\U000027BF]|[\U0001F1E6-\U0001F1FF]"
    )
    _ZALGO_RE   = re.compile(r"[\u0300-\u036f\u0489]{3,}")
    _NSFW_RE    = re.compile(
        r"\b(porn|xxx|xnxx|onlyfans|brazzers|xhamster|xvideos|pornhub|redtube)\b", re.I
    )

    async def _scan(self, msg: discord.Message, edited: bool):
        if not msg.guild or msg.author.bot or not isinstance(msg.author, discord.Member):
            return
        cfg = await get_guild_config(msg.guild.id)
        if not cfg["enabled"] or not cfg["filters"]:
            return

        member = msg.author
        if member.id == msg.guild.owner_id or member.id in OWNER_IDS:
            return
        if member.guild_permissions.administrator:
            return
        channel_ids = {msg.channel.id, getattr(msg.channel, "category_id", None), getattr(msg.channel, "parent_id", None)}
        if channel_ids & cfg["ignored_channels"]:
            return
        if any(r.id in cfg["ignored_roles"] for r in member.roles):
            return

        recent = self._recent[(msg.guild.id, member.id)]
        now = msg.created_at.timestamp()
        if not edited:
            recent.append((now, msg.content.lower().strip(), msg))

        for name, check in self._pipeline():
            if name not in cfg["filters"]:
                continue
            if edited and name in ("Anti Spam", "Similar Message Spam", "Anti Attachment Spam"):
                continue
            reason = await check(msg, cfg, recent, now)
            if not reason:
                continue
            punishment, heat = cfg["filters"][name]
            if not self._add_heat(msg.guild.id, member.id, name, heat):
                continue
            if name in ("Anti Spam", "Similar Message Spam"):
                await self._clear_recent(msg, recent, now)
            await _punish(member, msg.channel, msg, punishment, reason, self.bot, msg.guild, name)
            return

    def _pipeline(self):
        return (
            ("Blacklist Word", self._check_blacklist),
            ("Anti Invites", self._check_invites),
            ("Anti NSFW Link", self._check_nsfw),
            ("Anti Link", self._check_link),
            ("Anti Mass Mention", self._check_mass_mention),
            ("Anti Attachment Spam", self._check_attachment_spam),
            ("Anti Caps", self._check_caps),
            ("Anti Emoji Spam", self._check_emoji_spam),
            ("Anti Zalgo Spam", self._check_zalgo),
            ("New Line Spam", self._check_newline),
            ("Character Limit Spam", self._check_charlimit),
            ("Similar Message Spam", self._check_similar),
            ("Anti Spam", self._check_spam),
        )

    def _add_heat(self, guild_id: int, user_id: int, name: str, amount: float) -> bool:
        now = time.monotonic()
        key = (guild_id, user_id, name)
        value, stamp = self._heat.get(key, (0.0, now))
        value = max(0.0, value - (now - stamp) * HEAT_DECAY) + amount
        if value >= HEAT_LIMIT:
            self._heat.pop(key, None)
            return True
        self._heat[key] = (value, now)
        if len(self._heat) > 5000:
            cutoff = now - 60
            self._heat = {k: v for k, v in self._heat.items() if v[1] > cutoff}
        return False

    async def _clear_recent(self, msg: discord.Message, recent: deque, now: float):
        doomed = [m for t, _, m in recent if now - t <= 15 and m.id != msg.id]
        recent.clear()
        if not doomed:
            return
        try:
            await msg.channel.delete_messages(doomed[-10:])
        except (discord.Forbidden, discord.HTTPException, TypeError, ValueError):
            pass

    async def _check_blacklist(self, msg, cfg, recent, now):
        content = msg.content.lower()
        for word in cfg["blacklist"]:
            if word and word in content:
                return f"Blacklisted word: {word}"
        return None

    async def _invite_codes(self, guild: discord.Guild) -> set:
        hit = self._invite_cache.get(guild.id)
        if hit and time.monotonic() - hit[0] < 60:
            return hit[1]
        codes = set()
        if guild.vanity_url_code:
            codes.add(guild.vanity_url_code.lower())
        try:
            codes.update(inv.code.lower() for inv in await guild.invites())
        except (discord.Forbidden, discord.HTTPException):
            pass
        self._invite_cache[guild.id] = (time.monotonic(), codes)
        return codes

    async def _check_invites(self, msg, cfg, recent, now):
        found = self._INVITE_RE.findall(msg.content)
        if not found:
            return None
        own = await self._invite_codes(msg.guild)
        if all(code.lower() in own for code in found):
            return None
        return "Server invite"

    async def _check_nsfw(self, msg, cfg, recent, now):
        if self._NSFW_RE.search(msg.content):
            return "NSFW content"
        return None

    async def _check_link(self, msg, cfg, recent, now):
        links = self._LINK_RE.findall(msg.content)
        if not links:
            return None
        for link in links:
            if self._INVITE_RE.search(link) or self._SAFE_LINK_RE.search(link):
                continue
            return "Unauthorized link"
        return None

    async def _check_mass_mention(self, msg, cfg, recent, now):
        if len(set(m.id for m in msg.mentions)) + len(msg.role_mentions) >= 5:
            return "Mass mention"
        return None

    async def _check_attachment_spam(self, msg, cfg, recent, now):
        if len(msg.attachments) >= 4:
            return "Attachment spam"
        return None

    async def _check_caps(self, msg, cfg, recent, now):
        if len(msg.content) < 45:
            return None
        letters = [c for c in msg.content if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.70:
            return "Excessive caps"
        return None

    async def _check_emoji_spam(self, msg, cfg, recent, now):
        if len(self._EMOJI_RE.findall(msg.content)) > 6:
            return "Emoji spam"
        return None

    async def _check_zalgo(self, msg, cfg, recent, now):
        if self._ZALGO_RE.search(msg.content):
            return "Zalgo text"
        return None

    async def _check_newline(self, msg, cfg, recent, now):
        if msg.content.count("\n") > 10:
            return "Newline spam"
        return None

    async def _check_charlimit(self, msg, cfg, recent, now):
        if len(msg.content) >= 1500:
            return "Character limit exceeded"
        return None

    async def _check_similar(self, msg, cfg, recent, now):
        content = msg.content.lower().strip()[:200]
        if len(content) < 4:
            return None
        for stamp, other, other_msg in list(recent)[:-1]:
            if other_msg.id == msg.id or now - stamp > 30 or len(other) < 4:
                continue
            if difflib.SequenceMatcher(None, content, other[:200]).ratio() >= 0.85:
                return "Similar message spam"
        return None

    async def _check_spam(self, msg, cfg, recent, now):
        burst = sum(1 for stamp, _, _ in recent if now - stamp <= 10)
        if burst >= 3:
            return "Spam"
        return None

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        async with aiosqlite.connect(DB_PATH) as db:
            for tbl in ("automod", "automod_filters", "automod_ignored",
                        "automod_logging", "automod_blacklist"):
                await db.execute(f"DELETE FROM {tbl} WHERE guild_id=?", (guild.id,))
            await db.commit()
            invalidate_config(guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))

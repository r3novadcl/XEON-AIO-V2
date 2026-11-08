import asyncio
import re as _re
from pathlib import Path

import aiohttp
import aiosqlite
import discord
from discord import ui
from discord.ext import commands

from discord.http import Route

from XEON.emojis import E as _EMGR
from utils.config import OWNER_IDS

_KEY_MAP = {
    "success": "SUCCESS",
    "error": "ERROR",
    "info": "INFO",
    "settings": "SETTINGS",
    "name": "NAME",
    "avatar": "AVATAR",
    "banner": "BANNER",
}

ACCENT_COLOR = discord.Colour(0x000000)
BOT_NAME = "XEON"

DB_DIR = Path("db")
DB_PATH = DB_DIR / "custombot.db"


def ES(key: str) -> str:
    return _EMGR[_KEY_MAP.get(key, key.upper())]


def _card(emoji_key: str, text: str) -> ui.LayoutView:
    v = ui.LayoutView()
    c = ui.Container(accent_color=ACCENT_COLOR)
    c.add_item(ui.TextDisplay(f"{ES(emoji_key)} {text}"))
    v.add_item(c)
    return v


def _error_view(text: str) -> ui.LayoutView:
    return _card("error", text)


def _success_view(text: str) -> ui.LayoutView:
    return _card("success", text)


def _info_view(text: str) -> ui.LayoutView:
    return _card("info", text)


def _build_custombot_view(cog, guild_id: int, cfg: dict | None) -> ui.LayoutView:
    view = CustomBotView(cog, guild_id)
    c = ui.Container(accent_color=ACCENT_COLOR)

    c.add_item(ui.TextDisplay(f"### {ES('settings')} CustomBot Settings"))
    c.add_item(ui.Separator())

    c.add_item(ui.TextDisplay(
        f"Customize your **{BOT_NAME}** appearance for this server.\n"
        f"All changes are server-specific."
    ))
    c.add_item(ui.Separator())

    if cfg:
        cur_name   = cfg.get("name")   or "*(not set)*"
        cur_avatar = cfg.get("avatar") or "*(not set)*"
        cur_banner = cfg.get("banner") or "*(not set)*"
    else:
        cur_name = cur_avatar = cur_banner = "*(not set)*"

    c.add_item(ui.TextDisplay(
        f"{ES('name')}   **Nickname:** `{cur_name[:60]}`\n"
        f"{ES('avatar')} **Avatar:** `{cur_avatar[:60]}`\n"
        f"{ES('banner')} **Banner:** `{cur_banner[:60]}`"
    ))

    c.add_item(ui.Separator())

    row1 = ui.ActionRow()
    row1.add_item(view.btn_avatar)
    row1.add_item(view.btn_name)
    row1.add_item(view.btn_banner)
    c.add_item(row1)

    row2 = ui.ActionRow()
    row2.add_item(view.btn_reset)
    row2.add_item(view.btn_close)
    c.add_item(row2)

    c.add_item(ui.Separator(visible=False))
    c.add_item(ui.TextDisplay(
        f"**Tip:** Use direct image links (PNG / JPG / GIF). "
        f"Server needs Boost Level 2 for banners."
    ))

    view.add_item(c)
    return view


class CustomBotView(ui.LayoutView):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog      = cog
        self.guild_id = guild_id

        self.btn_avatar = ui.Button(label="Change Avatar", style=discord.ButtonStyle.primary, custom_id="cb_avatar")
        self.btn_name   = ui.Button(label="Change Name",   style=discord.ButtonStyle.primary, custom_id="cb_name")
        self.btn_banner = ui.Button(label="Change Banner", style=discord.ButtonStyle.primary, custom_id="cb_banner")
        self.btn_reset  = ui.Button(label="Reset All",     style=discord.ButtonStyle.danger,  custom_id="cb_reset")
        self.btn_close  = ui.Button(label="Close",         style=discord.ButtonStyle.secondary, custom_id="cb_close")

        self.btn_avatar.callback = self._on_avatar
        self.btn_name.callback   = self._on_name
        self.btn_banner.callback = self._on_banner
        self.btn_reset.callback  = self._on_reset
        self.btn_close.callback  = self._on_close

    async def _check_perms(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                view=_error_view("You need **Administrator** permission!"),
                ephemeral=True,
            )
            return False
        return True

    async def _wait_input(self, interaction: discord.Interaction, timeout: float = 60.0) -> str | None:
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
        try:
            msg = await self.cog.bot.wait_for("message", check=check, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        try:
            await msg.delete()
        except Exception:
            pass
        return msg.content.strip()

    async def _download(self, url: str) -> bytes | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception:
            pass
        return None

    async def _refresh(self, interaction: discord.Interaction):
        cfg = await self.cog.get_config(self.guild_id)
        new_view = _build_custombot_view(self.cog, self.guild_id, cfg)
        try:
            await interaction.message.edit(view=new_view)
        except Exception:
            pass

    async def _on_avatar(self, interaction: discord.Interaction):
        if not await self._check_perms(interaction):
            return

        await interaction.response.send_message(
            view=_info_view("**Send the avatar image URL** in this channel.\n*Timeout: 60s*"),
            ephemeral=True,
        )

        url = await self._wait_input(interaction)
        if not url:
            return await interaction.edit_original_response(view=_error_view("Timed out!"))
        if not url.startswith(("http://", "https://")):
            return await interaction.edit_original_response(
                view=_error_view("URL must start with `http://` or `https://`")
            )

        data = await self._download(url)
        if not data:
            return await interaction.edit_original_response(
                view=_error_view("Failed to download image from that URL.")
            )

        try:
            await interaction.guild.me.edit(avatar=data)
        except Exception as e:
            return await interaction.edit_original_response(
                view=_error_view(f"Couldn't update avatar: `{e}`")
            )

        await self.cog.set_config(self.guild_id, avatar=url)
        await interaction.edit_original_response(view=_success_view("**Avatar updated!**"))
        await self._refresh(interaction)

    async def _on_name(self, interaction: discord.Interaction):
        if not await self._check_perms(interaction):
            return

        await interaction.response.send_message(
            view=_info_view("**Send the new nickname** in this channel.\n*Timeout: 60s*"),
            ephemeral=True,
        )

        name = await self._wait_input(interaction)
        if not name:
            return await interaction.edit_original_response(view=_error_view("Timed out!"))
        if len(name) > 32:
            return await interaction.edit_original_response(
                view=_error_view("Nickname must be 32 characters or fewer.")
            )

        try:
            await interaction.guild.me.edit(nick=name)
        except Exception as e:
            return await interaction.edit_original_response(
                view=_error_view(f"Couldn't update nickname: `{e}`")
            )

        await self.cog.set_config(self.guild_id, name=name)
        await interaction.edit_original_response(view=_success_view(f"**Nickname set to:** `{name}`"))
        await self._refresh(interaction)

    async def _on_banner(self, interaction: discord.Interaction):
        if not await self._check_perms(interaction):
            return

        if interaction.guild.premium_tier < 2:
            return await interaction.response.send_message(
                view=_error_view("Server needs **Boost Level 2** to set a banner."),
                ephemeral=True,
            )

        await interaction.response.send_message(
            view=_info_view("**Send the banner image URL** in this channel.\n*Timeout: 60s*"),
            ephemeral=True,
        )

        url = await self._wait_input(interaction)
        if not url:
            return await interaction.edit_original_response(view=_error_view("Timed out!"))
        if not url.startswith(("http://", "https://")):
            return await interaction.edit_original_response(
                view=_error_view("URL must start with `http://` or `https://`")
            )

        data = await self._download(url)
        if not data:
            return await interaction.edit_original_response(
                view=_error_view("Failed to download image from that URL.")
            )

        try:
            await interaction.guild.me.edit(banner=data)
        except Exception as e:
            return await interaction.edit_original_response(
                view=_error_view(f"Couldn't update banner: `{e}`")
            )

        await self.cog.set_config(self.guild_id, banner=url)
        await interaction.edit_original_response(view=_success_view("**Banner updated!**"))
        await self._refresh(interaction)

    async def _on_reset(self, interaction: discord.Interaction):
        if not await self._check_perms(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.guild.me.edit(nick=None, avatar=None, banner=None)
        except Exception:
            pass

        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute("DELETE FROM config WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        await interaction.followup.send(
            view=_success_view("**Reset successful!** All customizations cleared."),
            ephemeral=True,
        )
        await self._refresh(interaction)

    async def _on_close(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            await interaction.message.delete()
            self.stop()
        except Exception:
            pass

FONTS = {
    11: "Default", 1: "Tempo", 3: "Sakura", 4: "Jellybean",
    6: "Modern", 7: "Medieval", 8: "8bit", 10: "Vampyre",
}

EFFECTS = {
    1: ("Solid", "Requires exactly 1 color"),
    2: ("Gradient", "Requires exactly 2 colors"),
    3: ("Neon", "Requires exactly 1 color"),
    4: ("Toon", "Requires exactly 1 color"),
    5: ("Pop", "Requires exactly 1 color"),
    6: ("Glow", "Requires exactly 1 color"),
}

COLORS = {
    "Red": 0xFF0000, "Green": 0x00FF00, "Blue": 0x0000FF,
    "Yellow": 0xFFFF00, "Purple": 0x800080, "Cyan": 0x00FFFF,
    "Orange": 0xFFA500, "Pink": 0xFFC0CB, "White": 0xFFFFFF,
}

DEFAULT_NAMEPLATE = (11, 1, [0xFFFFFF])


def _hex(value: int) -> str:
    return f"#{value:06X}"


def _parse_hex(raw: str) -> int | None:
    raw = raw.strip().lstrip("#")
    if len(raw) != 6:
        return None
    try:
        return int(raw, 16)
    except ValueError:
        return None


async def _patch_member(bot: commands.Bot, guild_id: int, payload: dict):
    route = Route("PATCH", "/guilds/{guild_id}/members/@me", guild_id=guild_id)
    await bot.http.request(route, json=payload)


def _is_admin(ctx: commands.Context) -> bool:
    perms = ctx.author.guild_permissions
    return perms.administrator or ctx.author.id == ctx.guild.owner_id or ctx.author.id in OWNER_IDS


class ColorModal(ui.Modal):
    def __init__(self, view: "NameplateView"):
        super().__init__(title="Custom Color (Hex Code)")
        self.np_view = view
        gradient = view.effect == 2
        self.first = ui.TextInput(
            label="First Hex Color" if gradient else "Hex Color",
            placeholder="#FF0000", min_length=6, max_length=7,
        )
        self.add_item(self.first)
        self.second = None
        if gradient:
            self.second = ui.TextInput(
                label="Second Hex Color", placeholder="#00FF00", min_length=6, max_length=7,
            )
            self.add_item(self.second)

    async def on_submit(self, interaction: discord.Interaction):
        first = _parse_hex(self.first.value)
        second = _parse_hex(self.second.value) if self.second else None
        if first is None or (self.second and second is None):
            return await interaction.response.send_message(
                view=_error_view("Invalid hex code. Use 6 characters like `#FF0000`."), ephemeral=True
            )
        self.np_view.colors = [first, second] if self.second else [first]
        self.np_view.menu = "main"
        self.np_view.render()
        await interaction.response.edit_message(view=self.np_view)


class NameplateView(ui.LayoutView):
    def __init__(self, cog, author_id: int, guild: discord.Guild | None, global_mode: bool, state=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.author_id = author_id
        self.guild = guild
        self.global_mode = global_mode
        font, effect, colors = state or DEFAULT_NAMEPLATE
        self.font = font
        self.effect = effect
        self.colors = list(colors)
        self.menu = "main"
        self.message: discord.Message | None = None
        self.render()

    def _color_label(self) -> str:
        shown = self.colors[:2] if self.effect == 2 else self.colors[:1]
        for name, value in COLORS.items():
            if shown == [value]:
                return name
        return ", ".join(_hex(c) for c in shown)

    def render(self):
        self.clear_items()
        scope = (
            "Change the bot's display name for **all servers** that have not customized it."
            if self.global_mode else
            "Change the typography, text effect and colors of the bot's name in this server."
        )
        title = "Global Nameplate Customizer" if self.global_mode else "Bot Nameplate Customizer"
        body = (
            f"### {ES('settings')} {title}\n"
            f"*{scope}*\n\n"
            f"{ES('arrow')} **Font:** `{FONTS.get(self.font, 'Default')}`\n"
            f"{ES('arrow')} **Text Effect:** `{EFFECTS.get(self.effect, EFFECTS[1])[0]}`\n"
            f"{ES('arrow')} **Color:** `{self._color_label()}`"
        )
        children = [ui.TextDisplay(body), ui.Separator()]

        if self.menu == "main":
            row = ui.ActionRow()
            for label, menu in (("Choose Font", "font"), ("Choose Text Effect", "style"), ("Choose Colour", "color")):
                button = ui.Button(label=label, style=discord.ButtonStyle.primary)
                button.callback = self._menu_callback(menu)
                row.add_item(button)
            children.append(row)
            row2 = ui.ActionRow()
            save = ui.Button(label="Save Globally" if self.global_mode else "Save", style=discord.ButtonStyle.success)
            save.callback = self.on_save
            row2.add_item(save)
            reset = ui.Button(label="Reset", style=discord.ButtonStyle.danger)
            reset.callback = self.on_reset
            row2.add_item(reset)
            children.append(row2)
        elif self.menu == "font":
            select = ui.Select(
                placeholder="Select a font...",
                options=[discord.SelectOption(label=n, value=str(i), description=f"Apply the {n} font.") for i, n in FONTS.items()],
            )
            select.callback = self.on_font
            children.append(ui.ActionRow(select))
            children.append(self._back_row())
        elif self.menu == "style":
            select = ui.Select(
                placeholder="Select a text effect...",
                options=[discord.SelectOption(label=n, value=str(i), description=d) for i, (n, d) in EFFECTS.items()],
            )
            select.callback = self.on_style
            children.append(ui.ActionRow(select))
            children.append(self._back_row())
        elif self.menu == "color":
            slots = (0, 1) if self.effect == 2 else (0,)
            for slot in slots:
                options = [
                    discord.SelectOption(label=name, value=name, description=f"Apply {name}.")
                    for name in COLORS
                ]
                options.append(discord.SelectOption(label="Custom Color", value="custom", description="Enter custom hex code(s)."))
                placeholder = "Select a color..." if len(slots) == 1 else f"Select gradient color {slot + 1}..."
                select = ui.Select(placeholder=placeholder, options=options)
                select.callback = self._color_callback(slot)
                children.append(ui.ActionRow(select))
            children.append(self._back_row())

        self.add_item(ui.Container(*children, accent_color=ACCENT_COLOR))

    def _back_row(self) -> ui.ActionRow:
        back = ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back.callback = self._menu_callback("main")
        return ui.ActionRow(back)

    def _menu_callback(self, menu: str):
        async def callback(interaction: discord.Interaction):
            self.menu = menu
            self.render()
            await interaction.response.edit_message(view=self)
        return callback

    def _color_callback(self, slot: int):
        async def callback(interaction: discord.Interaction):
            value = interaction.data["values"][0]
            if value == "custom":
                return await interaction.response.send_modal(ColorModal(self))
            while len(self.colors) < 2:
                self.colors.append(self.colors[0])
            self.colors[slot] = COLORS[value]
            self.render()
            await interaction.response.edit_message(view=self)
        return callback

    async def on_font(self, interaction: discord.Interaction):
        self.font = int(interaction.data["values"][0])
        self.menu = "main"
        self.render()
        await interaction.response.edit_message(view=self)

    async def on_style(self, interaction: discord.Interaction):
        self.effect = int(interaction.data["values"][0])
        if self.effect == 2 and len(self.colors) < 2:
            self.colors = [self.colors[0], self.colors[0]]
        elif self.effect != 2:
            self.colors = self.colors[:1]
        self.menu = "main"
        self.render()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                view=_error_view("Only the command author can use this menu."), ephemeral=True
            )
            return False
        return True

    async def on_save(self, interaction: discord.Interaction):
        colors = self.colors[:2] if self.effect == 2 else self.colors[:1]
        if self.effect == 2 and len(colors) < 2:
            colors = [colors[0], colors[0]]
        payload = {
            "display_name_font_id": self.font,
            "display_name_effect_id": self.effect,
            "display_name_colors": colors,
        }
        await interaction.response.defer(ephemeral=True)
        try:
            if self.global_mode:
                updated, skipped = await self.cog.apply_nameplate_global(payload)
                text = f"Global update complete.\nUpdated **{updated}** servers.\nSkipped **{skipped}** customized servers."
            else:
                await _patch_member(self.cog.bot, self.guild.id, payload)
                await self.cog.set_config(
                    self.guild.id, np_font=self.font, np_effect=self.effect,
                    np_colors=",".join(str(c) for c in colors),
                )
                text = "Successfully updated the bot's display style for this server."
            await interaction.followup.send(view=_success_view(text), ephemeral=True)
        except discord.HTTPException as error:
            await interaction.followup.send(view=_error_view(f"Failed to update display style: `{error}`"), ephemeral=True)

    async def on_reset(self, interaction: discord.Interaction):
        payload = {"display_name_font_id": None, "display_name_effect_id": None, "display_name_colors": None}
        await interaction.response.defer(ephemeral=True)
        try:
            await _patch_member(self.cog.bot, self.guild.id, payload)
            await self.cog.set_config(self.guild.id, np_font=None, np_effect=None, np_colors=None)
            self.font, self.effect, self.colors = DEFAULT_NAMEPLATE[0], DEFAULT_NAMEPLATE[1], list(DEFAULT_NAMEPLATE[2])
            self.render()
            await interaction.message.edit(view=self)
            await interaction.followup.send(view=_success_view("Reset the bot's display style to default."), ephemeral=True)
        except discord.HTTPException as error:
            await interaction.followup.send(view=_error_view(f"Failed to reset display style: `{error}`"), ephemeral=True)

    async def on_timeout(self):
        if not self.message:
            return
        for child in self.walk_children():
            if isinstance(child, (ui.Button, ui.Select)):
                child.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


class CustomBot(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        DB_DIR.mkdir(exist_ok=True)
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS config ("
                "guild_id INTEGER PRIMARY KEY, name TEXT, avatar TEXT, banner TEXT)"
            )
            async with db.execute("PRAGMA table_info(config)") as cur:
                existing = {row[1] for row in await cur.fetchall()}
            for column, kind in (("bio", "TEXT"), ("np_font", "INTEGER"), ("np_effect", "INTEGER"), ("np_colors", "TEXT")):
                if column not in existing:
                    await db.execute(f"ALTER TABLE config ADD COLUMN {column} {kind}")
            await db.commit()
        self.bot.loop.create_task(self.apply_all_configs())

    async def get_config(self, guild_id: int) -> dict | None:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM config WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def set_config(self, guild_id: int, **fields):
        allowed = {"name", "avatar", "banner", "bio", "np_font", "np_effect", "np_colors"}
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute("INSERT OR IGNORE INTO config (guild_id) VALUES (?)", (guild_id,))
            for col, val in fields.items():
                if col in allowed:
                    await db.execute(f"UPDATE config SET {col} = ? WHERE guild_id = ?", (val, guild_id))
            await db.commit()

    async def apply_all_configs(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(str(DB_PATH)) as db:
            async with db.execute("SELECT guild_id, name, avatar, banner FROM config") as cur:
                rows = await cur.fetchall()
        async with aiohttp.ClientSession() as session:
            for guild_id, name, avatar, banner in rows:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                try:
                    if name:
                        await guild.me.edit(nick=name)
                    if avatar:
                        async with session.get(avatar) as resp:
                            if resp.status == 200:
                                await guild.me.edit(avatar=await resp.read())
                    if banner and guild.premium_tier >= 2:
                        async with session.get(banner) as resp:
                            if resp.status == 200:
                                await guild.me.edit(banner=await resp.read())
                except Exception:
                    pass
                await asyncio.sleep(1.5)


    async def _download(self, url: str) -> bytes | None:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
            except aiohttp.ClientError:
                return None
        return None

    async def apply_nameplate_global(self, payload: dict) -> tuple[int, int]:
        updated = skipped = 0
        async with aiosqlite.connect(str(DB_PATH)) as db:
            async with db.execute("SELECT guild_id FROM config WHERE np_font IS NOT NULL") as cur:
                customized = {row[0] for row in await cur.fetchall()}
        for guild in list(self.bot.guilds):
            if guild.id in customized:
                skipped += 1
                continue
            try:
                await _patch_member(self.bot, guild.id, payload)
                updated += 1
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.6)
        return updated, skipped

    async def _guard(self, ctx: commands.Context) -> bool:
        if _is_admin(ctx):
            return True
        await ctx.send(view=_error_view("You must be a Server Administrator or Owner to use this."))
        return False

    @commands.command(name="bbio")
    @commands.guild_only()
    async def bbio(self, ctx: commands.Context, *, text: str = None):
        if not await self._guard(ctx):
            return
        if not text:
            return await ctx.send(view=_error_view(f"Usage: `{ctx.prefix}bbio <text | none>`"))
        bio = None if text.lower() == "none" else text[:190]
        try:
            await _patch_member(self.bot, ctx.guild.id, {"bio": bio})
        except discord.HTTPException as error:
            return await ctx.send(view=_error_view(f"Failed to update bio: `{error}`"))
        await self.set_config(ctx.guild.id, bio=bio)
        await ctx.send(view=_success_view("Reset the bot's server bio." if bio is None else "Updated the bot's server bio."))

    @commands.command(name="bpfp", aliases=["bavatar"])
    @commands.guild_only()
    async def bpfp(self, ctx: commands.Context, url: str = None):
        if not await self._guard(ctx):
            return
        url = url or (ctx.message.attachments[0].url if ctx.message.attachments else None)
        if not url:
            return await ctx.send(view=_error_view(f"Usage: `{ctx.prefix}bpfp <url | none>` or attach an image."))
        try:
            if url.lower() == "none":
                await ctx.guild.me.edit(avatar=None)
                await self.set_config(ctx.guild.id, avatar=None)
                return await ctx.send(view=_success_view("Reset the bot's server avatar."))
            data = await self._download(url)
            if not data:
                return await ctx.send(view=_error_view("Failed to download the image. Check the URL."))
            await ctx.guild.me.edit(avatar=data)
            await self.set_config(ctx.guild.id, avatar=url)
        except (discord.HTTPException, ValueError) as error:
            return await ctx.send(view=_error_view(f"Failed to update avatar: `{error}`"))
        await ctx.send(view=_success_view("Updated the bot's server avatar."))

    @commands.command(name="bbanner")
    @commands.guild_only()
    async def bbanner(self, ctx: commands.Context, url: str = None):
        if not await self._guard(ctx):
            return
        url = url or (ctx.message.attachments[0].url if ctx.message.attachments else None)
        if not url:
            return await ctx.send(view=_error_view(f"Usage: `{ctx.prefix}bbanner <url | none>` or attach an image."))
        try:
            if url.lower() == "none":
                await ctx.guild.me.edit(banner=None)
                await self.set_config(ctx.guild.id, banner=None)
                return await ctx.send(view=_success_view("Reset the bot's server banner."))
            data = await self._download(url)
            if not data:
                return await ctx.send(view=_error_view("Failed to download the image. Check the URL."))
            await ctx.guild.me.edit(banner=data)
            await self.set_config(ctx.guild.id, banner=url)
        except (discord.HTTPException, ValueError) as error:
            return await ctx.send(view=_error_view(f"Failed to update banner: `{error}`"))
        await ctx.send(view=_success_view("Updated the bot's server banner."))

    @commands.command(name="bnameplate", aliases=["bstyle"])
    @commands.guild_only()
    async def bnameplate(self, ctx: commands.Context):
        if not await self._guard(ctx):
            return
        cfg = await self.get_config(ctx.guild.id) or {}
        state = None
        if cfg.get("np_font") is not None:
            colors = [int(c) for c in (cfg.get("np_colors") or "16777215").split(",") if c]
            state = (cfg["np_font"], cfg.get("np_effect") or 1, colors or [0xFFFFFF])
        view = NameplateView(self, ctx.author.id, ctx.guild, False, state)
        view.message = await ctx.send(view=view)

    @commands.command(name="gnameplate", aliases=["gstyle"])
    async def gnameplate(self, ctx: commands.Context):
        if ctx.author.id not in OWNER_IDS:
            return await ctx.send(view=_error_view("You must be a Bot Owner to use this command."))
        view = NameplateView(self, ctx.author.id, None, True)
        view.message = await ctx.send(view=view)

    @commands.command(name="custombot", aliases=["cb"])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def custombot(self, ctx: commands.Context):
        cfg = await self.get_config(ctx.guild.id)
        await ctx.send(view=_build_custombot_view(self, ctx.guild.id, cfg))


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomBot(bot))

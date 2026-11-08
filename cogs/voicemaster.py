import discord
from discord.ext import commands
from discord import ui
import json
import os
import re as _re
from XEON.emojis import E as _EMGR

def _vm_partial(key: str) -> discord.PartialEmoji:
    s = _EMGR[key]
    m = _re.match(r'<(a)?:([A-Za-z0-9_]+):(\d+)>', s)
    if m:
        return discord.PartialEmoji(name=m.group(2), id=int(m.group(3)), animated=bool(m.group(1)))
    return discord.PartialEmoji(name='grey_arrw', id=1517367908714549308)

VM_LOCK      = _vm_partial("VM_LOCK")
VM_UNLOCK    = _vm_partial("VM_UNLOCK")
VM_HIDE      = _vm_partial("VM_HIDE")
VM_UNHIDE    = _vm_partial("VM_UNHIDE")
VM_RENAME    = _vm_partial("VM_RENAME")
VM_LIMIT     = _vm_partial("VM_LIMIT")
VM_MUTE      = _vm_partial("VM_MUTE")
VM_UNMUTE    = _vm_partial("VM_UNMUTE")
VM_DEAFEN    = _vm_partial("VM_BITRATE")
VM_UNDEAFEN  = _vm_partial("VM_UNDEAFEN")
VM_PERMIT    = _vm_partial("VM_KICK")
VM_BAN       = _vm_partial("VM_BAN")
VM_TRANSFER  = _vm_partial("VM_TRANSFER")
VM_CLAIM     = _vm_partial("VM_CLAIM")

BTN_EMOJI = {
    "lock": VM_LOCK, "unlock": VM_UNLOCK,
    "hide": VM_HIDE, "unhide": VM_UNHIDE,
    "rename": VM_RENAME, "limit": VM_LIMIT,
    "mute": VM_MUTE, "unmute": VM_UNMUTE,
    "deafen": VM_DEAFEN, "undeafen": VM_UNDEAFEN,
    "permit": VM_PERMIT, "ban": VM_BAN,
    "transfer": VM_TRANSFER, "claim": VM_CLAIM,
}

BTN_EMOJI_STR = {
    "lock":     _EMGR["VM_LOCK"],
    "unlock":   _EMGR["VM_UNLOCK"],
    "hide":     _EMGR["VM_HIDE"],
    "unhide":   _EMGR["VM_UNHIDE"],
    "rename":   _EMGR["VM_RENAME"],
    "limit":    _EMGR["VM_LIMIT"],
    "mute":     _EMGR["VM_MUTE"],
    "unmute":   _EMGR["VM_UNMUTE"],
    "deafen":   _EMGR["VM_BITRATE"],
    "undeafen": _EMGR["VM_UNDEAFEN"],
    "permit":   _EMGR["VM_KICK"],
    "ban":      _EMGR["VM_BAN"],
    "transfer": _EMGR["VM_TRANSFER"],
    "claim":    _EMGR["VM_CLAIM"],
}

BTN_LABELS = {
    "lock": "Lock", "unlock": "Unlock",
    "hide": "Hide", "unhide": "Unhide",
    "rename": "Rename", "limit": "Limit",
    "mute": "Mute", "unmute": "Unmute",
    "deafen": "Deafen", "undeafen": "Undeafen",
    "permit": "Permit", "ban": "Ban",
    "transfer": "Transfer", "claim": "Claim",
}

ALL_BUTTONS = [
    "lock", "unlock", "hide", "unhide", "rename",
    "limit", "mute", "unmute", "deafen", "undeafen",
    "permit", "ban", "transfer", "claim",
]

from utils.config import SUPPORT_SERVER as PROMO_LINK

BTN_DESC = {
    "lock":     f"[`Lock`]({PROMO_LINK}) your voice channel",
    "unlock":   f"[`Unlock`]({PROMO_LINK}) your voice channel",
    "hide":     f"[`Hide`]({PROMO_LINK}) your voice channel",
    "unhide":   f"[`Reveal`]({PROMO_LINK}) your voice channel",
    "rename":   f"[`Rename`]({PROMO_LINK}) your voice channel",
    "limit":    f"[`Limit`]({PROMO_LINK}) your voice channel user limit",
    "mute":     f"[`Mute`]({PROMO_LINK}) a user in your channel",
    "unmute":   f"[`Unmute`]({PROMO_LINK}) a user in your channel",
    "deafen":   f"[`Deafen`]({PROMO_LINK}) a user in your channel",
    "undeafen": f"[`Undeafen`]({PROMO_LINK}) a user in your channel",
    "permit":   f"[`Permit`]({PROMO_LINK}) a user to join",
    "ban":      f"[`Ban`]({PROMO_LINK}) a user from your channel",
    "transfer": f"[`Transfer`]({PROMO_LINK}) ownership",
    "claim":    f"[`Claim`]({PROMO_LINK}) an abandoned channel",
}

BLACK = discord.Colour(0x000000)
DATA_FILE = "data/voicemaster.json"

def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _get_guild(guild_id: int) -> dict | None:
    return _load().get(str(guild_id))

def _set_guild(guild_id: int, config: dict):
    data = _load()
    data[str(guild_id)] = config
    _save(data)

def _del_guild(guild_id: int):
    data = _load()
    data.pop(str(guild_id), None)
    _save(data)

def _reply_view(text: str) -> ui.LayoutView:
    v = ui.LayoutView(timeout=None)
    c = ui.Container(accent_colour=BLACK)
    c.add_item(ui.TextDisplay(content=text))
    v.add_item(c)
    return v

class RenameModal(ui.Modal, title="Rename Voice Channel"):
    name = ui.TextInput(label="New Channel Name", placeholder="Enter new name...", max_length=100, min_length=1)

    def __init__(self, vc):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        new = self.name.value.strip()
        try:
            await self.vc.edit(name=new)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['rename']} Channel renamed to **{new}**"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                view=_reply_view(f"Error: `{e}`"), ephemeral=True)

class LimitModal(ui.Modal, title="Set User Limit"):
    limit = ui.TextInput(label="User Limit (0 = unlimited)", placeholder="0-99", max_length=2)

    def __init__(self, vc):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = max(0, min(99, int(self.limit.value.strip())))
            await self.vc.edit(user_limit=val)
            t = "unlimited" if val == 0 else str(val)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['limit']} User limit set to **{t}**"), ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                view=_reply_view("Enter a valid number (0-99)"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                view=_reply_view(f"Error: `{e}`"), ephemeral=True)

class UserActionModal(ui.Modal):
    user_input = ui.TextInput(label="User ID or Username", placeholder="Enter user ID or username...", max_length=100)

    def __init__(self, vc, guild, action):
        super().__init__(title=f"{action.title()} User")
        self.vc = vc
        self.guild = guild
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        try:
            member = self.guild.get_member(int(raw))
        except ValueError:
            pass
        if not member:
            rl = raw.lower()
            member = discord.utils.find(
                lambda m: m.name.lower() == rl or m.display_name.lower() == rl, self.guild.members)
        if not member:
            return await interaction.response.send_message(
                view=_reply_view("Member not found! Use their User ID."), ephemeral=True)

        try:
            a = self.action
            if a == "mute":
                if not (member.voice and member.voice.channel == self.vc):
                    return await interaction.response.send_message(
                        view=_reply_view("That user is not in your channel!"), ephemeral=True)
                await member.edit(mute=True)
                msg = f"{BTN_EMOJI_STR['mute']} **{member.display_name}** has been muted"

            elif a == "unmute":
                if not (member.voice and member.voice.channel == self.vc):
                    return await interaction.response.send_message(
                        view=_reply_view("That user is not in your channel!"), ephemeral=True)
                await member.edit(mute=False)
                msg = f"{BTN_EMOJI_STR['unmute']} **{member.display_name}** has been unmuted"

            elif a == "deafen":
                if not (member.voice and member.voice.channel == self.vc):
                    return await interaction.response.send_message(
                        view=_reply_view("That user is not in your channel!"), ephemeral=True)
                await member.edit(deafen=True)
                msg = f"{BTN_EMOJI_STR['deafen']} **{member.display_name}** has been deafened"

            elif a == "undeafen":
                if not (member.voice and member.voice.channel == self.vc):
                    return await interaction.response.send_message(
                        view=_reply_view("That user is not in your channel!"), ephemeral=True)
                await member.edit(deafen=False)
                msg = f"{BTN_EMOJI_STR['undeafen']} **{member.display_name}** has been undeafened"

            elif a == "permit":
                ow = self.vc.overwrites_for(member)
                ow.connect = True
                ow.view_channel = True
                await self.vc.set_permissions(member, overwrite=ow)
                msg = f"{BTN_EMOJI_STR['permit']} **{member.display_name}** has been permitted"

            elif a == "ban":
                ow = self.vc.overwrites_for(member)
                ow.connect = False
                ow.view_channel = False
                await self.vc.set_permissions(member, overwrite=ow)
                if member.voice and member.voice.channel and member.voice.channel.id == self.vc.id:
                    await member.move_to(None)
                msg = f"{BTN_EMOJI_STR['ban']} **{member.display_name}** has been banned from your channel"
            else:
                msg = "Done"

            await interaction.response.send_message(view=_reply_view(msg), ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                view=_reply_view("I don't have permission to do that!"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                view=_reply_view(f"Error: `{e}`"), ephemeral=True)

class TransferModal(ui.Modal, title="Transfer Ownership"):
    user_input = ui.TextInput(label="User ID or Username", placeholder="Enter user ID...", max_length=100)

    def __init__(self, vc, guild, config, owner):
        super().__init__()
        self.vc = vc
        self.guild = guild
        self.config = config
        self.owner = owner

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        try:
            member = self.guild.get_member(int(raw))
        except ValueError:
            pass
        if not member:
            rl = raw.lower()
            member = discord.utils.find(
                lambda m: m.name.lower() == rl or m.display_name.lower() == rl, self.guild.members)
        if not member:
            return await interaction.response.send_message(
                view=_reply_view("Member not found!"), ephemeral=True)
        if member.id == self.owner.id:
            return await interaction.response.send_message(
                view=_reply_view("You can't transfer to yourself!"), ephemeral=True)
        if not (member.voice and member.voice.channel and member.voice.channel.id == self.vc.id):
            return await interaction.response.send_message(
                view=_reply_view("That user must be in your voice channel!"), ephemeral=True)

        tc = self.config.get("temp_channels", {})
        tc.pop(str(self.owner.id), None)
        tc[str(member.id)] = self.vc.id
        self.config["temp_channels"] = tc
        _set_guild(self.guild.id, self.config)

        await interaction.response.send_message(
            view=_reply_view(f"{BTN_EMOJI_STR['transfer']} Ownership transferred to **{member.display_name}**"),
            ephemeral=True)

async def _handle_action(interaction: discord.Interaction, action: str):
    member = interaction.user
    guild = interaction.guild

    if not guild:
        return await interaction.response.send_message(
            view=_reply_view("This only works in a server!"), ephemeral=True)

    config = _get_guild(guild.id)
    if not config:
        return await interaction.response.send_message(
            view=_reply_view("VoiceMaster is not configured!"), ephemeral=True)

    temp_channels = config.get("temp_channels", {})

    if action == "claim":
        if not (member.voice and member.voice.channel):
            return await interaction.response.send_message(
                view=_reply_view("You must be in a voice channel to claim!"), ephemeral=True)

        vc = member.voice.channel
        owner_id = None
        for uid, vid in temp_channels.items():
            if vid == vc.id:
                owner_id = uid
                break
        if not owner_id:
            return await interaction.response.send_message(
                view=_reply_view("This is not a temp channel!"), ephemeral=True)

        owner_member = guild.get_member(int(owner_id))
        if (owner_member and owner_member.voice and owner_member.voice.channel
                and owner_member.voice.channel.id == vc.id):
            return await interaction.response.send_message(
                view=_reply_view("The owner is still in the channel!"), ephemeral=True)

        temp_channels.pop(str(owner_id), None)
        temp_channels[str(member.id)] = vc.id
        config["temp_channels"] = temp_channels
        _set_guild(guild.id, config)
        return await interaction.response.send_message(
            view=_reply_view(f"{BTN_EMOJI_STR['claim']} You claimed **{vc.name}**!"), ephemeral=True)

    vc_id = temp_channels.get(str(member.id))
    if not vc_id:
        return await interaction.response.send_message(
            view=_reply_view("You don't own a voice channel!\nJoin the **Join to Create** channel first."),
            ephemeral=True)

    vc = guild.get_channel(vc_id)
    if not vc:
        temp_channels.pop(str(member.id), None)
        config["temp_channels"] = temp_channels
        _set_guild(guild.id, config)
        return await interaction.response.send_message(
            view=_reply_view("Your voice channel no longer exists!"), ephemeral=True)

    try:
        if action == "lock":
            ow = vc.overwrites_for(guild.default_role)
            ow.connect = False
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['lock']} Your channel has been **locked**"), ephemeral=True)

        elif action == "unlock":
            ow = vc.overwrites_for(guild.default_role)
            ow.connect = True
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['unlock']} Your channel has been **unlocked**"), ephemeral=True)

        elif action == "hide":
            ow = vc.overwrites_for(guild.default_role)
            ow.view_channel = False
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['hide']} Your channel is now **hidden**"), ephemeral=True)

        elif action == "unhide":
            ow = vc.overwrites_for(guild.default_role)
            ow.view_channel = True
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(
                view=_reply_view(f"{BTN_EMOJI_STR['unhide']} Your channel is now **visible**"), ephemeral=True)

        elif action == "rename":
            await interaction.response.send_modal(RenameModal(vc))

        elif action == "limit":
            await interaction.response.send_modal(LimitModal(vc))

        elif action in ("mute", "unmute", "deafen", "undeafen", "permit", "ban"):
            await interaction.response.send_modal(UserActionModal(vc, guild, action))

        elif action == "transfer":
            await interaction.response.send_modal(TransferModal(vc, guild, config, member))

    except discord.Forbidden:
        try:
            await interaction.response.send_message(
                view=_reply_view("I don't have permission!"), ephemeral=True)
        except Exception:
            pass
    except Exception as ex:
        try:
            await interaction.response.send_message(
                view=_reply_view(f"Error: `{ex}`"), ephemeral=True)
        except Exception:
            pass

class VMInterfaceView(ui.LayoutView):
    def __init__(self, enabled_buttons: list[str], bot_name: str = ""):
        super().__init__(timeout=None)
        self.enabled_buttons = enabled_buttons
        self.bot_name = bot_name
        self._build()

    def _build(self):
        self.clear_items()
        container = ui.Container(accent_colour=BLACK)

        container.add_item(ui.TextDisplay(content="### VoiceMaster Interface"))
        container.add_item(ui.Separator())

        container.add_item(ui.TextDisplay(
            content="Use the buttons below to manage your voice channel."))
        container.add_item(ui.Separator(visible=True))

        desc_lines = ["**__Control Buttons__**"]
        for btn in self.enabled_buttons:
            desc_lines.append(f"{BTN_EMOJI_STR.get(btn, '')} - {BTN_DESC.get(btn, '')}")
        container.add_item(ui.TextDisplay(content="\n".join(desc_lines)))
        container.add_item(ui.Separator())

        chunks = [self.enabled_buttons[i:i+5] for i in range(0, len(self.enabled_buttons), 5)]
        for chunk in chunks:
            row = ui.ActionRow()
            for btn_name in chunk:
                row.add_item(ui.Button(
                    emoji=BTN_EMOJI[btn_name],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"vm_btn_{btn_name}",
                ))
            container.add_item(row)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid.startswith("vm_btn_"):
            action = cid[7:]
            await _handle_action(interaction, action)
        return False

class SetupView(ui.LayoutView):
    def __init__(self, ctx, bot):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = bot
        self._build()

    def _build(self):
        self.clear_items()
        container = ui.Container(accent_colour=BLACK)

        container.add_item(ui.TextDisplay(content="### VoiceMaster Setup"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(content=(
            "**Select the buttons you want to enable for the VoiceMaster system.**\n\n"
            "Select `Enable All` to enable everything,\n"
            "or choose specific buttons from the dropdown."
        )))
        container.add_item(ui.Separator())

        opts = []
        for key, label in BTN_LABELS.items():
            opts.append(discord.SelectOption(label=label, value=key, emoji=BTN_EMOJI[key]))
        opts.append(discord.SelectOption(label="Enable All", value="enable_all"))

        select = ui.Select(
            placeholder="Select buttons to enable...",
            min_values=1, max_values=len(opts),
            options=opts, custom_id="vm_setup_select",
        )
        row = ui.ActionRow()
        row.add_item(select)
        container.add_item(row)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid == "vm_setup_select":
            await self._on_select(interaction)
        return False

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                view=_reply_view("This is not your setup!"), ephemeral=True)

        selected = interaction.data["values"]
        enabled = ALL_BUTTONS.copy() if "enable_all" in selected else [v for v in selected if v in ALL_BUTTONS]

        if not enabled:
            return await interaction.response.send_message(
                view=_reply_view("No valid buttons selected!"), ephemeral=True)

        guild = interaction.guild
        config = _get_guild(guild.id) or {}

        await interaction.response.defer()

        try:
            category = await guild.create_category("VoiceMaster")

            trigger_vc = await guild.create_voice_channel(
                name="Join to Create", category=category)

            interface_ch = await guild.create_text_channel(
                name="interface", category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True, send_messages=False)
                })

            bot_name = self.bot.user.name if self.bot.user else "Bot"
            config.update({
                "trigger_vc": trigger_vc.id,
                "interface_ch": interface_ch.id,
                "category": category.id,
                "enabled_buttons": enabled,
                "temp_channels": config.get("temp_channels", {}),
                "bot_name": bot_name,
            })
            _set_guild(guild.id, config)

            iface_view = VMInterfaceView(enabled, bot_name)
            await interface_ch.send(view=iface_view)
            self.bot.add_view(iface_view)

            confirm = ui.LayoutView(timeout=None)
            cc = ui.Container(accent_colour=BLACK)
            cc.add_item(ui.TextDisplay(content="### VoiceMaster Setup Complete"))
            cc.add_item(ui.Separator())
            cc.add_item(ui.TextDisplay(content=(
                f"**Trigger VC:** {trigger_vc.mention}\n"
                f"**Interface:** {interface_ch.mention}\n"
                f"**Category:** `{category.name}`\n"
                f"**Buttons:** `{len(enabled)}`"
            )))
            confirm.add_item(cc)
            await interaction.followup.send(view=confirm)

        except Exception as ex:
            await interaction.followup.send(view=_reply_view(f"Setup failed: `{ex}`"))

class ReconfigView(ui.LayoutView):
    def __init__(self, ctx, bot, config):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = bot
        self.config = config
        self._build()

    def _build(self):
        self.clear_items()
        container = ui.Container(accent_colour=BLACK)

        container.add_item(ui.TextDisplay(content="### Reconfigure Buttons"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(content="Select which buttons to enable in the interface."))
        container.add_item(ui.Separator())

        opts = []
        current = self.config.get("enabled_buttons", [])
        for key, label in BTN_LABELS.items():
            opts.append(discord.SelectOption(
                label=label, value=key, emoji=BTN_EMOJI[key],
                default=key in current))
        opts.append(discord.SelectOption(label="Enable All", value="enable_all"))

        select = ui.Select(
            placeholder="Select buttons...",
            min_values=1, max_values=len(opts),
            options=opts, custom_id="vm_reconfig_select",
        )
        row = ui.ActionRow()
        row.add_item(select)
        container.add_item(row)

        container.add_item(ui.Separator())
        bot_name = self.bot.user.name if self.bot.user else "Bot"
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid == "vm_reconfig_select":
            await self._on_select(interaction)
        return False

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                view=_reply_view("This is not your panel!"), ephemeral=True)

        selected = interaction.data["values"]
        enabled = ALL_BUTTONS.copy() if "enable_all" in selected else [v for v in selected if v in ALL_BUTTONS]

        await interaction.response.defer()

        self.config["enabled_buttons"] = enabled
        _set_guild(interaction.guild.id, self.config)

        interface_ch = interaction.guild.get_channel(self.config.get("interface_ch", 0))
        if interface_ch:
            try:
                await interface_ch.purge(limit=10)
                bot_name = self.config.get("bot_name", self.bot.user.name if self.bot.user else "Bot")
                new_view = VMInterfaceView(enabled, bot_name)
                await interface_ch.send(view=new_view)
                self.bot.add_view(new_view)
            except Exception as e:
                print(f"[VoiceMaster] Error updating interface: {e}")

        await interaction.followup.send(
            view=_reply_view(f"Buttons updated! `{len(enabled)}` buttons enabled."), ephemeral=True)

class ConfigView(ui.LayoutView):
    def __init__(self, config, guild, bot_name):
        super().__init__(timeout=None)
        self._build(config, guild, bot_name)

    def _build(self, config, guild, bot_name):
        self.clear_items()
        container = ui.Container(accent_colour=BLACK)

        trigger_vc = guild.get_channel(config.get("trigger_vc", 0))
        interface_ch = guild.get_channel(config.get("interface_ch", 0))
        category = guild.get_channel(config.get("category", 0))
        enabled = config.get("enabled_buttons", [])
        temp_count = len(config.get("temp_channels", {}))

        container.add_item(ui.TextDisplay(content="### VoiceMaster Configuration"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(content=(
            f"**Trigger VC:** {trigger_vc.mention if trigger_vc else '`Not found`'}\n"
            f"**Interface:** {interface_ch.mention if interface_ch else '`Not found`'}\n"
            f"**Category:** {f'`{category.name}`' if category else '`Not found`'}\n"
            f"**Active Channels:** `{temp_count}`\n"
            f"**Enabled Buttons:** `{len(enabled)}/{len(ALL_BUTTONS)}`\n\n"
            + (", ".join(BTN_EMOJI_STR.get(b, b) for b in enabled) if enabled else "None")
        )))
        self.add_item(container)

class ResetConfirmView(ui.LayoutView):
    def __init__(self, ctx, config, bot_name):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.config = config
        self.bot_name = bot_name
        self._build()

    def _build(self):
        self.clear_items()
        container = ui.Container(accent_colour=BLACK)

        container.add_item(ui.TextDisplay(content="### Reset VoiceMaster?"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(content=(
            "This will delete:\n"
            "- All temp voice channels\n"
            "- Interface channel\n"
            "- Trigger VC\n"
            "- VoiceMaster category\n\n"
            "**Are you sure?**"
        )))
        container.add_item(ui.Separator())

        row = ui.ActionRow()
        row.add_item(ui.Button(
            label="Yes, Reset", style=discord.ButtonStyle.danger, custom_id="vm_reset_yes"))
        row.add_item(ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary, custom_id="vm_reset_no"))
        container.add_item(row)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")

        if cid == "vm_reset_yes":
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message(
                    view=_reply_view("Not your panel!"), ephemeral=True) or False

            await interaction.response.defer()
            guild = interaction.guild

            for uid, vc_id in list(self.config.get("temp_channels", {}).items()):
                vc = guild.get_channel(vc_id)
                if vc:
                    try:
                        await vc.delete()
                    except Exception:
                        pass

            for key in ("interface_ch", "trigger_vc", "category"):
                ch = guild.get_channel(self.config.get(key, 0))
                if ch:
                    try:
                        await ch.delete()
                    except Exception:
                        pass

            _del_guild(guild.id)
            await interaction.followup.send(
                view=_reply_view("VoiceMaster has been reset successfully"))

        elif cid == "vm_reset_no":
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message(
                    view=_reply_view("Not your panel!"), ephemeral=True) or False

            await interaction.response.edit_message(view=_reply_view("Reset cancelled."))

        return False

class VoiceMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        data = _load()
        count = 0
        for guild_id, config in data.items():
            enabled = config.get("enabled_buttons", ALL_BUTTONS)
            bot_name = config.get("bot_name", self.bot.user.name if self.bot.user else "Bot")
            if enabled:
                view = VMInterfaceView(enabled, bot_name)
                self.bot.add_view(view)
                count += 1
        print(f"[VoiceMaster] Registered {count} persistent view(s)")

    @commands.hybrid_group(name="voicemaster", aliases=["vm"], description="Show the VoiceMaster main panel.", invoke_without_command=True, fallback="panel")
    @commands.guild_only()
    async def voicemaster(self, ctx: commands.Context):
        prefix = ctx.prefix
        bot_name = self.bot.user.name if self.bot.user else "Bot"

        v = ui.LayoutView(timeout=None)
        c = ui.Container(accent_colour=BLACK)
        c.add_item(ui.TextDisplay(content=f"### {bot_name} VoiceMaster"))
        c.add_item(ui.Separator())
        c.add_item(ui.TextDisplay(content=(
            f"`{prefix}vm setup` — Setup VoiceMaster system\n"
            f"`{prefix}vm config` — View current configuration\n"
            f"`{prefix}vm reset` — Reset VoiceMaster system\n"
            f"`{prefix}vm buttons` — Reconfigure buttons"
        )))
        v.add_item(c)
        await ctx.send(view=v)

    @voicemaster.command(name="setup", description="Set up the join-to-create voice hub.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vm_setup(self, ctx: commands.Context):
        existing = _get_guild(ctx.guild.id)
        if existing:
            return await ctx.send(view=_reply_view(
                f"VoiceMaster already configured! Use `{ctx.prefix}vm reset` first."))

        view = SetupView(ctx, self.bot)
        await ctx.send(view=view)

    @voicemaster.command(name="buttons", description="Post the VoiceMaster control panel.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vm_buttons(self, ctx: commands.Context):
        config = _get_guild(ctx.guild.id)
        if not config:
            return await ctx.send(view=_reply_view(
                f"VoiceMaster not configured! Use `{ctx.prefix}vm setup`"))

        view = ReconfigView(ctx, self.bot, config)
        await ctx.send(view=view)

    @voicemaster.command(name="config", description="View the current VoiceMaster configuration.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def vm_config(self, ctx: commands.Context):
        config = _get_guild(ctx.guild.id)
        bot_name = self.bot.user.name if self.bot.user else "Bot"

        if not config:
            return await ctx.send(view=_reply_view(
                f"VoiceMaster not configured! Use `{ctx.prefix}vm setup`"))

        view = ConfigView(config, ctx.guild, bot_name)
        await ctx.send(view=view)

    @voicemaster.command(name="reset", description="Reset all VoiceMaster settings.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def vm_reset(self, ctx: commands.Context):
        config = _get_guild(ctx.guild.id)
        bot_name = self.bot.user.name if self.bot.user else "Bot"

        if not config:
            return await ctx.send(view=_reply_view("VoiceMaster is not configured!"))

        view = ResetConfirmView(ctx, config, bot_name)
        await ctx.send(view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        config = _get_guild(member.guild.id)
        if not config:
            return

        trigger_id = config.get("trigger_vc")
        category_id = config.get("category")
        temp_channels = config.get("temp_channels", {})
        changed = False

        if after.channel and after.channel.id == trigger_id:
            existing = member.guild.get_channel(temp_channels.get(str(member.id), 0))
            try:
                if existing:
                    await member.move_to(existing)
                else:
                    category = member.guild.get_channel(category_id)
                    new_vc = await member.guild.create_voice_channel(
                        name=f"{member.display_name}'s Channel",
                        category=category,
                        reason="VoiceMaster: join to create",
                    )
                    await new_vc.set_permissions(member, connect=True, manage_channels=True, move_members=True)
                    await member.move_to(new_vc)
                    temp_channels[str(member.id)] = new_vc.id
                    changed = True
            except Exception as e:
                print(f"[VoiceMaster] Error: {e}")

        if before.channel and before.channel.id != trigger_id and before.channel != after.channel:
            if before.channel.id in temp_channels.values() and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="VoiceMaster: empty temp channel")
                except Exception:
                    pass
                for uid, vid in list(temp_channels.items()):
                    if vid == before.channel.id:
                        temp_channels.pop(uid, None)
                        changed = True

        if changed:
            config["temp_channels"] = temp_channels
            _set_guild(member.guild.id, config)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        config = _get_guild(channel.guild.id)
        if not config:
            return
        temp = config.get("temp_channels", {})
        stale = [uid for uid, vid in temp.items() if vid == channel.id]
        if stale:
            for uid in stale:
                temp.pop(uid, None)
            config["temp_channels"] = temp
            _set_guild(channel.guild.id, config)

async def setup(bot):
    await bot.add_cog(VoiceMaster(bot))

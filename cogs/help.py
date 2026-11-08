import logging

import discord
from discord import SelectOption
from discord.ext import commands
from discord.ui import (
    ActionRow, Button, Container, LayoutView, Section,
    Select, Separator, TextDisplay, Thumbnail,
)

from utils.config import BOT_NAME, INVITE_URL, SUPPORT_SERVER, WEBSITE
from XEON.emojis import E as _EMGR, partial as _partial

ACCENT_COLOR = discord.Colour(0x000000)
ARROW = "»"

CATEGORIES = [
    {
        "key": "security", "label": "Security", "emoji": "HELP_SECURITY",
        "description": "Antinuke, whitelist and server protection.",
        "sections": [("Antinuke", ["antinuke"])],
    },
    {
        "key": "permit", "label": "Permit Commands", "emoji": "HELP_PERMIT",
        "description": "Extra owners and ignore lists.",
        "sections": [
            ("Extraowner", ["extraowner"]),
            ("Ignore", ["ignore", "unignore", "ignorelist"]),
        ],
        "extra": {"extraowner": ["set", "reset", "view", "clear"]},
    },
    {
        "key": "automod", "label": "Automod", "emoji": "HELP_AUTOMOD",
        "description": "Spam, links, invites and word filters.",
        "sections": [("Automod", ["automod"])],
    },
    {
        "key": "moderation", "label": "Moderation", "emoji": "HELP_MODERATION",
        "description": "Bans, mutes, locks, purge and lists.",
        "sections": [
            ("Moderation", [
                "ban", "unban", "softban", "fakeban", "kick", "mute", "unmute", "nick",
                "nuke", "snipe", "unbanall",
            ]),
            ("Lock and Hide", [
                "lock", "unlock", "lockall", "unlockall", "hide", "unhide",
                "hideall", "unhideall", "slowmode", "unslowmode",
            ]),
            ("Channel", ["channel"]),
            ("Purge", [
                "clear", "clearall", "clearuser", "clearbots", "clearembed",
                "clearmentions", "clearreactions", "clearfiles", "clearimages",
                "clearemoji", "clearcontain",
            ]),
            ("List", ["list"]),
        ],
    },
    {
        "key": "general", "label": "General", "emoji": "HELP_GENERAL",
        "description": "Bot info, avatars and member counts.",
        "sections": [
            ("General", [
                "ping", "pong", "stats", "uptime", "system", "afk", "membercount",
                "boostcount", "joinedat", "avatar", "banner", "servericon",
                "serverbanner", "invite", "users",
            ]),
        ],
    },
    {
        "key": "utility", "label": "Utility", "emoji": "HELP_UTILITY",
        "description": "Info commands, embeds and trackers.",
        "sections": [
            ("Info", ["serverinfo", "userinfo", "roleinfo", "channelinfo"]),
            ("Embed", ["embed"]),
            ("Tracker", [
                "messages", "addmessages", "removemessages", "resetmessages",
                "blacklistchannel", "unblacklistchannel", "blacklistedchannels",
                "invites", "tracker",
            ]),
        ],
    },
    {
        "key": "automations", "label": "Automations", "emoji": "HELP_AUTOMATIONS",
        "description": "Autoreact and autorole.",
        "sections": [("Autoreact", ["autoreact"]), ("Autorole", ["autorole"])],
    },
    {
        "key": "autoresponders", "label": "Autoresponders", "emoji": "HELP_AUTORESPONDERS",
        "description": "Keyword based automatic replies.",
        "sections": [("Autoresponder", ["autoresponder"])],
    },
    {
        "key": "roles", "label": "Roles", "emoji": "HELP_CUSTOMROLE",
        "description": "Role management and reaction roles.",
        "sections": [
            ("Role", ["role"]),
            ("Remove Role", ["rrole", "rrolehumans", "rrolebots", "rroleall"]),
            ("Reaction Roles", ["reactionrole"]),
        ],
    },
    {
        "key": "greetings", "label": "Greetings", "emoji": "HELP_GREETINGS",
        "description": "Welcome messages for new members.",
        "sections": [("Greet", ["greet"])],
    },
    {
        "key": "giveaways", "label": "Giveaways", "emoji": "GIFTBOX",
        "description": "Host and manage giveaways.",
        "sections": [("Giveaway", ["giveaway", "gstart", "gend", "greroll", "glist", "gdelete"])],
    },
    {
        "key": "music", "label": "Music", "emoji": "HELP_MUSIC",
        "description": "Play, queue and control music.",
        "sections": [
            ("Playback", [
                "play", "join", "stop", "pause", "resume", "skip", "volume",
                "loop", "shuffle", "autoplay", "247",
            ]),
            ("Queue", ["queue", "nowplaying"]),
        ],
    },
    {
        "key": "voice", "label": "Voice Commands", "emoji": "HELP_VOICE",
        "description": "Join-to-create voice channels.",
        "sections": [("Voicemaster", ["voicemaster"])],
    },
    {
        "key": "tickets", "label": "Tickets", "emoji": "HELP_TICKETS",
        "description": "Support and report ticket system.",
        "sections": [("Ticket", ["ticket", "tclose", "tdelete"])],
    },
    {
        "key": "logging", "label": "Logging", "emoji": "HELP_LOGGING",
        "description": "Per-event server logging.",
        "sections": [("Logging", ["logging"])],
    },
    {
        "key": "settings", "label": "Bot Settings", "emoji": "HELP_SETTINGS",
        "description": "Prefix, custom bot profile and noprefix.",
        "sections": [
            ("Prefix", ["prefix", "setprefix", "resetprefix"]),
            ("Custom Bot", ["custombot", "bbio", "bpfp", "bbanner", "bnameplate"]),
            ("Noprefix", ["np"]),
        ],
    },
]

CATEGORY_BY_KEY = {c["key"]: c for c in CATEGORIES}


def _expand(command: commands.Command) -> list[str]:
    names = [command.qualified_name]
    if isinstance(command, commands.Group):
        for sub in sorted(command.commands, key=lambda c: c.name):
            if not sub.hidden:
                names.extend(_expand(sub))
    return names


def category_sections(bot: commands.Bot, category: dict) -> list[tuple[str, list[str]]]:
    extra = category.get("extra", {})
    result = []
    for title, roots in category["sections"]:
        names: list[str] = []
        for root in roots:
            command = bot.get_command(root)
            if command is None or command.hidden:
                continue
            names.extend(_expand(command))
            for sub in extra.get(root, []):
                full = f"{root} {sub}"
                if full not in names:
                    names.append(full)
        if names:
            result.append((title, names))
    return result


def visible_categories(bot: commands.Bot) -> list[dict]:
    return [c for c in CATEGORIES if category_sections(bot, c)]


def total_commands(bot: commands.Bot) -> int:
    seen = set()
    for category in CATEGORIES:
        for _, names in category_sections(bot, category):
            seen.update(names)
    return len(seen)


def _emoji_text(key: str) -> str:
    return _EMGR[key]


def _option_emoji(key: str):
    return _partial(key)


class HelpView(LayoutView):
    def __init__(self, bot: commands.Bot, author: discord.abc.User, prefix: str, start: str | None = None):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.prefix = prefix
        self.message: discord.Message | None = None
        self.categories = visible_categories(bot)
        self.index = 0
        self.show(start)

    def show(self, key: str | None):
        self.clear_items()
        if key is None:
            self.add_item(self.home_container())
            self.add_item(ActionRow(self.make_select()))
            return
        self.index = next((i for i, c in enumerate(self.categories) if c["key"] == key), 0)
        self.add_item(self.category_container(self.categories[self.index]))
        self.add_item(self.nav_row())
        self.add_item(ActionRow(self.make_select()))

    def make_select(self) -> Select:
        options = [
            SelectOption(
                label=c["label"], value=c["key"],
                description=c["description"][:100],
                emoji=_option_emoji(c["emoji"]),
            )
            for c in self.categories
        ]
        select = Select(placeholder="↳ Select a module to see", options=options[:25])
        select.callback = self.on_select
        return select

    def home_container(self) -> Container:
        bot_name = BOT_NAME
        lines = [
            f"### Hey , I'm **{bot_name}**",
            f"- **My prefix for this server is ** `{self.prefix}`",
            f"- **Type `{self.prefix}help [context]` for more**",
            f"- **Total commands:** `{total_commands(self.bot)}`",
        ]
        modules = "\n".join(
            f"> **{_emoji_text(c['emoji'])} `{ARROW}` {c['label']}**"
            for c in self.categories
        )
        header = Section(
            TextDisplay("\n".join(lines)),
            accessory=Thumbnail(
                media=discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url),
                description=bot_name,
            ),
        )
        tip = (
            "** __Pro Tip__**\n"
            f"Embeds feel hard? It doesn't bite! {_emoji_text('HELP_CUTE')}\n"
            f"Build them easily with `{self.prefix}embed create`"
        )
        links = (
            f"**{_emoji_text('HELP_LINK')} __Links__**\n"
            f"[Invite me]({INVITE_URL})  •  [Support]({SUPPORT_SERVER})  •  [Website]({WEBSITE})"
        )
        return Container(
            header,
            TextDisplay(modules),
            TextDisplay(tip),
            TextDisplay(links),
            accent_color=ACCENT_COLOR,
        )

    def category_container(self, category: dict) -> Container:
        blocks = [f"### {category['label']}"]
        for title, names in category_sections(self.bot, category):
            joined = " , ".join(f"`{n}`" for n in names)
            blocks.append(f"**__{title}__**\n{joined}")
        text = "\n".join(blocks)
        if len(text) > 3600:
            text = text[:3560].rsplit(" , ", 1)[0] + "`"
        return Container(
            TextDisplay(text),
            accent_color=ACCENT_COLOR,
        )

    def nav_row(self) -> ActionRow:
        total = len(self.categories)
        prev_btn = Button(emoji=_partial("PREV"), style=discord.ButtonStyle.secondary)
        prev_btn.callback = self.on_prev
        delete_btn = Button(emoji=_partial("DELETE"), style=discord.ButtonStyle.secondary)
        delete_btn.callback = self.on_delete
        next_btn = Button(emoji=_partial("NEXT"), style=discord.ButtonStyle.secondary)
        next_btn.callback = self.on_next
        home_btn = Button(emoji=_partial("FILTER"), style=discord.ButtonStyle.secondary)
        home_btn.callback = self.on_home
        page_btn = Button(
            label=f"{self.index + 1}/{total}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        return ActionRow(prev_btn, delete_btn, next_btn, home_btn, page_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"This help menu isn't for you. Run `{self.prefix}help` yourself.",
                ephemeral=True,
            )
            return False
        return True

    async def on_select(self, interaction: discord.Interaction):
        self.show(interaction.data["values"][0])
        await interaction.response.edit_message(view=self)

    async def on_prev(self, interaction: discord.Interaction):
        key = self.categories[(self.index - 1) % len(self.categories)]["key"]
        self.show(key)
        await interaction.response.edit_message(view=self)

    async def on_next(self, interaction: discord.Interaction):
        key = self.categories[(self.index + 1) % len(self.categories)]["key"]
        self.show(key)
        await interaction.response.edit_message(view=self)

    async def on_home(self, interaction: discord.Interaction):
        self.show(None)
        await interaction.response.edit_message(view=self)

    async def on_delete(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()

    async def on_timeout(self):
        if not self.message:
            return
        for child in self.walk_children():
            if isinstance(child, (Button, Select)):
                child.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


def _command_detail(ctx: commands.Context, command: commands.Command) -> LayoutView:
    usage = f"{ctx.prefix}{command.qualified_name} {command.signature}".strip()
    lines = [
        f"### {command.qualified_name}",
        f"{_emoji_text('ARROW')} **Usage:** `{usage}`",
    ]
    if command.aliases:
        lines.append(f"{_emoji_text('ARROW')} **Aliases:** {' , '.join(f'`{a}`' for a in command.aliases)}")
    description = command.short_doc or command.help
    if description:
        lines.append(f"{_emoji_text('ARROW')} **About:** {description}")
    if isinstance(command, commands.Group) and command.commands:
        subs = " , ".join(f"`{c.qualified_name}`" for c in sorted(command.commands, key=lambda c: c.name) if not c.hidden)
        if subs:
            lines.append(f"\n**__Subcommands__**\n{subs}")
    view = LayoutView(timeout=120)
    view.add_item(Container(
        TextDisplay("\n".join(lines)),
        accent_color=ACCENT_COLOR,
    ))
    return view


class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        bot.remove_command("help")

    @commands.command(name="help", aliases=["h", "menu", "commands"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def help_command(self, ctx: commands.Context, *, query: str = None):
        try:
            start = None
            if query:
                q = query.strip().lower()
                for category in visible_categories(self.bot):
                    if q in (category["key"], category["label"].lower()):
                        start = category["key"]
                        break
                else:
                    command = self.bot.get_command(q)
                    if command is not None and not command.hidden:
                        return await ctx.send(view=_command_detail(ctx, command))
            view = HelpView(self.bot, ctx.author, ctx.prefix, start)
            view.message = await ctx.send(view=view)
        except Exception as error:
            self.logger.error("Help command error: %s", error, exc_info=True)
            await ctx.send("An error occurred while loading the help menu.")


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))

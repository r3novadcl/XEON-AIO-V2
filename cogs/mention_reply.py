import discord
from discord.ext import commands
from utils.config import BOT_NAME, INVITE_URL as INVITE_LINK, SUPPORT_SERVER as SUPPORT_LINK
from discord import ui
from utils import emojis as E


DEFAULT_ACCENT = discord.Colour(0x000000)

FOOTER_TEXT = f"Powered By {BOT_NAME} Devs"


class MentionReply(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        stripped = message.content.strip()
        if stripped not in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            return

        try:
            prefix = await self.bot.get_prefix(message)
            if isinstance(prefix, (list, tuple)):
                prefix = [p for p in prefix if not p.startswith("<@")]
                prefix = prefix[0] if prefix else "&"
        except Exception:
            prefix = "&"

        view = ui.LayoutView(timeout=None)
        c = ui.Container(accent_color=DEFAULT_ACCENT)

        A = E.ARROW
        header = ui.Section(
            ui.TextDisplay(
                f"### Hey, I'm **{BOT_NAME}**\n"
                f"{A} **Server Prefix:** `{prefix}`\n"
                f"{A} **Get Started:** `{prefix}help`\n"
                f"{A} **Support:** [Join Support Server]({SUPPORT_LINK})"
            ),
            accessory=ui.Thumbnail(media=discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url)),
        )
        c.add_item(header)
        c.add_item(ui.Separator(visible=True))

        c.add_item(ui.ActionRow(
            ui.Button(
                label="Invite Me",
                style=discord.ButtonStyle.link,
                url=INVITE_LINK,
            ),
            ui.Button(
                label="Support Server",
                style=discord.ButtonStyle.link,
                url=SUPPORT_LINK,
            ),
        ))

        c.add_item(ui.Separator(visible=True))


        view.add_item(c)

        try:
            await message.channel.send(view=view)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[MentionReply] Error: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MentionReply(bot))

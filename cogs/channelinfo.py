import discord
from discord.ext import commands
from utils import emojis as E

BLACK = discord.Colour(0x000000)


class ChannelInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="channelinfo", aliases=["ci", "cinfo", "chinfo"])
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        channel  = channel or ctx.channel
        created  = discord.utils.format_dt(channel.created_at, style="F")
        created_r= discord.utils.format_dt(channel.created_at, style="R")
        category = channel.category.name if channel.category else "None"
        slowmode = f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Disabled"
        nsfw     = "Yes" if channel.is_nsfw() else "No"
        topic    = channel.topic or "No topic set"
        position = channel.position + 1

        ow_count = len(channel.overwrites)

        container = discord.ui.Container(accent_color=BLACK)
        container.add_item(discord.ui.TextDisplay(
            content=f"### {E.CHANNEL} #{channel.name}'s Info"
        ))
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(
            content=f"### {E.INFO} About Channel"
        ))
        container.add_item(discord.ui.TextDisplay(
            content=(
                f"{E.ARROW} **Name:** {channel.mention}\n"
                f"{E.ARROW} **ID:** `{channel.id}`\n"
                f"{E.ARROW} **Category:** `{category}`\n"
                f"{E.ARROW} **Position:** `{position}`\n"
                f"{E.ARROW} **Type:** `Text Channel`\n"
                f"{E.ARROW} **NSFW:** `{nsfw}`\n"
                f"{E.ARROW} **Slowmode:** `{slowmode}`\n"
                f"{E.ARROW} **Topic:** {topic}\n"
                f"{E.ARROW} **Created:** {created} ({created_r})\n"
                f"{E.ARROW} **Overwrites:** `{ow_count}`"
            )
        ))
        container.add_item(discord.ui.Separator())

        ts = discord.utils.format_dt(ctx.message.created_at, style="f")
        container.add_item(discord.ui.TextDisplay(
            content=f"Requested by {ctx.author.mention} | {ts}"
        ))

        view = discord.ui.LayoutView(timeout=None)
        view.add_item(container)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(ChannelInfo(bot))

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TARGET_CHANNEL_IDS = {
    1397093836865671319,
    1488315991178874880,
}
REACTION_EMOJI = os.getenv("REACTION_EMOJI", "📸")
TIMEZONE_NAME = os.getenv("TIMEZONE_NAME", "Asia/Riyadh")
PREFIX = os.getenv("PREFIX", "!")
DATA_FILE = Path("streaks.json")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


def load_data():
    if not DATA_FILE.exists():
        return {}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_data(data):
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_local():
    return datetime.now(ZoneInfo(TIMEZONE_NAME))


def is_image_attachment(att: discord.Attachment) -> bool:
    if att.content_type and att.content_type.startswith("image/"):
        return True

    filename = att.filename.lower()
    image_exts = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
        ".heic",
    )
    return filename.endswith(image_exts)


def message_has_image(message: discord.Message) -> bool:
    return any(is_image_attachment(att) for att in message.attachments)


def get_record(data, user_id: int):
    key = str(user_id)
    if key not in data:
        data[key] = {
            "streak": 0,
            "longest": 0,
            "last_date": None,
        }
    return data[key]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Watching channels: {sorted(TARGET_CHANNEL_IDS)}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id in TARGET_CHANNEL_IDS and message_has_image(message):
        try:
            await message.add_reaction(REACTION_EMOJI)
        except discord.HTTPException:
            pass

        data = load_data()
        record = get_record(data, message.author.id)

        today = now_local().date()
        yesterday = today - timedelta(days=1)
        last_date_str = record["last_date"]

        # ينحسب مرة واحدة فقط يوميًا مهما كان عدد الصور
        if last_date_str != today.isoformat():
            if last_date_str == yesterday.isoformat():
                record["streak"] += 1
            else:
                record["streak"] = 1

            record["last_date"] = today.isoformat()
            record["longest"] = max(record["longest"], record["streak"])
            save_data(data)

    await bot.process_commands(message)


@bot.command(name="streak")
async def streak(ctx: commands.Context, member: discord.Member | None = None):
    member = member or ctx.author
    data = load_data()
    record = data.get(
        str(member.id),
        {"streak": 0, "longest": 0, "last_date": None},
    )

    await ctx.send(
        f"**{member.display_name}**\n"
        f"Current streak: **{record['streak']}** days\n"
        f"Longest streak: **{record['longest']}** days\n"
        f"Last counted day: **{record['last_date'] or 'Never'}**"
    )


@bot.command(name="leaderboard")
async def leaderboard(ctx: commands.Context):
    if ctx.guild is None:
        await ctx.send("This command only works inside a server.")
        return

    data = load_data()
    if not data:
        await ctx.send("No streaks recorded yet.")
        return

    sorted_users = sorted(
        data.items(),
        key=lambda item: (
            item[1].get("streak", 0),
            item[1].get("longest", 0),
        ),
        reverse=True,
    )[:10]

    lines = []
    for index, (user_id, record) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        lines.append(
            f"{index}. {name} — {record.get('streak', 0)} days "
            f"(best: {record.get('longest', 0)})"
        )

    await ctx.send("**Photo Streak Leaderboard**\n" + "\n".join(lines))


print("DISCORD_TOKEN exists:", bool(TOKEN))
print("DISCORD_TOKEN length:", len(TOKEN))

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

if not TARGET_CHANNEL_IDS:
    raise RuntimeError("TARGET_CHANNEL_IDS is missing.")

bot.run(TOKEN)
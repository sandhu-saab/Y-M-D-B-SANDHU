import re
import aiohttp
import asyncio
from pyrogram import Client, filters, enums
from plugins.Dreamxfutures.Imdbposter import get_movie_details
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LOG_CHANNEL
from collections import defaultdict

media_filter = filters.document | filters.video | filters.audio

caption_template = """<b>𝖭𝖤𝖶 {kind} 𝖠𝖣𝖣𝖤𝖣 ✅</b>

🎬 <b>Tɪᴛʟᴇ: {title} {year}</b>
🎧 <b>Aᴜᴅɪᴏ: {language}</b>
🎞️ <b>Gᴇɴʀᴇꜱ: {genres}</b>

<blockquote>✨ Telegram Files ✨</blockquote>

{links}

<blockquote>〽️ Powered by @OttSandhu</blockquote>"""

movie_files = defaultdict(list)
notified_movies = set()
processing_movies = set()
POST_DELAY = 10

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu",
    "Malayalam", "Kannada", "Marathi", "Punjabi", "Gujrati", "Gujarati", "Korean",
    "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese",
    "Russian", "Japanese", "Odia", "Assamese", "Urdu"
]


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media:
            break
    else:
        return

    media.file_type = file_type
    media.caption = message.caption

    success, is_allowed = await save_file(media)
    if success and is_allowed and await db.movie_update_status(bot.me.id):
        await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    try:
        file_name = await clean_filename(media.file_name)
        caption = await clean_caption(media.caption)
        year = extract_year(caption)
        season = extract_season(caption) or extract_season(file_name)

        if year:
            file_name = file_name[: file_name.find(year) + 4]
        elif season:
            file_name = file_name[: file_name.find(season) + 1]

        quality = await get_quality(caption) or "HDRip"
        language = extract_languages(caption)

        file_id, file_ref = unpack_new_file_id(media.file_id)
        file_size = format_file_size(media.file_size)

        movie_files[file_name].append({
            "file_id": file_id,
            "caption": caption,
            "quality": quality,
            "language": language,
            "year": year,
            "file_size": file_size,
        })

        if file_name in processing_movies:
            return
        processing_movies.add(file_name)

        await asyncio.sleep(POST_DELAY)

        if file_name in movie_files:
            await send_movie_update(bot, file_name, movie_files[file_name])
            del movie_files[file_name]

        processing_movies.remove(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        print(f"Error in queue_movie_file: {e}")
        await bot.send_message(LOG_CHANNEL, f"Error in queue_movie_file: <code>{e}</code>")


async def send_movie_update(bot, file_name, files):
    try:
        if file_name in notified_movies:
            return
        notified_movies.add(file_name)

        imdb = await get_movie_details(file_name)
        title = imdb.get("title", file_name)
        rating = imdb.get("rating", "N/A")
        genres = imdb.get("genres") or "Unknown"
        kind = imdb.get("kind", "Movie").upper().replace(" ", "_")
        if kind == "TV_SERIES":
            kind = "SERIES"

        poster_img = await fetch_jisshu_poster(title)

        languages = set()
        for file in files:
            if file["language"] and file["language"] != "Not Idea":
                languages.update(file["language"].split(", "))
        language = ", ".join(sorted(languages)) or "Not Idea"

        # Quality-wise links sorted & line gap
        def quality_sort_key(file):
            q = file.get("quality", "").lower()
            try:
                return int(re.search(r"\d+", q).group())
            except:
                return 9999

        sorted_files = sorted(files, key=quality_sort_key)
        max_quality_len = max(len(f['quality']) for f in sorted_files) if sorted_files else 0

        quality_text = ""
        for file in sorted_files:
            quality = file["quality"].ljust(max_quality_len)
            size = file["file_size"]
            file_id = file["file_id"]
            link = f"<a href='https://t.me/IMDB004_BOT?start=file_0_{file_id}'>{size}</a>"
            quality_text += f"📦 <b>{quality}</b> : {link}\n\n"

        caption_data = {
            "kind": kind,
            "title": title,
            "year": files[0]["year"] or "",
            "quality": files[0]["quality"],
            "language": language,
            "genres": genres,
            "links": quality_text.strip(),
        }

        full_caption = caption_template.format_map(caption_data)

        await bot.send_photo(
            chat_id=MOVIE_UPDATE_CHANNEL,
            photo=poster_img or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg",
            caption=full_caption,
            parse_mode=enums.ParseMode.HTML,
        )

    except Exception as e:
        print("Error in send_movie_update:", e)
        await bot.send_message(LOG_CHANNEL, f"Error in send_movie_update: <code>{e}</code>")


# Jisshu Poster System
async def fetch_jisshu_poster(title):
    async with aiohttp.ClientSession() as session:
        query = title.strip().replace(" ", "+")
        url = f"https://jisshuapis.vercel.app/api.php?query={query}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as res:
                if res.status != 200:
                    return None
                data = await res.json()
                for key in ["jisshu-2", "jisshu-3", "jisshu-4"]:
                    posters = data.get(key)
                    if posters and isinstance(posters, list) and posters:
                        return posters[0]
                return None
        except:
            return None


# Utility Functions
def extract_year(text):
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else None

def extract_season(text):
    match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", text)
    return match.group(1) if match else None

def extract_languages(text):
    langs = [lang for lang in CAPTION_LANGUAGES if lang.lower() in text.lower()]
    return ", ".join(langs) if langs else "Not Idea"

async def clean_filename(text):
    return re.sub(r"[^\w\s]", " ", text).replace("_", " ").strip()

async def clean_caption(text):
    if not text:
        return ""
    return re.sub(r"[^\w\s]", " ", text).replace("_", " ").lower().strip()

async def get_quality(text):
    qualities = [
        "480p", "720p", "720p HEVC", "1080p", "1080p HEVC", "2160p",
        "ORG", "hdcam", "HDCAM", "HQ", "HDRip", "camrip", "WEB-DL", "HDTC", "HDTS"
    ]
    for q in qualities:
        if q.lower() in text.lower():
            return q
    return "HDRip"

def format_file_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

import re
from plugins.Dreamxfutures.Imdbposter import get_movie_details
from database.users_chats_db import db
from pyrogram import Client, filters
from info import CHANNELS, MOVIE_UPDATE_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import temp  # Make sure temp.U_NAME is available

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu",
    "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati", "Korean",
    "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese",
    "Russian", "Japanese", "Odia", "Assamese", "Urdu"
]

media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    """Handle media messages from CHANNELS"""
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return
    
    media.file_type = file_type
    media.caption = message.caption
    success, dreamxbotz = await save_file(media)
    
    try:
        if success and dreamxbotz == 1 and await db.movie_update_status(bot.me.id):
            await send_msg(bot, media.file_name, media.caption)
    except Exception as e:
        print(f"Error In Movie Update - {e}")
        pass

def clean_mentions_links(text: str) -> str:
    """Remove unwanted mentions and URLs from text"""
    return re.sub(r'(@\w+|\bwww\.[^\s\]\)]+|\([\@^\)]+\)|\[[\@^\]]+\])', '', text).strip()

async def send_msg(bot, filename, caption):
    try:
        filename = clean_mentions_links(filename).title()
        caption = clean_mentions_links(caption).lower()

        # Extract year
        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        # Extract season
        season_pattern = r"(?i)(?:s|season)0*(\d{1,2})"
        season = re.search(season_pattern, caption) or re.search(season_pattern, filename)
        season = season.group(1) if season else None

        if year:
            filename = filename[:filename.find(year) + 4]
        elif season and season in filename:
            filename = filename[:filename.find(season) + 1]

        # Extract quality
        qualities = [
            "ORG", "org", "hdcam", "HDCAM", "HQ", "hq", "HDRip", "hdrip", "camrip",
            "CAMRip", "hdtc", "predvd", "DVDscr", "dvdscr", "dvdrip", "HDTC", "dvdscreen", "HDTS", "hdts"
        ]
        quality = await get_qualities(caption.lower(), qualities) or "HDRip"

        # Extract language
        language = ""
        for lang in CAPTION_LANGUAGES:
            if lang.lower() in caption:
                language += f"{lang}, "
        language = language.rstrip(', ') if language else "Not identified 😄"

        # Clean filename for title
        filename = re.sub(r"[\(\)\[\]\{\}:;'\-!]", "", filename)
        filename = re.sub(r"\s+", " ", filename).strip()

        # Default IMDb values
        rating = "N/A"
        genres = "N/A"
        imdb_url = "Not available"
        poster_url = None

        if await db.add_name(filename):
            imdb = await get_movie_details(filename)
            if imdb:
                poster_url = imdb.get('poster_url')
                rating = imdb.get("rating", "N/A")
                genres = imdb.get("genres", "N/A")
                imdb_url = imdb.get("url", "Not available")

        # Compose message
        text = f"🎥 {filename} ({year if year else 'N/A'})\n\n"
        text += f"{language}\n\n"
        if imdb_url.startswith("http"):
            text += f"🌟[IMDB Info]({imdb_url}) (⭐️Rating {rating}/10)\n\n"
        else:
            text += f"🌟IMDB Info (⭐️Rating {rating}/10)\n\n"
        text += f"Genres : {genres}"

        # Build button
        filenames = filename.replace(" ", '-')
        btn = [[InlineKeyboardButton('📁 ɢᴇᴛ ғɪʟᴇs', url=f"https://t.me/{temp.U_NAME}?start=getfile-{filenames}")]]
        
        if poster_url:
            await bot.send_photo(
                chat_id=MOVIE_UPDATE_CHANNEL,
                photo=poster_url,
                caption=text,
                reply_markup=InlineKeyboardMarkup(btn),
                has_spoiler=True
            )
        else:
            await bot.send_message(
                chat_id=MOVIE_UPDATE_CHANNEL,
                text=text,
                reply_markup=InlineKeyboardMarkup(btn)
            )

    except Exception as e:
        print(f"Error in send_msg: {e}")
        pass

async def get_qualities(text, qualities: list):
    """Get all matched qualities from text"""
    quality = [q for q in qualities if q in text]
    return ", ".join(quality)

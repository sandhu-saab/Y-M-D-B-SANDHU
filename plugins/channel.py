import re
from plugins.Dreamxfutures.Imdbposter import get_movie_details, fetch_image
from database.users_chats_db import db
from pyrogram import Client, filters
from info import CHANNELS, MOVIE_UPDATE_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp

CAPTION_LANGUAGES = ["Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese", "Russian", "Japanese", "Odia", "Assamese", "Urdu"]

media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    """Media Handler"""
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
            await send_msg(bot, filename=media.file_name, caption=media.caption)
    except Exception as e:
        print(f"Error In Movie Update - {e}")
        pass

def clean_mentions_links(text: str) -> str:
    return re.sub(r'(\@\w+(\.\w+)?|\bwww\.[^\s\]\)]+|\([\@^\)]+\)|\[[\@^\]]+\])', '', text).strip()

async def send_msg(bot, filename, caption): 
    try:
        filename = clean_mentions_links(filename).title()
        caption = clean_mentions_links(caption).lower()
        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        pattern = r"(?i)(?:s|season)0*(\d{1,2})"
        season = re.search(pattern, caption) or re.search(pattern, filename)
        season = season.group(1) if season else None 

        if year:
            filename = filename[: filename.find(year) + 4]  
        elif season and season in filename:
            filename = filename[: filename.find(season) + 1]

        qualities = ["ORG", "org", "hdcam", "HDCAM", "HQ", "hq", "HDRip", "hdrip", "camrip", "CAMRip", "hdtc", "predvd", "DVDscr", "dvdscr", "dvdrip", "HDTC", "dvdscreen", "HDTS", "hdts"]
        quality = await get_qualities(caption.lower(), qualities) or "HDRip"

        language = ""
        possible_languages = CAPTION_LANGUAGES
        for lang in possible_languages:
            if lang.lower() in caption.lower():
                language += f"{lang}, "
        language = language[:-2] if language else "Not idea 😄"

        filename = re.sub(r"[\(\)\[\]\{\}:;'\-!]", "", filename)
        filename = re.sub(r"\s+", " ", filename).strip()
        
        rating = "N/A"
        resized_poster = None
        if await db.add_name(filename):
            imdb = await get_movie_details(filename)
            if imdb:
                poster_url = imdb.get('poster_url')
                rating = imdb.get("rating", "N/A")
                if poster_url:
                    resized_poster = await fetch_image(poster_url)

            text = "​<b>【 {} 】 🆕️\n\nFᴏʀᴍᴀᴛ: {}\n\nAᴜᴅɪᴏ: {}\n\nRᴀᴛɪɴɢ: {} /10\n\n<blockquote>👑 Pʀᴏᴠɪᴅᴇᴅ Bʏ : @Baii_Ji</blockquote></b>"
            text = text.format(filename, quality, language, rating)

            search_movie = filename.replace(" ", '-')
            btn = [[InlineKeyboardButton(' Gᴇᴛ Fɪʟᴇs ', url=f"https://telegram.me/{temp.U_NAME}?start=getfile-{search_movie}")]]

            if resized_poster:
                await bot.send_photo(chat_id=MOVIE_UPDATE_CHANNEL, photo=resized_poster, caption=text, reply_markup=InlineKeyboardMarkup(btn))
            else:
                await bot.send_message(chat_id=MOVIE_UPDATE_CHANNEL, text=text, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        print(f"Error in send_msg: {e}")
        pass

async def get_qualities(text, qualities: list):
    """Get all Quality from text"""
    quality = []
    for q in qualities:
        if q in text:
            quality.append(q)
    quality = ", ".join(quality)
    return quality[:-2] if quality.endswith(", ") else quality

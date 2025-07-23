import re
import logging
import asyncio
from datetime import datetime
from collections import defaultdict
from typing import Optional, Tuple, Dict, List, Set
from pymongo.errors import PyMongoError, DuplicateKeyError
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait

from plugins.Dreamxfutures.Imdbposter import get_movie_details, fetch_image
from database.users_chats_db import db
from pyrogram import Client, filters, enums
from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LINK_PREVIEW, ABOVE_PREVIEW
from Script import script
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp

logger = logging.getLogger(__name__)

# Constants and Configuration
class Config:
    # Precomputed sets for faster lookups
    IGNORE_WORDS = {
        "rarbg", "dub", "sub", "sample", "mkv", "aac", "combined",
        "action", "adventure", "animation", "biography", "comedy", "crime", 
        "documentary", "drama", "family", "fantasy", "film-noir", "history", 
        "horror", "music", "musical", "mystery", "romance", "sci-fi", "sport", 
        "thriller", "war", "western", "hdcam", "hdtc", "camrip", "ts", "tc", 
        "telesync", "dvdscr", "dvdrip", "predvd", "webrip", "web-dl", "tvrip", 
        "hdtv", "web dl", "webdl", "bluray", "brrip", "bdrip", "360p", "480p", 
        "720p", "1080p", "2160p", "4k", "1440p", "540p", "240p", "140p", "hevc", 
        "hdrip", "hin", "hindi", "tam", "tamil", "kan", "kannada", "tel", "telugu", 
        "mal", "malayalam", "eng", "english", "pun", "punjabi", "ben", "bengali", 
        "mar", "marathi", "guj", "gujarati", "urd", "urdu", "kor", "korean", "jpn", 
        "japanese", "nf", "netflix", "sonyliv", "sony", "sliv", "amzn", "prime", 
        "primevideo", "hotstar", "zee5", "jio", "jhs", "aha", "hbo", "paramount", 
        "apple", "hoichoi", "sunnxt", "viki"
    }

    CAPTION_LANGUAGES = {
        "hin": "Hindi", "hindi": "Hindi",
        "tam": "Tamil", "tamil": "Tamil",
        "kan": "Kannada", "kannada": "Kannada",
        "tel": "Telugu", "telugu": "Telugu",
        "mal": "Malayalam", "malayalam": "Malayalam",
        "eng": "English", "english": "English",
        "pun": "Punjabi", "punjabi": "Punjabi",
        "ben": "Bengali", "bengali": "Bengali",
        "mar": "Marathi", "marathi": "Marathi",
        "guj": "Gujarati", "gujarati": "Gujarati",
        "urd": "Urdu", "urdu": "Urdu",
        "kor": "Korean", "korean": "Korean",
        "jpn": "Japanese", "japanese": "Japanese",
    }

    OTT_PLATFORMS = {
        "nf": "Netflix", "netflix": "Netflix",
        "sonyliv": "SonyLiv", "sony": "SonyLiv", "sliv": "SonyLiv",
        "amzn": "Amazon Prime Video", "prime": "Amazon Prime Video", "primevideo": "Amazon Prime Video",
        "hotstar": "Disney+ Hotstar", "zee5": "Zee5",
        "jio": "JioHotstar", "jhs": "JioHotstar",
        "aha": "Aha", "hbo": "HBO Max", "paramount": "Paramount+",
        "apple": "Apple TV+", "hoichoi": "Hoichoi", "sunnxt": "Sun NXT", "viki": "Viki", 
        "chtv": "ChaupalTV", "chpl": "ChaupalTV", "chaupal": "ChaupalTV", "kableone": "KABLEONE"
    }

    STANDARD_GENRES = {
        'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime', 'Documentary',
        'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History', 'Horror', 'Music',
        'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western'
    }

    # Precompiled regex patterns
    CLEAN_PATTERN = re.compile(r'@[^ \n\r\t\.,:;!?()\[\]{}<>\\/"\'=_%]+|\bwww\.[^\s\]\)]+|\([\@^]+\)|\[[\@^]+\]')
    NORMALIZE_PATTERN = re.compile(r"[._\-]+|[()\[\]{}:;'–!,.?_]")
    QUALITY_PATTERN = re.compile(
        r"\b(?:HDCam|HDTC|CamRip|TS|TC|TeleSync|DVDScr|DVDRip|PreDVD|"
        r"WEBRip|WEB-DL|TVRip|HDTV|WEB DL|WebDl|BluRay|BRRip|BDRip|"
        r"360p|480p|720p|1080p|2160p|4K|1440p|540p|240p|140p|HEVC|HDRip)\b", 
        re.IGNORECASE
    )
    YEAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:19|20)\d{2}(?![A-Za-z0-9])")
    RANGE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*[\(\[]E(?:p(?:isode)?)?0*(\d{1,2})\s*(?:to|-)\s*E?0*(\d{1,2})[\)\]]', re.IGNORECASE)
    SINGLE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*E(?:p(?:isode)?)?0*(\d{1,3})', re.IGNORECASE)
    NAMED_REGEX = re.compile(r'Season\s*0*(\d{1,2})[\s\-,:]*Ep(?:isode)?\s*0*(\d{1,3})', re.IGNORECASE)

MEDIA_FILTER = filters.document | filters.video | filters.audio
locks = defaultdict(asyncio.Lock)
pending_updates = {}

class MediaProcessor:
    """Handles processing of media files and extracting metadata"""
    
    @staticmethod
    def clean_mentions_links(text: str) -> str:
        """Remove mentions and links from text"""
        return Config.CLEAN_PATTERN.sub("", text or "").strip()

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text by removing special characters and extra spaces"""
        text = Config.NORMALIZE_PATTERN.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def remove_ignored_words(text: str) -> str:
        """Remove words from the ignore list"""
        return " ".join(word for word in text.split() if word.lower() not in Config.IGNORE_WORDS)

    @staticmethod
    def get_qualities(text: str) -> Dict[str, List[str]]:
        """Extract quality information from text"""
        qualities = Config.QUALITY_PATTERN.findall(text)
        resolutions = set()
        quality_types = set()
        
        for q in qualities:
            q_lower = q.lower()
            if q_lower in RESOLUTION_MAPPINGS:
                resolutions.add(RESOLUTION_MAPPINGS[q_lower])
            elif q_lower in QUALITY_TYPE_MAPPINGS:
                quality_types.add(QUALITY_TYPE_MAPPINGS[q_lower])
        
        return {
            'resolutions': sorted(resolutions, key=lambda x: int(x.replace('p', '').replace('K', '000'))) if resolutions else [],
            'quality_types': sorted(quality_types) if quality_types else []
        }

    @staticmethod
    def extract_ott_platform(text: str) -> str:
        """Extract OTT platform information from text"""
        text = text.lower()
        platforms = {plat for key, plat in Config.OTT_PLATFORMS.items() if key in text}
        return " | ".join(platforms) if platforms else ""

    @staticmethod
    def extract_season_episode(filename: str) -> Tuple[Optional[int], Optional[str]]:
        """Extract season and episode information from filename"""
        for pattern in (Config.RANGE_REGEX, Config.SINGLE_REGEX, Config.NAMED_REGEX):
            if match := pattern.search(filename):
                season = int(match.group(1))
                if pattern == Config.RANGE_REGEX:
                    episode = f"{match.group(2)}-{match.group(3)}"
                else:
                    episode = match.group(2)
                return season, episode
        return None, None

    @staticmethod
    def extract_media_info(filename: str, caption: str) -> Dict:
        """Extract all relevant media information from filename and caption"""
        filename = MediaProcessor.normalize(MediaProcessor.clean_mentions_links(filename).title())
        caption_clean = MediaProcessor.clean_mentions_links(caption).lower() if caption else ""
        unified = f"{caption_clean} {filename.lower()}".strip()

        season = episode = year = None
        tag = "#MOVIE"
        processed_raw = base_raw = filename
        
        # Get quality data
        quality_data = MediaProcessor.get_qualities(caption_clean) or MediaProcessor.get_qualities(filename.lower()) or {}
        
        ott_platform = MediaProcessor.extract_ott_platform(f"{filename} {caption_clean}") or ""

        lang_keys = {k for k in Config.CAPTION_LANGUAGES if k in caption_clean or k in filename.lower()}
        language = ", ".join(sorted({Config.CAPTION_LANGUAGES[k] for k in lang_keys})) if lang_keys else ""

        season, episode = MediaProcessor.extract_season_episode(filename)
        if season is not None:
            tag = "#SERIES"
            if match := (Config.RANGE_REGEX.search(filename) or Config.SINGLE_REGEX.search(filename)):
                match_str = match.group(0)
                start_idx = filename.lower().find(match_str.lower())
                end_idx = start_idx + len(match_str)
                processed_raw = filename[:end_idx]
                base_raw = filename[:start_idx]
                if year_match := Config.YEAR_PATTERN.search(filename.lower()[end_idx:]):
                    year = year_match.group(0)
                    year_idx = filename.lower().find(year, end_idx)
                    if year_idx != -1:
                        processed_raw = filename[:year_idx+4]
                        base_raw += f" {year}"
        else:
            if year_match := Config.YEAR_PATTERN.search(unified):
                year = year_match.group(0)
                year_idx = filename.lower().find(year.lower())
                if year_idx != -1:
                    processed_raw = filename[:year_idx + 4]
                    base_raw = processed_raw
            else:
                if qual_match := Config.QUALITY_PATTERN.search(unified):
                    qual_str = qual_match.group(0)
                    qual_idx = filename.lower().find(qual_str.lower())
                    if qual_idx != -1:
                        processed_raw = filename[:qual_idx]
                        base_raw = processed_raw

        base_name = MediaProcessor.normalize(MediaProcessor.remove_ignored_words(MediaProcessor.normalize(base_raw)))
        if year and year not in base_name:
            base_name += f" {year}"

        if base_name.endswith(")"):
            base_name = re.sub(r"\s+\(\d{4}\)$", "", base_name)
            if year:
                base_name += f" ({year})"

        return {
            "processed": MediaProcessor.normalize(processed_raw),
            "base_name": base_name,
            "tag": tag,
            "season": season,
            "episode": episode,
            "year": year,
            "quality_data": quality_data,
            "ott_platform": ott_platform,
            "language": language
        }

class MessageUpdater:
    """Handles creating and updating movie/series update messages"""
    
    @staticmethod
    def schedule_update(bot, base_name: str, delay: int = 5) -> None:
        """Schedule an update for the movie message after a delay"""
        if handle := pending_updates.get(base_name):
            if not handle.cancelled():
                handle.cancel()
        
        loop = asyncio.get_event_loop()
        pending_updates[base_name] = loop.call_later(
            delay,
            lambda: asyncio.create_task(MessageUpdater.update_movie_message(bot, base_name))
        )

    @staticmethod
    async def send_movie_update(bot, base_name: str) -> Optional[Message]:
        """Send a new movie update message to the channel"""
        max_retries = 3
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                movie_doc = await db.movie_updates.find_one({"_id": base_name})
                if not movie_doc:
                    return None

                text = MessageUpdater.generate_movie_message(movie_doc, base_name)
                buttons = MessageUpdater.create_buttons(base_name)

                if movie_doc.get("poster_url") and not LINK_PREVIEW:
                    resized_poster = await fetch_image(movie_doc["poster_url"])
                    msg = await bot.send_photo(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        photo=resized_poster,
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                    is_photo = True
                else:
                    send_params = {
                        "chat_id": MOVIE_UPDATE_CHANNEL,
                        "text": text,
                        "reply_markup": buttons,
                        "parse_mode": enums.ParseMode.HTML
                    }
                    if movie_doc.get("poster_url") and LINK_PREVIEW:
                        send_params["invert_media"] = ABOVE_PREVIEW
                    msg = await bot.send_message(**send_params)
                    is_photo = False

                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$set": {"message_id": msg.id, "is_photo": is_photo}}
                )
                return msg
            except FloodWait as e:
                wait_time = e.value + 2
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to send movie update: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send movie update after {max_retries} attempts")
                await asyncio.sleep(base_delay * (attempt + 1))
        return None

    @staticmethod
    async def update_movie_message(bot, base_name: str) -> None:
        """Update an existing movie message in the channel"""
        try:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if not movie_doc:
                return

            text = MessageUpdater.generate_movie_message(movie_doc, base_name)
            buttons = MessageUpdater.create_buttons(base_name)

            message_id = movie_doc.get("message_id")
            is_photo = movie_doc.get("is_photo", False)

            if not message_id:
                await MessageUpdater.send_movie_update(bot, base_name)
                return

            try:
                if is_photo:
                    await bot.edit_message_caption(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=message_id,
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=message_id,
                        text=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML,
                        invert_media=ABOVE_PREVIEW,
                        disable_web_page_preview=not LINK_PREVIEW
                    )
                return
            except (MessageIdInvalid, MessageNotModified):
                pass
            except Exception:
                try:
                    await bot.delete_messages(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_ids=message_id
                    )
                    await db.movie_updates.update_one(
                        {"_id": base_name},
                        {"$set": {"message_id": None, "is_photo": False}}
                    )
                except Exception:
                    pass
                await MessageUpdater.send_movie_update(bot, base_name)
        except Exception as e:
            logger.error(f"Failed to update movie message: {e}")

    @staticmethod
    def create_buttons(base_name: str) -> InlineKeyboardMarkup:
        """Create inline keyboard buttons for the movie message"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    '📂 Gᴇᴛ Fɪʟᴇ 📂',
                    url=f"https://t.me/{temp.U_NAME}?start=getfile-{base_name.replace(' ', '-')}"
                )
            ],
            [
                InlineKeyboardButton(
                    '♻️ Hᴏᴡ Tᴏ Dᴏᴡɴʟᴏᴀᴅ ♻️', 
                    url="https://t.me/+dVRLYHXJztJlMmY9"
                )
            ]
        ])

    @staticmethod
    def generate_movie_message(movie_doc: Dict, base_name: str) -> str:
        """Generate the formatted message text for a movie/series update"""
        def make_line(prefix: str, value: str) -> str:
            return f"➩ {prefix} : {value}" if value and value != "N/A" else ""
        
        # Process all fields
        rating_line = make_line("Rating", f"{movie_doc.get('rating', '')}★")
        ott_line = make_line("OTT", movie_doc.get("ott_platform", ""))
        
        # Process resolutions and quality types
        all_resolutions = set()
        all_quality_types = set()
        for file in movie_doc.get("files", []):
            if file.get("quality_data"):
                all_resolutions.update(file["quality_data"].get("resolutions", []))
                all_quality_types.update(file["quality_data"].get("quality_types", []))
        resolution_line = make_line("Pixels", ", ".join(sorted(all_resolutions, key=lambda x: int(x.replace('p','').replace('K','000'))))
        quality_type_line = make_line("Print", ", ".join(sorted(all_quality_types)))
        
        # Process languages
        all_languages = set()
        for file in movie_doc.get("files", []):
            if file.get("language", "N/A") != "N/A":
                all_languages.update(l.strip() for l in file["language"].split(",") if l.strip())
        language_line = make_line("Audio", ", ".join(sorted(all_languages)))
        
        # Process genres
        genres_line = make_line("Genres", movie_doc.get("genres", ""))
        
        # Process episodes
        episodes_block = ""
        if movie_doc.get("tag") == "#SERIES":
            episodes_by_season = defaultdict(set)
            for file in movie_doc.get("files", []):
                if file.get("season") and file.get("episode"):
                    season = file["season"]
                    episode = file["episode"]
                    if '-' in episode:  # Episode range
                        start, end = map(int, episode.split('-'))
                        episodes_by_season[season].update(range(start, end + 1))
                    else:  # Single episode
                        episodes_by_season[season].add(int(episode))
            
            if episodes_by_season:
                epi_lines = []
                for season, episodes in sorted(episodes_by_season.items(), key=lambda x: int(x[0])):
                    sorted_eps = sorted(episodes)
                    # Group consecutive episodes
                    grouped = []
                    start = sorted_eps[0]
                    prev = start
                    
                    for ep in sorted_eps[1:]:
                        if ep == prev + 1:
                            prev = ep
                        else:
                            if start == prev:
                                grouped.append(str(start))
                            else:
                                grouped.append(f"{start}-{prev}")
                            start = prev = ep
                    
                    if start == prev:
                        grouped.append(str(start))
                    else:
                        grouped.append(f"{start}-{prev}")
                    
                    epi_lines.append(f"S{int(season)}: {', '.join(grouped)}")
                episodes_block = "\n➩ Episodes :\n" + "\n".join(epi_lines)

        # Format with the template
        message = script.MOVIE_UPDATE_NOTIFY_TXT.format(
            base_name=base_name,
            rating_line=rating_line,
            ott_line=ott_line,
            quality_type_line=quality_type_line,
            resolution_line=resolution_line,
            language_line=language_line,
            genres_line=genres_line,
            episodes_block=episodes_block
        )
        
        # Remove any empty lines that might have been created
        message = "\n".join(line for line in message.split("\n") if line.strip())
        
        return message

@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):
    """Handle incoming media files from monitored channels"""
    media = next(
        (getattr(message, ft) for ft in ("document", "video", "audio")
         if getattr(message, ft, None)),
        None
    )
    if not media:
        return

    media.file_type = next(ft for ft in ("document", "video", "audio") if hasattr(message, ft))
    media.caption = message.caption or ""
    success, info = await save_file(media)
    if not success:
        return

    try:
        if await db.movie_update_status(bot.me.id):
            await process_and_send_update(bot, media.file_name, media.caption)
    except Exception as e:
        logger.exception(f"Error processing media: {e}")

async def process_and_send_update(bot, filename: str, caption: str) -> None:
    """Process media file and send/update the movie message"""
    try:
        media_info = MediaProcessor.extract_media_info(filename, caption)
        base_name = media_info["base_name"]
        processed = media_info["processed"]

        lock = locks[base_name]
        async with lock:
            await _process_with_lock(bot, filename, caption, media_info, base_name, processed)
    except PyMongoError as e:
        logger.error(f"Database error: {e}")
    except Exception as e:
        logger.exception(f"Processing failed: {e}")

async def _process_with_lock(bot, filename: str, caption: str, media_info: Dict, base_name: str, processed: str) -> None:
    """Process media file while holding a lock for the base_name"""
    if not hasattr(db, 'movie_updates'):
        db.movie_updates = db.db.movie_updates

    movie_doc = await db.movie_updates.find_one({"_id": base_name})
    file_data = {
        "filename": filename,
        "processed": processed,
        "quality_data": media_info["quality_data"],
        "language": media_info["language"],
        "ott_platform": media_info["ott_platform"],
        "timestamp": datetime.now(),
        "tag": media_info["tag"],
        "season": media_info["season"],
        "episode": media_info["episode"]
    }

    if not movie_doc:
        # New movie/series - fetch details and create document
        details = await get_movie_details(base_name) or {}
        raw_genres = details.get("genres", "")
        if isinstance(raw_genres, str):
            genre_list = [g.strip() for g in raw_genres.split(",")]
            genres = ", ".join(g for g in genre_list if g in Config.STANDARD_GENRES) or ""
        else:
            genres = ", ".join(g for g in raw_genres if g in Config.STANDARD_GENRES) or ""

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "poster_url": details.get("poster_url"),
            "genres": genres,
            "rating": details.get("rating", ""),
            "imdb_url": details.get("url", ""),
            "year": media_info["year"] or details.get("year"),
            "tag": media_info["tag"],
            "ott_platform": media_info["ott_platform"],
            "message_id": None,
            "is_photo": False
        }
        try:
            await db.movie_updates.insert_one(movie_doc)
            await MessageUpdater.send_movie_update(bot, base_name)
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
        except DuplicateKeyError:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if movie_doc:
                if any(f["filename"] == filename for f in movie_doc["files"]):
                    return
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$push": {"files": file_data}}
                )
                movie_doc["files"].append(file_data)
                MessageUpdater.schedule_update(bot, base_name)
    else:
        # Existing movie/series - update document
        if any(f["filename"] == filename for f in movie_doc["files"]):
            return
        await db.movie_updates.update_one(
            {"_id": base_name},
            {"$push": {"files": file_data}}
        )
        movie_doc["files"].append(file_data)
        MessageUpdater.schedule_update(bot, base_name)

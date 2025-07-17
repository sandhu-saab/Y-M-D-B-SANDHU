import re
import aiohttp
from io import BytesIO
from info import DREAMXBOTZ_IMAGE_FETCH
from imdb import Cinemagoer
import asyncio

ia = Cinemagoer()

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""

async def fetch_image(url, size=None, timeout=10):
    if not DREAMXBOTZ_IMAGE_FETCH:
        print("Image fetching is disabled.")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    content = await response.read()
                    return BytesIO(content)
                else:
                    print(f"Failed to fetch image: {response.status}")
    except asyncio.TimeoutError:
        print(f"Timeout while fetching image: {url}")
    except Exception as e:
        print(f"Error in fetch_image: {e}")
    return None

async def get_movie_details(query, id=False, file=None):
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year:
                    year = list_to_str(year[:1])
            else:
                year = None
            movieid = ia.search_movie(title.lower(), results=10)
            if not movieid:
                return None
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            if not movieid:
                movieid = filtered
            movieid = movieid[0].movieID
        else:
            movieid = query
        movie = ia.get_movie(movieid)
        ia.update(movie, info=['main', 'vote details'])
        date = movie.get("original air date") or movie.get("year") or "N/A"
        plot = movie.get('plot') or movie.get('plot outline')
        if plot and len(plot) > 0:
            plot = plot[0]
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
        poster_url = movie.get('full-size cover url')
        return {
            'title': movie.get('title'),
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie.get('imdbID')}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster_url': poster_url,
            'plot': plot,
            'rating': str(movie.get("rating", "N/A")),
            'url': f'https://www.imdb.com/title/tt{movieid}'
        }
    except Exception as e:
        print(f"An error occurred in get_movie_details: {e}")
    return None

async def get_poster_from_bharath_api(query):
    try:
        api_url = f"https://bharathboyapis.vercel.app/api/movie-posters?query={query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("Poster API Response:", data)  # Debug line
                    posters = data.get('posters', [])
                    
                    if posters and isinstance(posters, list):
                        for poster in posters:
                            if poster.get('url'):
                                return poster['url']
                    print(f"No valid poster URL found for: {query}")
                else:
                    print(f"API Error: Status {resp.status} for {query}")
    except asyncio.TimeoutError:
        print(f"Timeout while fetching poster for: {query}")
    except Exception as e:
        print(f"Error in get_poster_from_bharath_api: {str(e)}")
    return None

async def get_landscape_poster_from_bharath_api(query):
    try:
        api_url = f"https://bharathboyapis.vercel.app/api/movie-posters?query={query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("Landscape API Response:", data)  # Debug line
                    backdrops = data.get('backdrops', [])
                    
                    if backdrops and isinstance(backdrops, list):
                        for backdrop in backdrops:
                            if backdrop.get('url'):
                                return backdrop['url']
                    print(f"No valid backdrop URL found for: {query}")
                else:
                    print(f"API Error: Status {resp.status} for {query}")
    except asyncio.TimeoutError:
        print(f"Timeout while fetching backdrop for: {query}")
    except Exception as e:
        print(f"Error in get_landscape_poster_from_bharath_api: {str(e)}")
    return None

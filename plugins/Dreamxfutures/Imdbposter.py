import re
import aiohttp
from io import BytesIO
from info import DREAMXBOTZ_IMAGE_FETCH
from imdb import Cinemagoer

ia = Cinemagoer()

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""

async def fetch_image(url, size=None):
    if not DREAMXBOTZ_IMAGE_FETCH:
        print("Image fetching is disabled.")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return BytesIO(content)
                else:
                    print(f"Failed to fetch image: {response.status}")
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
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    posters = data.get('posters', [])
                    if posters and 'url' in posters[0]:
                        return posters[0]['url']
    except Exception as e:
        print(f"Error fetching poster from Bharath API: {e}")
    return None

async def get_landscape_poster_from_bharath_api(query):
    try:
        api_url = f"https://bharathboyapis.vercel.app/api/movie-posters?query={query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    backdrops = data.get('backdrops', [])
                    if backdrops and 'url' in backdrops[0]:
                        return backdrops[0]['url']
    except Exception as e:
        print(f"Error fetching backdrop from Bharath API: {e}")
    return None

# The Movie Database
# Multi-language support added by Aqntbghd
# 3.0 API update by ToMM

import countrycode

# apiary.io debugging URL
# BASE_URL = 'http://private-ad99a-themoviedb.apiary.io/3'

BASE_URL = 'https://api.tmdb.org/3' # TODO Possibly put this behind cloudflare?
API_KEY = 'a3dc111e66105f6387e99393813ae4d5'
TMDB_CONFIG = '%s/configuration?api_key=%s' % (BASE_URL, API_KEY)

# Movies
TMDB_MOVIE_SEARCH = '%s/search/movie?api_key=%s&query=%%s&year=%%s&language=%%s&include_adult=%%s' % (BASE_URL, API_KEY)
TMDB_MOVIE = '%s/movie/%%s?api_key=%s&append_to_response=releases,credits&language=%%s' % (BASE_URL, API_KEY)
TMDB_MOVIE_IMAGES = '%s/movie/%%s/images?api_key=%s' % (BASE_URL, API_KEY)

# TV
TMDB_TV_SEARCH = '%s/search/tv?api_key=%s&query=%%s&year=%%s&language=%%s&include_adult=%%s' % (BASE_URL, API_KEY)
TMDB_TV = '%s/tv/%%s?api_key=%s&append_to_response=credits&language=%%s' % (BASE_URL, API_KEY)
TMDB_TV_SEASON = '%s/tv/%%s/season/%%s?api_key=%s&language=%%s' % (BASE_URL, API_KEY)
TMDB_TV_EPISODE = '%s/tv/%%s/season/%%s/episode/%%s?api_key=%s&append_to_response=credits&language=%%s' % (BASE_URL, API_KEY)
TMDB_TV_IMAGES = '%s/tv/%%s/images?api_key=%s' % (BASE_URL, API_KEY)
TMDB_TV_EXTERNAL_IDS = '%s/tv/%%s/external_ids?api_key=%s' % (BASE_URL, API_KEY)
TMDB_TV_TVDB = '%s/tv/find/%%s?api_key=%s&external_source=tvdb_id' % (BASE_URL, API_KEY)

ARTWORK_ITEM_LIMIT = 15
POSTER_SCORE_RATIO = .3 # How much weight to give ratings vs. vote counts when picking best posters. 0 means use only ratings.
BACKDROP_SCORE_RATIO = .3
RE_IMDB_ID = Regex('^tt\d{7}$')

# TMDB does not seem to have an official set of supported languages.  Users can register and 'translate'
# any movie to any ISO 639-1 language.  The following is a realistic list from a popular title.
# This agent falls back to English metadata and sorts out foreign artwork to to ensure the best
# user experience when less common languages are chosen.
LANGUAGES = [
             Locale.Language.English, Locale.Language.Czech, Locale.Language.Danish, Locale.Language.German,
             Locale.Language.Greek, Locale.Language.Spanish, Locale.Language.Finnish, Locale.Language.French,
             Locale.Language.Hebrew, Locale.Language.Croatian, Locale.Language.Hungarian, Locale.Language.Italian,
             Locale.Language.Latvian, Locale.Language.Dutch, Locale.Language.Norwegian, Locale.Language.Polish,
             Locale.Language.Portuguese, Locale.Language.Russian, Locale.Language.Slovak, Locale.Language.Swedish,
             Locale.Language.Thai, Locale.Language.Turkish, Locale.Language.Vietnamese, Locale.Language.Chinese,
             Locale.Language.Korean
            ]

####################################################################################################
def Start():

  pass

####################################################################################################
@expose
def GetImdbId(tmdb_id, lang='en'):

  tmdb_dict = GetJSON(url=TMDB_MOVIE % (tmdb_id, lang))

  if isinstance(tmdb_dict, dict) and 'imdb_id' in tmdb_dict and RE_IMDB_ID.search(tmdb_dict['imdb_id']):
    return tmdb_dict['imdb_id']

  return None

####################################################################################################
@expose
def GetTvdbId(tmdb_id):

  tmdb_dict = GetJSON(url=TMDB_TV_EXTERNAL_IDS % tmdb_id)

  if isinstance(tmdb_dict, dict) and 'tvdb_id' in tmdb_dict and tmdb_dict['tvdb_id']:
    return str(tmdb_dict['tvdb_id'])

  return None

####################################################################################################
@expose
def GetTvRageId(tmdb_id):

  tmdb_dict = GetJSON(url=TMDB_TV_EXTERNAL_IDS % tmdb_id)

  if isinstance(tmdb_dict, dict) and 'tvrage_id' in tmdb_dict and tmdb_dict['tvrage_id']:
    return str(tmdb_dict['tvrage_id'])

  return None

####################################################################################################
@expose
def GetTMDbSearchResults(id, name, year, lang, manual, get_imdb_id):

  # TODO sanity checks on input vars

  media = FakeMediaObj(id, name, year)
  results = []
  PerformTMDbMovieSearch(results, media, lang, manual, get_imdb_id)

  return results if len(results) > 0 else None

####################################################################################################
@expose
def GetTMDbMetadata(id, lang):

  return PerformTMDbMovieUpdate(id, lang)

####################################################################################################
def GetJSON(url, cache_time=CACHE_1MONTH):

  tmdb_dict = None

  try:
    tmdb_dict = JSON.ObjectFromURL(url, sleep=2.0, headers={'Accept': 'application/json'}, cacheTime=cache_time)
  except:
    Log('Error fetching JSON from The Movie Database.')

  return tmdb_dict

####################################################################################################
def AppendSearchResult(results, id, name=None, year=-1, score=0, lang=None):

  new_result = dict(id=str(id), name=name, year=int(year), score=score, lang=lang)

  if isinstance(results, list):

    results.append(new_result)

  else:

    results.Append(MetadataSearchResult(**new_result))

####################################################################################################
def DictToMovieMetadataObj(metadata_dict, metadata):

  for attr_name, attr_obj in metadata.attrs.iteritems():

    if attr_name not in metadata_dict:
      continue

    dict_value = metadata_dict[attr_name]

    if isinstance(dict_value, list):

      for val in dict_value:
        attr_obj.add(val)

    elif isinstance(dict_value, dict):

      if attr_name in ['posters', 'art', 'themes']:  # Can't access MapObject, so have to write these out

        for k, v in dict_value.iteritems():
          if isinstance(v, tuple):
            attr_obj[k] = Proxy.Preview(HTTP.Request(v[0]).content, sort_order=v[1])
          else:
            attr_obj[k] = v

        attr_obj.validate_keys(dict_value.keys())

      else:
        for k, v in dict_value.iteritems():
          attr_obj[k] = v

    elif attr_name is 'originally_available_at':

      attr_obj.set(Datetime.FromTimestamp(dict_value))

    else:
      attr_obj.set(dict_value)

####################################################################################################
def PerformTMDbMovieSearch(results, media, lang, manual, get_imdb_id=False):

  # If search is initiated by a different, primary metadata agent.
  # This requires the other agent to use the IMDb id as key.
  if media.primary_metadata is not None and RE_IMDB_ID.search(media.primary_metadata.id):
    AppendSearchResult(results=results, id=media.primary_metadata.id, score=100)

  else:
    # If this a manual search (Fix Incorrect Match) and we get an IMDb id as input.
    if manual and RE_IMDB_ID.search(media.name):
      tmdb_dict = GetJSON(url=TMDB_MOVIE % (media.name, lang))

      if isinstance(tmdb_dict, dict) and 'id' in tmdb_dict:

        if get_imdb_id and 'imdb_id' in tmdb_dict and RE_IMDB_ID.search(tmdb_dict['imdb_id']):
          id = str(tmdb_dict['imdb_id'])
        else:
          id = str(tmdb_dict['id'])

        AppendSearchResult(results=results,
                           id=id,
                           name=tmdb_dict['title'],
                           year=int(tmdb_dict['release_date'].split('-')[0]),
                           score=100,
                           lang=lang)

    # If this is an automatic search and The Movie Database agent is used as a primary agent.
    else:
      if media.year and int(media.year) > 1900:
        year = media.year
      else:
        year = ''

      include_adult = 'false'
      if Prefs['adult']:
        include_adult = 'true'

      # Historically we've StrippedDiacritics() here, but this is a pretty aggressive function that won't pass
      # anything that can't be encoded to ASCII, and as such has a tendency to nuke whole titles in, e.g., Asian
      # languages (See GHI #26).  If we have a string that was modified by StripDiacritics() and we get no results,
      # try the search again with the original.
      #
      stripped_name = String.StripDiacritics(media.name)
      tmdb_dict = GetJSON(url=TMDB_MOVIE_SEARCH % (String.Quote(stripped_name), year, lang, include_adult))
      if media.name != stripped_name and (tmdb_dict == None or len(tmdb_dict['results']) == 0):
        Log('No results for title modified by strip diacritics, searching again with the original: ' + media.name)
        tmdb_dict = GetJSON(url=TMDB_MOVIE_SEARCH % (String.Quote(media.name), year, lang, include_adult))

      if isinstance(tmdb_dict, dict) and 'results' in tmdb_dict:
        for i, movie in enumerate(sorted(tmdb_dict['results'], key=lambda k: k['popularity'], reverse=True)):
          score = 90
          score = score - abs(String.LevenshteinDistance(movie['title'].lower(), media.name.lower()))

          # Adjust score slightly for 'popularity' (helpful for similar or identical titles when no media.year is present)
          score = score - (5 * i)

          if 'release_date' in movie and movie['release_date']:
            release_year = int(movie['release_date'].split('-')[0])
          else:
            release_year = -1

          if media.year and int(media.year) > 1900 and release_year:
            year_diff = abs(int(media.year) - release_year)

            if year_diff <= 1:
              score = score + 10
            else:
              score = score - (5 * year_diff)

          if score <= 0:
            continue
          else:

            if get_imdb_id and 'imdb_id' in movie and RE_IMDB_ID.search(movie['imdb_id']):
              id = str(movie['imdb_id'])
            else:
              id = str(movie['id'])

            AppendSearchResult(results=results,
                               id=id,
                               name=movie['title'],
                               year=release_year,
                               score=score,
                               lang=lang)

####################################################################################################
def PerformTMDbMovieUpdate(metadata_id, lang):

  metadata = dict(id=metadata_id)

  config_dict = GetJSON(url=TMDB_CONFIG, cache_time=CACHE_1WEEK * 2)
  tmdb_dict = GetJSON(url=TMDB_MOVIE % (metadata_id, lang))

  if not isinstance(tmdb_dict, dict) or 'overview' not in tmdb_dict or tmdb_dict['overview'] is None or tmdb_dict['overview'] == "":
    # Retry the query with no language specified if we didn't get anything from the initial request.
    tmdb_dict = GetJSON(url=TMDB_MOVIE % (metadata_id, ''))

  # This additional request is necessary since full art/poster lists are not returned if they don't exactly match the language
  tmdb_images_dict = GetJSON(url=TMDB_MOVIE_IMAGES % metadata_id)

  if not isinstance(tmdb_dict, dict) or not isinstance(tmdb_images_dict, dict):
    return None

  # Rating.
  votes = tmdb_dict['vote_count']
  rating = tmdb_dict['vote_average']
  if votes > 3:
    metadata.rating = rating
    metadata.audience_rating = 0.0

  # Title of the film.
  metadata['title'] = tmdb_dict['title']

  if 'original_title' in tmdb_dict and tmdb_dict['original_title'] != tmdb_dict['title']:
    metadata['original_title'] = tmdb_dict['original_title']

  # Tagline.
  metadata['tagline'] = tmdb_dict['tagline']

  # Release date.
  try:
    originally_available_at_date_obj = Datetime.ParseDate(tmdb_dict['release_date']).date()
    metadata['originally_available_at'] = Datetime.TimestampFromDatetime(originally_available_at_date_obj)
    metadata['year'] = metadata.originally_available_at_date_obj.year
  except:
    pass

  if Prefs['country'] != '':
    c = Prefs['country']

    for country in tmdb_dict['releases']['countries']:
      if country['iso_3166_1'] == countrycode.COUNTRY_TO_CODE[c]:

        # Content rating.
        if 'certification' in country and country['certification'] != '':
          if countrycode.COUNTRY_TO_CODE[c] == 'US':
            metadata['content_rating'] = country['certification']
          else:
            metadata['content_rating'] = '%s/%s' % (countrycode.COUNTRY_TO_CODE[c].lower(), country['certification'])

        # Release date (country specific).
        if 'release_date' in country and country['release_date'] != '':
          originally_available_at_date_obj = Datetime.ParseDate(country['release_date']).date()
          metadata['originally_available_at'] = Datetime.TimestampFromDatetime(originally_available_at_date_obj)
          metadata['year'] = originally_available_at_date_obj.year

        break

  # Summary.
  metadata['summary'] = tmdb_dict['overview']
  if metadata['summary'] == 'No overview found.':
    metadata['summary'] = ""

  # Runtime.
  try: metadata['duration'] = int(tmdb_dict['runtime']) * 60 * 1000
  except: pass

  # Genres.
  metadata['genres'] = []
  for genre in tmdb_dict['genres']:
    metadata['genres'].append(genre['name'].strip())

  # Collections.
  metadata['collections'] = []
  if Prefs['collections'] and tmdb_dict['belongs_to_collection'] is not None:
    metadata['collections'].append(tmdb_dict['belongs_to_collection']['name'].replace(' Collection',''))

  # Studio.
  if 'production_companies' in tmdb_dict and len(tmdb_dict['production_companies']) > 0:
    index = tmdb_dict['production_companies'][0]['id']
    company = None

    for studio in tmdb_dict['production_companies']:
      if studio['id'] <= index:
        index = studio['id']
        company = studio['name'].strip()

    metadata['studio'] = company

  else:
    metadata['studio'] = None

  # Country.
  metadata['countries'] = []
  if 'production_countries' in tmdb_dict:
    for country in tmdb_dict['production_countries']:
      country = country['name'].replace('United States of America', 'USA')
      metadata['countries'].append(country)

  # Crew.
  metadata['directors'] = []
  metadata['writers'] = []
  metadata['producers'] = []

  for member in tmdb_dict['credits']['crew']:
    if member['job'] == 'Director':
      metadata['directors'].append(member['name'])
    elif member['job'] in ('Writer', 'Screenplay'):
      metadata['writers'].append(member['name'])
    elif member['job'] == 'Producer':
      metadata['producers'].append(member['name'])

  # Cast.
  metadata['roles'] = []

  for member in sorted(tmdb_dict['credits']['cast'], key=lambda k: k['order']):
    role = {}
    role['role'] = member['character']
    role['actor'] = member['name']
    if member['profile_path'] is not None:
      role['photo'] = config_dict['images']['base_url'] + 'original' + member['profile_path']

  # Note: for TMDB artwork, number of votes is a good predictor of poster quality. Ratings are assigned
  # using a Baysean average that appears to be poorly calibrated, so ratings are almost always between
  # 5 and 6 or zero.  Consider both of these, weighting them according to the POSTER_SCORE_RATIO.

  # No votes get zero, use TMDB's apparent initial Baysean prior mean of 5 instead.
  valid_names = list()

  metadata['posters'] = {}

  if tmdb_images_dict['posters']:
    max_average = max([(lambda p: p['vote_average'] or 5)(p) for p in tmdb_images_dict['posters']])
    max_count = max([(lambda p: p['vote_count'])(p) for p in tmdb_images_dict['posters']]) or 1

    for i, poster in enumerate(tmdb_images_dict['posters']):

      score = (poster['vote_average'] / max_average) * POSTER_SCORE_RATIO
      score += (poster['vote_count'] / max_count) * (1 - POSTER_SCORE_RATIO)
      tmdb_images_dict['posters'][i]['score'] = score

      # Boost the score for localized posters (according to the preference).
      if Prefs['localart']:
        if poster['iso_639_1'] == lang:
          tmdb_images_dict['posters'][i]['score'] = poster['score'] + 1

      # Discount score for foreign posters.
      if poster['iso_639_1'] != lang and poster['iso_639_1'] is not None and poster['iso_639_1'] != 'en':
        tmdb_images_dict['posters'][i]['score'] = poster['score'] - 1

    for i, poster in enumerate(sorted(tmdb_images_dict['posters'], key=lambda k: k['score'], reverse=True)):
      if i > ARTWORK_ITEM_LIMIT:
        break
      else:
        poster_url = config_dict['images']['base_url'] + 'original' + poster['file_path']
        thumb_url = config_dict['images']['base_url'] + 'w154' + poster['file_path']
        valid_names.append(poster_url)

        if poster_url not in metadata['posters']:
          try: metadata['posters'][poster_url] = (thumb_url, i+1)
          except: pass

  # Backdrops.
  valid_names = list()
  metadata['art'] = {}
  if tmdb_images_dict['backdrops']:
    max_average = max([(lambda p: p['vote_average'] or 5)(p) for p in tmdb_images_dict['backdrops']])
    max_count = max([(lambda p: p['vote_count'])(p) for p in tmdb_images_dict['backdrops']]) or 1

    for i, backdrop in enumerate(tmdb_images_dict['backdrops']):

      score = (backdrop['vote_average'] / max_average) * BACKDROP_SCORE_RATIO
      score += (backdrop['vote_count'] / max_count) * (1 - BACKDROP_SCORE_RATIO)
      tmdb_images_dict['backdrops'][i]['score'] = score

      # For backdrops, we prefer "No Language" since they're intended to sit behind text.
      if backdrop['iso_639_1'] == 'xx' or backdrop['iso_639_1'] == 'none':
        tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) + 2

      # Boost the score for localized art (according to the preference).
      if Prefs['localart']:
        if backdrop['iso_639_1'] == lang:
          tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) + 1

      # Discount score for foreign art.
      if backdrop['iso_639_1'] != lang and backdrop['iso_639_1'] is not None and backdrop['iso_639_1'] != 'en':
        tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) - 1

    for i, backdrop in enumerate(sorted(tmdb_images_dict['backdrops'], key=lambda k: k['score'], reverse=True)):
      if i > ARTWORK_ITEM_LIMIT:
        break
      else:
        backdrop_url = config_dict['images']['base_url'] + 'original' + backdrop['file_path']
        thumb_url = config_dict['images']['base_url'] + 'w300' + backdrop['file_path']
        valid_names.append(backdrop_url)

        if backdrop_url not in metadata['art']:
          try: metadata['art'][backdrop_url] = (thumb_url, i+1)
          except: pass

  return metadata

####################################################################################################
class TMDbAgent(Agent.Movies):

  name = 'The Movie Database'
  languages = LANGUAGES
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']
  contributes_to = ['com.plexapp.agents.imdb']

  def search(self, results, media, lang, manual):

    PerformTMDbMovieSearch(results, media, lang, manual)

  def update(self, metadata, media, lang):

    metadata_dict = PerformTMDbMovieUpdate(metadata.id, lang)

    DictToMovieMetadataObj(metadata_dict, metadata)

####################################################################################################
class TMDbAgent(Agent.TV_Shows):

  name = 'The Movie Database'
  languages = LANGUAGES
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.thetvdb']
  contributes_to = ['com.plexapp.agents.thetvdb']

  def search(self, results, media, lang, manual):

    # If TMDB is used as a secondary agent for TVDB, find the TMDB id
    if media.primary_agent == 'com.plexapp.agents.thetvdb':
      tmdb_dict = GetJSON(url=TMDB_TV_TVDB % (media.primary_metadata.id))

      if isinstance(tmdb_dict, dict) and 'tv_results' in tmdb_dict and len(tmdb_dict['tv_results']) > 0:
        tmdb_id = tmdb_dict['tv_results'][0]['id']

        results.Append(MetadataSearchResult(
          id = str(tmdb_id),
          score = 100
        ))

      return

    if media.year and int(media.year) > 1900:
      year = media.year
    else:
      year = ''

    include_adult = 'false'
    if Prefs['adult']:
      include_adult = 'true'

    media_show = media.show
    if not manual:
      filename = String.Unquote(media.filename)
      if (' (US)' in filename or ' (UK)' in filename) and (media.show.endswith(' Us') or media.show.endswith(' Uk')):
        media_show = media.show.rsplit(' ', 1)[0]

    # StrippedDiacritics() is a pretty aggressive function that won't pass
    # anything that can't be encoded to ASCII, and as such has a tendency to nuke whole titles in, e.g., Asian
    # languages (See GHI #26).  If we have a string that was modified by StripDiacritics() and we get no results,
    # try the search again with the original.
    #
    stripped_name = String.StripDiacritics(media_show)
    tmdb_dict = GetJSON(url=TMDB_TV_SEARCH % (String.Quote(stripped_name), year, lang, include_adult))

    if media_show != stripped_name and (tmdb_dict == None or len(tmdb_dict['results']) == 0):
      Log('No results for title modified by strip diacritics, searching again with the original: ' + media_show)
      tmdb_dict = GetJSON(url=TMDB_TV_SEARCH % (String.Quote(media_show), year, lang, include_adult))

    if isinstance(tmdb_dict, dict) and 'results' in tmdb_dict:
      for i, show in enumerate(sorted(tmdb_dict['results'], key=lambda k: k['popularity'], reverse=True)):
        score = 90
        score = score - abs(String.LevenshteinDistance(show['name'].lower(), media_show.lower()))

        # Adjust score slightly for 'popularity' (helpful for similar or identical titles when no media.year is present)
        #score = score - (5 * i)

        if 'first_air_date' in show and show['first_air_date']:
          release_year = int(show['first_air_date'].split('-')[0])
          score = score + 5
        else:
          release_year = None
          score = score - 5

        if media.year and int(media.year) > 1900 and release_year:
          year_diff = abs(int(media.year) - release_year)

          if year_diff == 0:
            score = score + 10
          else:
            score = score - (5 * year_diff)

        if score <= 0:
          continue
        else:
          results.Append(MetadataSearchResult(
            id = str(show['id']),
            name = show['name'],
            year = release_year,
            score = score,
            lang = lang
          ))

  def update(self, metadata, media, lang):

    config_dict = GetJSON(url=TMDB_CONFIG, cache_time=CACHE_1WEEK * 2)
    tmdb_dict = GetJSON(url=TMDB_TV % (metadata.id, lang))

    if not isinstance(tmdb_dict, dict) or 'overview' not in tmdb_dict or tmdb_dict['overview'] is None or tmdb_dict['overview'] == "":
      # Retry the query with no language specified if we didn't get anything from the initial request.
      tmdb_dict = GetJSON(url=TMDB_TV % (metadata.id, ''))

    # This additional request is necessary since full art/poster lists are not returned if they don't exactly match the language
    tmdb_images_dict = GetJSON(url=TMDB_TV_IMAGES % metadata.id)

    if not isinstance(tmdb_dict, dict) or not isinstance(tmdb_images_dict, dict):
      return None

    # Rating.
    votes = tmdb_dict['vote_count']
    rating = tmdb_dict['vote_average']
    if votes > 3:
      metadata.rating = rating
      metadata.audience_rating = 0.0

    # Name of the show.
    metadata.title = tmdb_dict['name']

    # First air date.
    try:
      metadata.originally_available_at = Datetime.ParseDate(tmdb_dict['first_air_date']).date()
      metadata.year = metadata.originally_available_at.year
    except:
      pass

    # Summary.
    metadata.summary = tmdb_dict['overview']
    if metadata.summary == 'No overview found.':
      metadata.summary = ""

    # Runtime.
    try: metadata.duration = int(tmdb_dict['episode_run_time'][0]) * 60 * 1000
    except: pass

    # Genres.
    metadata.genres.clear()
    for genre in tmdb_dict['genres']:
      metadata.genres.add(genre['name'].strip())

    # Studio.
    if 'production_companies' in tmdb_dict and len(tmdb_dict['production_companies']) > 0:
      index = tmdb_dict['production_companies'][0]['id']

      for studio in tmdb_dict['production_companies']:
        if studio['id'] <= index:
          index = studio['id']
          company = studio['name'].strip()

      metadata.studio = company

    else:
      metadata.studio = None

    # Country.
    metadata.countries.clear()
    if 'origin_country' in tmdb_dict:
      for country in tmdb_dict['origin_country']:
        if len(country) == 2 and country in countrycode.CODE_TO_COUNTRY:
          country = countrycode.CODE_TO_COUNTRY[country]
        else:
          continue

        country = country.replace('United States of America', 'USA')
        metadata.countries.add(country)

    # Cast.
    metadata.roles.clear()

    for member in sorted(tmdb_dict['credits']['cast'], key=lambda k: k['order']):
      role = metadata.roles.new()
      role.role = member['character']
      role.actor = member['name']
      if member['profile_path'] is not None:
        role.photo = config_dict['images']['base_url'] + 'original' + member['profile_path']

    # Note: for TMDB artwork, number of votes is a good predictor of poster quality. Ratings are assigned
    # using a Baysean average that appears to be poorly calibrated, so ratings are almost always between
    # 5 and 6 or zero.  Consider both of these, weighting them according to the POSTER_SCORE_RATIO.

    # No votes get zero, use TMDB's apparent initial Baysean prior mean of 5 instead.
    valid_names = list()

    if tmdb_images_dict['posters']:
      max_average = max([(lambda p: p['vote_average'] or 5)(p) for p in tmdb_images_dict['posters']])
      max_count = max([(lambda p: p['vote_count'])(p) for p in tmdb_images_dict['posters']]) or 1

      for i, poster in enumerate(tmdb_images_dict['posters']):

        score = (poster['vote_average'] / max_average) * POSTER_SCORE_RATIO
        score += (poster['vote_count'] / max_count) * (1 - POSTER_SCORE_RATIO)
        tmdb_images_dict['posters'][i]['score'] = score

        # Boost the score for localized posters (according to the preference).
        if Prefs['localart']:
          if poster['iso_639_1'] == lang:
            tmdb_images_dict['posters'][i]['score'] = poster['score'] + 1

        # Discount score for foreign posters.
        if poster['iso_639_1'] != lang and poster['iso_639_1'] is not None and poster['iso_639_1'] != 'en':
          tmdb_images_dict['posters'][i]['score'] = poster['score'] - 1

      for i, poster in enumerate(sorted(tmdb_images_dict['posters'], key=lambda k: k['score'], reverse=True)):
        if i > ARTWORK_ITEM_LIMIT:
          break
        else:
          poster_url = config_dict['images']['base_url'] + 'original' + poster['file_path']
          thumb_url = config_dict['images']['base_url'] + 'w154' + poster['file_path']
          valid_names.append(poster_url)

          if poster_url not in metadata.posters:
            try: metadata.posters[poster_url] = Proxy.Preview(HTTP.Request(thumb_url).content, sort_order=i+1)
            except: pass

    metadata.posters.validate_keys(valid_names)

    # Backdrops.
    valid_names = list()

    if tmdb_images_dict['backdrops']:
      max_average = max([(lambda p: p['vote_average'] or 5)(p) for p in tmdb_images_dict['backdrops']])
      max_count = max([(lambda p: p['vote_count'])(p) for p in tmdb_images_dict['backdrops']]) or 1

      for i, backdrop in enumerate(tmdb_images_dict['backdrops']):

        score = (backdrop['vote_average'] / max_average) * BACKDROP_SCORE_RATIO
        score += (backdrop['vote_count'] / max_count) * (1 - BACKDROP_SCORE_RATIO)
        tmdb_images_dict['backdrops'][i]['score'] = score

        # For backdrops, we prefer "No Language" since they're intended to sit behind text.
        if backdrop['iso_639_1'] == 'xx' or backdrop['iso_639_1'] == 'none':
          tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) + 2

        # Boost the score for localized art (according to the preference).
        if Prefs['localart']:
          if backdrop['iso_639_1'] == lang:
            tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) + 1

        # Discount score for foreign art.
        if backdrop['iso_639_1'] != lang and backdrop['iso_639_1'] is not None and backdrop['iso_639_1'] != 'en':
          tmdb_images_dict['backdrops'][i]['score'] = float(backdrop['score']) - 1

      for i, backdrop in enumerate(sorted(tmdb_images_dict['backdrops'], key=lambda k: k['score'], reverse=True)):
        if i > ARTWORK_ITEM_LIMIT:
          break
        else:
          backdrop_url = config_dict['images']['base_url'] + 'original' + backdrop['file_path']
          thumb_url = config_dict['images']['base_url'] + 'w300' + backdrop['file_path']
          valid_names.append(backdrop_url)

          if backdrop_url not in metadata.art:
            try: metadata.art[backdrop_url] = Proxy.Preview(HTTP.Request(thumb_url).content, sort_order=i+1)
            except: pass

    metadata.art.validate_keys(valid_names)

    # Get episode data.
    @parallelize
    def UpdateEpisodes():

      # Loop over seasons.
      for s in media.seasons:
        season = metadata.seasons[s]

        # Set season metadata.
        @task
        def UpdateSeason(season=season, s=s):

          tmdb_season_dict = GetJSON(url=TMDB_TV_SEASON % (metadata.id, s, lang))

          if tmdb_season_dict is None:
            return None

          season.summary = tmdb_season_dict['overview']

          # Season poster.
          valid_names = list()

          if 'poster_path' in tmdb_season_dict and tmdb_season_dict['poster_path']:
            poster_url = config_dict['images']['base_url'] + 'original' + tmdb_season_dict['poster_path']
            thumb_url = config_dict['images']['base_url'] + 'w154' + tmdb_season_dict['poster_path']
            valid_names.append(poster_url)

            if poster_url not in season.posters:
              try:
                season.posters[poster_url] = Proxy.Preview(HTTP.Request(thumb_url).content)
              except:
                pass

          season.posters.validate_keys(valid_names)

        # Loop over episodes in a season.
        for e in media.seasons[s].episodes:
          episode = metadata.seasons[s].episodes[e]

          # Set episode metadata.
          @task
          def UpdateEpisode(episode=episode, s=s, e=e):

            tmdb_episode_dict = GetJSON(url=TMDB_TV_EPISODE % (metadata.id, s, e, lang))

            if not isinstance(tmdb_episode_dict, dict):
              return None

            # Rating.
            votes = tmdb_episode_dict['vote_count']
            rating = tmdb_episode_dict['vote_average']
            if votes > 3:
              episode.rating = rating

            # Name of the episode.
            episode.title = tmdb_episode_dict['name']

            # Summary.
            episode.summary = tmdb_episode_dict['overview']

            # Air date.
            try:
              episode.originally_available_at = Datetime.ParseDate(tmdb_episode_dict['air_date']).date()
            except:
              pass

            # Crew.
            episode.directors.clear()
            episode.writers.clear()
            episode.producers.clear()

            if 'crew' in tmdb_episode_dict['credits']:

              for member in tmdb_episode_dict['credits']['crew']:
                if member['job'] == 'Director':
                  episode.directors.add(member['name'])
                elif member['job'] in ('Writer', 'Screenplay'):
                  episode.writers.add(member['name'])
                elif member['job'] == 'Producer':
                  episode.producers.add(member['name'])

            # TODO:
            # - Actors per episode?
            # - Guest stars?

            # Episode still.
            valid_names = list()

            if 'still_path' in tmdb_episode_dict and tmdb_episode_dict['still_path']:
              still_url = config_dict['images']['base_url'] + 'original' + tmdb_episode_dict['still_path']
              thumb_url = config_dict['images']['base_url'] + 'w154' + tmdb_episode_dict['still_path']
              valid_names.append(still_url)

              if still_url not in episode.thumbs:
                try:
                  episode.thumbs[still_url] = Proxy.Preview(HTTP.Request(thumb_url).content)
                except:
                  pass

            episode.thumbs.validate_keys(valid_names)

####################################################################################################
class FakeMediaObj():

  def __init__(self, id, name, year):
    self.name = name
    self.year = year
    self.primary_metadata = FakePrimaryMetadataObj(id)

####################################################################################################
class FakePrimaryMetadataObj():

  def __init__(self, id):
    self.id = id
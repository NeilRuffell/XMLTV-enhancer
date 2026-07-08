Build a provider-agnostic XMLTV enrichment service for Kodi IPTV Simple and the Kodi skin `skin.estuary.pvr.plus.omega`.

The input XMLTV already contains channels, channel IDs, channel logos, programme start/stop times, programme titles, and programme descriptions. Preserve all of that. The missing layer is safe programme category metadata for Kodi EPG colouring, genre icons, and skin flags.

The service must transform an existing XMLTV into enriched XMLTV by adding exactly one safe `<category>` to every `<programme>` and generating a matching Kodi IPTV Simple `genres.xml`.

Do not replace the provider guide. Do not rebuild the schedule. Do not modify programme times. Do not modify channel IDs. Do not modify channel logos. Do not modify stream URLs. Do not patch Kodi. Do not patch the skin.

Input modes:

```yaml
INPUT_MODE: xmltv_url | xmltv_file

XMLTV_URL: ""
XMLTV_FILE: "/data/input.xml"
```

Required TMDb configuration:

```yaml
TMDB_TOKEN: ""
TMDB_LANGUAGE: "en-US"
TMDB_REGION: "CA"
```

`TMDB_TOKEN` is required for full enrichment. If `TMDB_TOKEN` is missing, the service may start, but `/stats` must report degraded mode and `/audit` must fail with `tmdb_unavailable`.

Output endpoints:

```text
/health
/refresh
/refresh?clear=1
/stats
/epg.xml
/genres.xml
/inspect?title=...
/audit
```

Required behaviour for every `<programme>`:

1. Preserve `start`, `stop`, `channel`, `<title>`, `<desc>`, `<icon>`, `<date>`, `<episode-num>`, `<sub-title>`, `<rating>`, `<star-rating>`, and all other existing non-category metadata.
2. Remove all existing `<category>` tags.
3. Add exactly one corrected `<category>` tag.
4. Never add more than one `<category>`.
5. Never leave a programme without a `<category>`.
6. Never output bare ambiguous categories such as `Drama`, `Comedy`, `Action`, `Thriller`, `Romance`, or `Science Fiction`.
7. Never output `Feature Film`.
8. Never output `TV Movie` for a TV show.
9. Never put `Movie` or `Film` in a category unless the programme is confidently resolved as an actual movie.
10. If classification is not confident, output `Other Unknown`.

Use this exact whitelist of allowed output categories:

```text
Movie
Movie - Action
Movie - Adventure
Movie - Animation
Movie - Comedy
Movie - Drama
Movie - Factual
Movie - Horror
Movie - Mystery
Movie - Romance
Movie - Sci-Fi
Movie - Thriller
Movie - War
Movie - Western

Entertainment
Entertainment - Action
Entertainment - Animation
Entertainment - Comedy
Entertainment - Drama
Entertainment - Game Show
Entertainment - Reality
Entertainment - Sci-Fi
Entertainment - Soap
Entertainment - Talk

Children
Documentary
News & Documentaries - News
News & Documentaries - Business
Sports - Baseball
Sports - Basketball
Sports - Football
Sports - Golf
Sports - Hockey
Sports - Motor Sport
Sports - Tennis
Lifestyle
Music
Other Unknown
```

Generate `genres.xml` from the same whitelist.

Use these mappings:

```text
Movie*                         -> 0x10
News & Documentaries - News    -> 0x20
News & Documentaries - Business-> 0x20
Entertainment*                 -> 0x30
Sports*                        -> 0x40
Children                       -> 0x50
Music                          -> 0x60
Documentary                    -> 0x90
Lifestyle                      -> 0xA0
```

Do not use `0x00`.

Do not map `Other Unknown` unless explicitly configured. It must remain safe and must never trigger movie/film colouring.

Classification order:

1. Build channel lookup from XMLTV `<channel id>`.
2. For each programme, use channel name, title, description, runtime, and existing metadata.
3. Detect obvious live/non-library categories first:

   * news/business channels and descriptions -> `News & Documentaries - News` or `News & Documentaries - Business`
   * sports channels/titles/descriptions -> sport-specific category if obvious, otherwise safest sports category
   * children/kids channels -> `Children`
   * documentary/factual channels -> `Documentary`
   * lifestyle/home/food/travel channels -> `Lifestyle`
   * music channels -> `Music`
4. If not obvious, resolve with TMDb.
5. Use TMDb movie/TV search or multi-search. Do not blindly take the first result.
6. Score candidates using exact normalized title match, alternative title match, year match if available, description similarity, media type, popularity/vote count as weak tie-breaker, and channel context as weak tie-breaker.
7. If TMDb confidently returns `media_type=movie`, output a `Movie...` category.
8. If TMDb confidently returns `media_type=tv`, output an `Entertainment...` category.
9. If not confident, output `Other Unknown`.

Title normalization:

* Normalize only for lookup.
* Do not change the actual XMLTV `<title>`.
* Remove noise such as `HD`, `FHD`, `UHD`, `4K`, `NEW`, `LIVE`, `Premiere`, `S01E02`, `S1 E2`, `1x02`, `Episode 4`, and `Season 2`.
* Preserve valid numeric titles such as `2012`, `1917`, `1883`, `1923`, `24`, and `9-1-1`.
* Keep multiple lookup candidates, including the raw title and normalized title.

Movie category rules:

```text
TMDb movie Action          -> Movie - Action
TMDb movie Adventure       -> Movie - Adventure
TMDb movie Animation       -> Movie - Animation
TMDb movie Comedy          -> Movie - Comedy
TMDb movie Drama           -> Movie - Drama
TMDb movie Documentary     -> Movie - Factual
TMDb movie Horror          -> Movie - Horror
TMDb movie Mystery         -> Movie - Mystery
TMDb movie Romance         -> Movie - Romance
TMDb movie Science Fiction -> Movie - Sci-Fi
TMDb movie Thriller        -> Movie - Thriller
TMDb movie War             -> Movie - War
TMDb movie Western         -> Movie - Western
fallback movie             -> Movie
```

TV category rules:

```text
TMDb TV Comedy             -> Entertainment - Comedy
TMDb TV Drama              -> Entertainment - Drama
TMDb TV Action & Adventure -> Entertainment - Action
TMDb TV Animation          -> Entertainment - Animation
TMDb TV Reality            -> Entertainment - Reality
TMDb TV Sci-Fi & Fantasy   -> Entertainment - Sci-Fi
TMDb TV Soap               -> Entertainment - Soap
TMDb TV Talk               -> Entertainment - Talk
fallback TV                -> Entertainment
```

Special category rules:

```text
Business/news/markets/finance/economics -> News & Documentaries - Business
General news/weather/current affairs    -> News & Documentaries - News
Kids/children/cartoon channels           -> Children
Documentary/history/science/nature       -> Documentary
Food/home/garden/travel/lifestyle        -> Lifestyle
Music channels/programming               -> Music
Obvious baseball                         -> Sports - Baseball
Obvious basketball                       -> Sports - Basketball
Obvious football/NFL/CFL                 -> Sports - Football
Obvious golf                             -> Sports - Golf
Obvious hockey/NHL                       -> Sports - Hockey
Obvious racing/F1/motorsport             -> Sports - Motor Sport
Obvious tennis                           -> Sports - Tennis
```

Caching:

* Use persistent cache under `/data/cache`.
* Cache by classifier version, normalized title, optional year, optional channel name/id, TMDb result, media type, final category, and genre ID.
* `/refresh?clear=1` must delete cache and rebuild.
* If classifier version changes, ignore old cache.
* Never reuse stale cached values if the whitelist or mapping changes.

`/inspect?title=...` must return JSON showing:

```json
{
  "query": "...",
  "normalized_candidates": [],
  "special_detection": null,
  "tmdb_candidates": [],
  "chosen": {
    "source": "tmdb | rule | fallback",
    "media_type": "movie | tv | null",
    "title": "...",
    "genres": [],
    "final_category": "...",
    "genre_id": "..."
  }
}
```

`/audit` must validate the generated XMLTV and fail if any of these occur:

```text
programme_missing_category
programme_multiple_categories
category_not_in_whitelist
category_missing_from_genres_xml
bare_ambiguous_category
feature_film_present
tv_contains_movie_or_film
non_movie_contains_movie_or_film
movie_category_without_movie_media_type
genre_id_0x00_used
tmdb_unavailable
xml_invalid
```

Acceptance tests:

```text
/inspect?title=2012
```

Expected:

```text
media_type = movie
final_category starts with Movie
genre_id = 0x10
```

```text
/inspect?title=Seinfeld
```

Expected:

```text
media_type = tv
final_category = Entertainment - Comedy
genre_id = 0x30
category does not contain Movie
category does not contain Film
```

```text
/inspect?title=The Office
```

Expected:

```text
media_type = tv
final_category = Entertainment - Comedy
genre_id = 0x30
category does not contain Movie
category does not contain Film
```

```text
/audit
```

Expected:

```text
zero safety violations
```

Implementation requirements:

* Python or Node is acceptable.
* Use a proper XML parser/writer.
* Output valid UTF-8 XML with XML declaration.
* Preserve original XMLTV channel/programme order.
* Preserve XML escaping correctly.
* Serve `/epg.xml` and `/genres.xml` over HTTP on configurable port, default `8765`.
* Redact secrets in logs, `/stats`, `/audit`, and errors.
* Never log `TMDB_TOKEN`, provider URLs with credentials, usernames, or passwords.
* Provide Dockerfile and docker-compose example.
* Provide tests for XML rewriting, category classification, TMDb resolver, genre mapping, and audit validation.

Docker Compose example:

```yaml
services:
  epg-enricher:
    build: .
    ports:
      - "8765:8765"
    volumes:
      - ./data:/data
    environment:
      INPUT_MODE: "xmltv_file"
      XMLTV_FILE: "/data/input.xml"
      TMDB_TOKEN: ""
      TMDB_LANGUAGE: "en-US"
      TMDB_REGION: "CA"
      PORT: "8765"
      REFRESH_SECONDS: "21600"
```

Final output files:

```text
http://<host>:8765/epg.xml
http://<host>:8765/genres.xml
```

Kodi IPTV Simple must be able to use the enriched XMLTV as its EPG source and the generated `genres.xml` as its genre mapping file.

The service is successful only when the uploaded-style XMLTV is transformed into a valid enriched XMLTV where every programme has exactly one safe skin-compatible category, every mapped category has a valid Kodi genre ID, and `/audit` reports zero safety violations.

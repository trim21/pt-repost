import dataclasses


@dataclasses.dataclass(kw_only=True)
class TMDBMovieInfo:
    genre_ids: list[int] = dataclasses.field(default_factory=list)
    id: int
    origin_country: list[str] = dataclasses.field(default_factory=list)
    original_language: str

    # movie name
    original_title: str = ""
    title: str = ""


@dataclasses.dataclass(kw_only=True)
class TMDBTvInfo:
    genre_ids: list[int] = dataclasses.field(default_factory=list)
    id: int
    origin_country: list[str] = dataclasses.field(default_factory=list)
    original_language: str

    # tv name
    original_name: str = ""
    name: str = ""


@dataclasses.dataclass(kw_only=True)
class TMDBExternalIDs:
    imdb_id: str | None = None


@dataclasses.dataclass(kw_only=True)
class TMDBMovieSearchResult:
    page: int
    results: list[TMDBMovieInfo]
    total_pages: int
    total_results: int


@dataclasses.dataclass(kw_only=True)
class TMDBTvSearchResult:
    page: int
    results: list[TMDBTvInfo]
    total_pages: int
    total_results: int


@dataclasses.dataclass(kw_only=True)
class Season:
    season_number: int
    episode_count: int


@dataclasses.dataclass(kw_only=True)
class TMDBMovieDetail:
    id: int
    imdb_id: str | None = None
    origin_country: list[str] = dataclasses.field(default_factory=list)

    # movie name
    original_title: str = ""
    title: str = ""


@dataclasses.dataclass(kw_only=True)
class TMDBTvDetail:
    id: int
    origin_country: list[str] = dataclasses.field(default_factory=list)

    # tv name
    original_name: str = ""
    name: str = ""

    seasons: list[Season]

    # need params={"append_to_response": "external_ids"}
    external_ids: TMDBExternalIDs


@dataclasses.dataclass(kw_only=True)
class FullSubjectInfo:
    id: int
    names: list[str] = dataclasses.field(default_factory=list)
    imdb_id: str | None
    episode_count: int = 0
    douban_id: str | None
    origin_country: list[str] = dataclasses.field(default_factory=list)
    release_type: str
    genre_ids: list[int] = dataclasses.field(default_factory=list)

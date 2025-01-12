from __future__ import annotations

import dataclasses
from typing import List

from pydantic import Field


@dataclasses.dataclass(kw_only=True)
class Rating:
    max: int
    average: str
    num_raters: int = Field(..., alias="numRaters")
    min: int


@dataclasses.dataclass(kw_only=True)
class AuthorItem:
    name: str


@dataclasses.dataclass(kw_only=True)
class Attrs:
    website: List[str]
    pubdate: List[str]
    language: List[str]
    title: List[str]
    country: List[str]
    writer: List[str]
    director: List[str]
    cast: List[str]
    episodes: List[str]
    movie_duration: List[str]
    year: List[str]
    movie_type: List[str]


@dataclasses.dataclass(kw_only=True)
class Tag:
    count: int
    name: str


@dataclasses.dataclass(kw_only=True)
class DoubanSubject:
    # rating: Rating
    # author: List[AuthorItem]
    alt_title: str = ""
    # image: str
    title: str
    # summary: str
    # attrs: Attrs
    id: str
    # mobile_link: str = ""
    # alt: str
    # tags: List[Tag]

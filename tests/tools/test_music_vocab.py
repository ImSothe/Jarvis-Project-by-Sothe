"""Snap mis-transcribed artist names back to the ones the user listens to."""

from __future__ import annotations

import pytest

from openjarvis.tools import music_vocab

NAMES = ["Quevedo", "Residente", "Bad Bunny", "Rels B", "Aitana", "C. Tangana"]


@pytest.fixture(autouse=True)
def _known_artists(monkeypatch):
    monkeypatch.setattr(music_vocab, "load_names", lambda limit=60: NAMES[:limit])


@pytest.mark.parametrize(
    "heard, expected",
    [
        ("Ponquevedos", "Quevedo"),
        ("pon que veo", "Quevedo"),
        ("quevedos", "Quevedo"),
        ("ponme Quevedo", "Quevedo"),
        ("Residentes", "Residente"),
        ("ponme algo de bad bunni", "Bad Bunny"),
        ("badbunny", "Bad Bunny"),
    ],
)
def test_mangled_names_are_corrected(heard, expected):
    assert music_vocab.correct_query(heard) == expected


@pytest.mark.parametrize(
    "query",
    [
        "Quevedo: Bzrp Music Sessions, Vol. 52",  # a song title that merely contains the name
        "Los Planetas",
        "Metallica",
        "no",
        "",
    ],
)
def test_other_queries_are_left_alone(query):
    assert music_vocab.correct_query(query) == query


def test_without_a_vocabulary_nothing_changes(monkeypatch):
    monkeypatch.setattr(music_vocab, "load_names", lambda limit=60: [])
    assert music_vocab.correct_query("Ponquevedos") == "Ponquevedos"

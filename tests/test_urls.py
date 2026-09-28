"""Tests for turning links into video IDs.

``@pytest.mark.parametrize`` runs the same test once per row in the list,
which is a compact way to check many link shapes.
"""

import pytest

from ytranscript.errors import InvalidLinkError
from ytranscript.urls import canonical_url, extract_video_id, is_youtube_url

ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={ID}",
        f"https://youtube.com/watch?v={ID}",
        f"http://www.youtube.com/watch?v={ID}",
        f"https://www.youtube.com/watch?v={ID}&t=42s&list=PLabc",
        f"https://www.youtube.com/watch?feature=share&v={ID}",
        f"https://m.youtube.com/watch?v={ID}",
        f"https://music.youtube.com/watch?v={ID}",
        f"https://youtu.be/{ID}",
        f"https://youtu.be/{ID}?si=abcdef&t=10",
        f"https://www.youtube.com/shorts/{ID}",
        f"https://www.youtube.com/embed/{ID}",
        f"https://www.youtube-nocookie.com/embed/{ID}?rel=0",
        f"https://www.youtube.com/live/{ID}?feature=share",
        f"https://www.youtube.com/v/{ID}",
        f"youtube.com/watch?v={ID}",  # no scheme
        f"youtu.be/{ID}",  # no scheme
        f"  https://youtu.be/{ID}  ",  # surrounding whitespace
        ID,  # bare id
    ],
)
def test_extract_video_id_accepts_every_common_shape(url):
    assert extract_video_id(url) == ID


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://vimeo.com/123456",
        "https://www.google.com/search?q=youtube",
        "https://www.youtube.com/",
        "https://www.youtube.com/channel/UCabc123",
        "https://www.youtube.com/playlist?list=PLabc",
        "https://www.youtube.com/watch?v=tooshort",
        "https://youtu.be/",
        "not a link at all",
    ],
)
def test_extract_video_id_rejects_bad_links(url):
    with pytest.raises(InvalidLinkError):
        extract_video_id(url)


def test_error_message_is_helpful():
    with pytest.raises(InvalidLinkError) as excinfo:
        extract_video_id("https://vimeo.com/123456")
    assert "not a YouTube link" in str(excinfo.value)


def test_is_youtube_url():
    assert is_youtube_url(f"https://youtu.be/{ID}")
    assert is_youtube_url(f"youtube.com/watch?v={ID}")
    assert is_youtube_url(ID)
    assert not is_youtube_url("https://vimeo.com/123456")
    assert not is_youtube_url("")


def test_canonical_url():
    assert canonical_url(ID) == f"https://www.youtube.com/watch?v={ID}"

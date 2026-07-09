import feedparser
from datetime import datetime, timezone

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

CHANNEL_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
MAX_TRANSCRIPT_CHARS = 8000     # ограничение, чтобы не кормить LLM (и не платить) за огромные транскрипты
MAX_DESCRIPTION_CHARS = 500


def fetch_channel_videos(channel_id: str) -> list[dict]:
    """
    Новые видео канала — через встроенный RSS YouTube (без API-ключа).
    Отдаёт последние ~15 видео канала (столько YouTube кладёт в этот фид).
    """
    url = CHANNEL_FEED_URL.format(channel_id=channel_id)
    feed = feedparser.parse(url)

    items = []
    for entry in feed.entries:
        video_id = entry.get("yt_videoid", "")
        if not video_id:
            continue

        thumbnail_url = ""
        media_thumb = entry.get("media_thumbnail")
        if media_thumb and isinstance(media_thumb, list) and media_thumb:
            thumbnail_url = media_thumb[0].get("url", "")

        description = (entry.get("media_description", "") or "")[:MAX_DESCRIPTION_CHARS]

        published_at = None
        if entry.get("published_parsed"):
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        items.append({
            "video_id": video_id,
            "title": entry.get("title", ""),
            "description": description,
            # Канонический вид ссылки — строим сами, ничего лишнего в query нет.
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumbnail_url,
            "published_at": published_at,
        })
    return items


def fetch_transcript(video_id: str) -> str:
    """
    Достаёт субтитры видео (обычно автосгенерированные YouTube) и склеивает
    в обычный текст. Берём любую доступную дорожку, независимо от языка —
    наша LLM и так переводит с любого языка. Пусто, если субтитров нет вообще
    (у части видео их отключают).
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = next(iter(transcript_list), None)
        if transcript is None:
            return ""
        chunks = transcript.fetch()
        text = " ".join(chunk.get("text", "") for chunk in chunks)
        return text[:MAX_TRANSCRIPT_CHARS]
    except (TranscriptsDisabled, NoTranscriptFound):
        return ""
    except Exception as e:
        print(f"[youtube] Не удалось получить субтитры {video_id}: {e}")
        return ""

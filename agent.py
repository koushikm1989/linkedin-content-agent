import feedparser
import anthropic
import requests
import smtplib
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── SOURCES ───────────────────────────────────────────────────────────────────

REDDIT_FEEDS = [
    "https://www.reddit.com/r/ProductManagement/.rss",
    "https://www.reddit.com/r/ProductManagement_IN/.rss",
    "https://www.reddit.com/r/prodmgmt/.rss",
    "https://www.reddit.com/r/AIML/.rss",
    "https://www.reddit.com/r/interviews/.rss",
    "https://www.reddit.com/r/MadeMeSmile/.rss",
    "https://www.reddit.com/r/memes/.rss",
    "https://www.reddit.com/r/AIDankmemes/.rss",
]

GOOGLE_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=product+management&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=AI+product+management&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=product+manager+career&hl=en-IN&gl=IN&ceid=IN:en",
]

MEDIUM_URLS = [
    "https://pdmgr.medium.com/",
    "https://medium.com/@InnoThiga",
]

BLOG_URLS = [
    "https://www.theproductfolks.com/product-management-blog",
    "https://www.jefago.com/product-management/",
]

LINKEDIN_RSS_FEEDS = [
    "https://rsshub.app/linkedin/company/product-management-exercises",
    "https://rsshub.app/linkedin/company/product-management-learning-pml",
    "https://rsshub.app/linkedin/company/nyu-pmc",
    "https://rsshub.app/linkedin/in/sandeep-panda-226a5a26",
    "https://rsshub.app/linkedin/in/anirudh-sheldenkar-88b8b115",
]

PINTEREST_RSS_FEEDS = [
    "https://rsshub.app/pinterest/search/product%20management",
    "https://rsshub.app/pinterest/search/product%20design",
    "https://rsshub.app/pinterest/search/artificial%20intelligence",
    "https://rsshub.app/pinterest/search/AI%20PM",
]

YOUTUBE_HANDLES = [
    "@Atlassian",
    "@tryexponent",
    "@airtribe",
    "@LennysPodcast",
    "@ProductSchoolSanFrancisco",
    "@hellopm",
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

FEEDPARSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def extract_image(entry) -> str:
    """Try every known location an image URL might live in an RSS entry."""
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image") or \
               m.get("url", "").endswith((".jpg", ".png", ".webp")):
                return m.get("url")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")
    if hasattr(entry, "links"):
        for link in entry.links:
            if link.get("type", "").startswith("image"):
                return link.get("href")
    if entry.get("summary"):
        soup = BeautifulSoup(entry["summary"], "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]
    return None


def fetch_rss_articles(feeds: list[str], max_age_hours: int = None) -> list[dict]:
    """Generic RSS fetcher. max_age_hours=None means no date filter (historical)."""
    articles = []
    cutoff = datetime.now() - timedelta(hours=max_age_hours) if max_age_hours else None

    for url in feeds:
        try:
            feed = feedparser.parse(url, agent=FEEDPARSER_AGENT)
            for entry in feed.entries[:15]:
                if cutoff:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                        if published < cutoff:
                            continue
                    except Exception:
                        pass
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "summary": entry.get("summary", "")[:400].strip(),
                    "source":  feed.feed.get("title", url),
                    "image":   extract_image(entry),
                })
        except Exception as e:
            print(f"  RSS error ({url}): {e}")

    return articles


def get_youtube_channel_rss(handle: str) -> str:
    """Fetch a YouTube channel page and extract its RSS feed URL from the HTML."""
    try:
        resp = requests.get(f"https://www.youtube.com/{handle}", headers=HEADERS, timeout=10)
        for pattern in [r'"channelId":"(UC[a-zA-Z0-9_-]+)"',
                        r'"externalId":"(UC[a-zA-Z0-9_-]+)"']:
            match = re.search(pattern, resp.text)
            if match:
                return f"https://www.youtube.com/feeds/videos.xml?channel_id={match.group(1)}"
    except Exception as e:
        print(f"  YouTube channel ID error ({handle}): {e}")
    return None


def fetch_youtube_articles(handles: list[str]) -> list[dict]:
    """Resolve YouTube @handles to RSS feeds and fetch recent videos."""
    articles = []
    for handle in handles:
        rss_url = get_youtube_channel_rss(handle)
        if not rss_url:
            print(f"  Could not resolve channel ID for {handle}")
            continue
        try:
            feed = feedparser.parse(rss_url, agent=FEEDPARSER_AGENT)
            for entry in feed.entries[:5]:
                thumbnail = None
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    thumbnail = entry.media_thumbnail[0].get("url")
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "summary": entry.get("summary", "")[:400].strip(),
                    "source":  f"YouTube: {feed.feed.get('title', handle)}",
                    "image":   thumbnail,
                })
            print(f"  {handle}: {len(feed.entries[:5])} videos fetched")
        except Exception as e:
            print(f"  YouTube RSS error ({handle}): {e}")
    return articles


def fetch_medium_articles(urls: list[str]) -> list[dict]:
    articles = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all("h2"):
                title = tag.get_text(strip=True)
                parent = tag.find_parent("a")
                link = parent["href"] if parent and parent.get("href") else url
                if not link.startswith("http"):
                    link = "https://medium.com" + link
                img = None
                container = tag.find_parent("div") or tag.find_parent("article")
                if container:
                    img_tag = container.find("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src")
                if title and len(title) > 15:
                    articles.append({"title": title, "link": link,
                                     "summary": "", "source": url, "image": img})
        except Exception as e:
            print(f"  Medium scrape error ({url}): {e}")
    return articles[:10]


def fetch_blog_articles(urls: list[str]) -> list[dict]:
    articles = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["h2", "h3"]):
                title = tag.get_text(strip=True)
                anchor = tag.find("a") or tag.find_parent("a")
                link = anchor["href"] if anchor and anchor.get("href") else url
                if not link.startswith("http"):
                    base = "/".join(url.split("/")[:3])
                    link = base + "/" + link.lstrip("/")
                img = None
                container = tag.find_parent("div") or tag.find_parent("article")
                if container:
                    img_tag = container.find("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src")
                if title and len(title) > 15:
                    articles.append({"title": title, "link": link,
                                     "summary": "", "source": url, "image": img})
        except Exception as e:
            print(f"  Blog scrape error ({url}): {e}")
    return articles[:10]


# ── CLAUDE ────────────────────────────────────────────────────────────────────

def pick_best(client, articles: list[dict], source_label: str) -> dict:
    """One Claude call: pick the single best article from a pool and write a LinkedIn post."""
    if not articles:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\n"
        f"URL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(articles[:20])
    ])

    prompt = f"""You are a LinkedIn content strategist for a Product Manager based in India.
Today is {datetime.now().strftime('%B %d, %Y')}.

Source pool: {source_label}

Pick the SINGLE best article for a PM/tech professional LinkedIn audience.
Prioritise: unique insight, career relevance, AI in product, India tech scene.

{numbered}

Write a LinkedIn post of 150-200 words: strong hook, 3 punchy insights, closing question.
Tone: professional but conversational.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

LINKEDIN POST:
[full post text]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text

    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", response_text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(articles):
            picked_index = idx

    return {"article": articles[picked_index], "response": response_text}


def rank_and_draft(reddit, google_other, new_sources) -> list[dict]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = []

    print("  Article 1 — picking from Reddit...")
    r1 = pick_best(client, reddit, "REDDIT")
    if r1:
        results.append(r1)

    print("  Article 2 — picking from Google News / Medium / Blogs...")
    r2 = pick_best(client, google_other, "GOOGLE NEWS / MEDIUM / BLOGS")
    if r2:
        results.append(r2)

    print("  Article 3 — picking from LinkedIn / Pinterest / YouTube...")
    r3 = pick_best(client, new_sources, "LINKEDIN / PINTEREST / YOUTUBE")
    if r3:
        results.append(r3)

    print("  Article 4 — picking wildcard best from all sources...")
    picked_urls = {r["article"]["link"] for r in results}
    remaining = [a for a in (reddit + google_other + new_sources)
                 if a["link"] not in picked_urls]
    r4 = pick_best(client, remaining, "ALL SOURCES — wildcard best pick")
    if r4:
        results.append(r4)

    return results


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def build_html_email(results: list[dict]) -> str:
    labels = [
        ("📌", "Article 1", "From Reddit", "#ff4500"),
        ("📰", "Article 2", "From Google News / Medium / Blogs", "#1a73e8"),
        ("🔗", "Article 3", "From LinkedIn / Pinterest / YouTube", "#0077b5"),
        ("⭐", "Article 4", "Wildcard best pick", "#f5a623"),
    ]

    sections = []
    for i, result in enumerate(results):
        article = result["article"]
        response = result["response"]
        emoji, num, sublabel, color = labels[i] if i < len(labels) else ("📄", f"Article {i+1}", "", "#333")

        post_match = re.search(r"LINKEDIN POST:\s*\n([\s\S]+?)(?:\n---|\Z)", response)
        linkedin_post = post_match.group(1).strip() if post_match else response

        why_match = re.search(r"Why picked:\s*(.+)", response)
        why = why_match.group(1).strip() if why_match else ""

        image_html = ""
        if article.get("image"):
            image_html = (
                f'<img src="{article["image"]}" '
                f'style="max-width:100%;border-radius:8px;margin:12px 0;display:block;" '
                f'alt="Article image">'
            )

        post_html = linkedin_post.replace("\n", "<br>")

        sections.append(f"""
<div style="border-left:4px solid {color};background:#fafafa;padding:20px;
            margin-bottom:28px;border-radius:4px;">
  <p style="margin:0 0 4px;font-size:13px;color:#888;">{emoji} {num} &mdash; {sublabel}</p>
  <h2 style="margin:0 0 12px;font-size:18px;">
    <a href="{article['link']}" style="color:#111;text-decoration:none;">{article['title']}</a>
  </h2>
  {image_html}
  <p style="color:#666;font-size:12px;margin:4px 0;">
    Source: {article['source']}
    {"&nbsp;&nbsp;|&nbsp;&nbsp;<em>" + why + "</em>" if why else ""}
  </p>
  <hr style="border:none;border-top:1px solid #e8e8e8;margin:16px 0;">
  <p style="font-weight:600;color:{color};margin:0 0 8px;">✍️ LinkedIn Post Draft</p>
  <div style="background:#fff;padding:16px;border-radius:4px;
              border:1px solid #e8e8e8;line-height:1.8;font-size:14px;">
    {post_html}
  </div>
  <p style="margin-top:14px;">
    <a href="{article['link']}"
       style="background:{color};color:#fff;padding:8px 18px;border-radius:4px;
              text-decoration:none;font-size:13px;">Read Full Article →</a>
  </p>
</div>""")

    date_str = datetime.now().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;
max-width:680px;margin:0 auto;padding:24px;color:#333;">
  <div style="background:#0077b5;padding:24px;border-radius:8px;
              margin-bottom:32px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;">📰 Your Daily LinkedIn Content</h1>
    <p style="color:#cce5ff;margin:8px 0 0;font-size:14px;">Top 4 picks for {date_str}</p>
  </div>
  {"".join(sections)}
  <div style="text-align:center;color:#aaa;font-size:12px;
              margin-top:32px;padding-top:20px;border-top:1px solid #eee;">
    Generated by your LinkedIn Content Agent &middot; Powered by Claude Haiku
  </div>
</body></html>"""


def send_email(results: list[dict]):
    sender    = os.environ["GMAIL_ADDRESS"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001F4F0 Your LinkedIn posts for "
        f"{datetime.now().strftime('%b %d, %Y')} \u2014 4 articles ready"
    )
    msg["From"] = sender
    msg["To"]   = recipient
    msg.attach(MIMEText(build_html_email(results), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print("Email sent successfully.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/6 — Reddit RSS (historical)...")
    reddit = fetch_rss_articles(REDDIT_FEEDS, max_age_hours=None)
    print(f"  {len(reddit)} articles")

    print("Step 2/6 — Google News RSS (last 48 h)...")
    google = fetch_rss_articles(GOOGLE_NEWS_FEEDS, max_age_hours=48)
    print(f"  {len(google)} articles")

    print("Step 3/6 — Medium profiles...")
    medium = fetch_medium_articles(MEDIUM_URLS)
    print(f"  {len(medium)} articles")

    print("Step 4/6 — PM blogs...")
    blogs = fetch_blog_articles(BLOG_URLS)
    print(f"  {len(blogs)} articles")

    print("Step 5/6 — LinkedIn / Pinterest / YouTube...")
    linkedin  = fetch_rss_articles(LINKEDIN_RSS_FEEDS, max_age_hours=None)
    print(f"  LinkedIn (RSSHub): {len(linkedin)} posts")
    pinterest = fetch_rss_articles(PINTEREST_RSS_FEEDS, max_age_hours=None)
    print(f"  Pinterest (RSSHub): {len(pinterest)} pins")
    youtube   = fetch_youtube_articles(YOUTUBE_HANDLES)
    print(f"  YouTube: {len(youtube)} videos")

    google_other = google + medium + blogs
    new_sources  = linkedin + pinterest + youtube

    print(f"\nTotals — Reddit: {len(reddit)} | Google/Medium/Blogs: {len(google_other)} | LinkedIn/Pinterest/YouTube: {len(new_sources)}")

    if not any([reddit, google_other, new_sources]):
        print("No articles found. Exiting.")
        return

    print("\nStep 6/6 — Claude Haiku: 4 independent picks...")
    results = rank_and_draft(reddit, google_other, new_sources)

    print("Sending HTML email with images...")
    send_email(results)
    print("Done!")


if __name__ == "__main__":
    main()

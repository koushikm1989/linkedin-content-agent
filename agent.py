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

# ── POOL METADATA ─────────────────────────────────────────────────────────────

POOL_META = {
    "Reddit":      {"color": "#ff4500", "emoji": "👾", "bg": "#fff8f6"},
    "Google News": {"color": "#4285f4", "emoji": "📰", "bg": "#f6f9ff"},
    "Medium":      {"color": "#000000", "emoji": "✍️", "bg": "#f9f9f9"},
    "Blog":        {"color": "#1a73e8", "emoji": "📝", "bg": "#f6f9ff"},
    "LinkedIn":    {"color": "#0077b5", "emoji": "💼", "bg": "#f0f7fb"},
    "Pinterest":   {"color": "#e60023", "emoji": "📌", "bg": "#fff6f7"},
    "YouTube":     {"color": "#ff0000", "emoji": "▶️", "bg": "#fff8f8"},
    "Unknown":     {"color": "#888888", "emoji": "🔗", "bg": "#fafafa"},
}

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
                    "pool":    None,
                })
        except Exception as e:
            print(f"  RSS error ({url}): {e}")

    return articles


def get_youtube_channel_rss(handle: str) -> str:
    """Fetch a YouTube channel page and extract its RSS feed URL from the HTML."""
    try:
        resp = requests.get(
            f"https://www.youtube.com/{handle}", headers=HEADERS, timeout=10
        )
        for pattern in [
            r'"channelId":"(UC[a-zA-Z0-9_-]+)"',
            r'"externalId":"(UC[a-zA-Z0-9_-]+)"',
        ]:
            match = re.search(pattern, resp.text)
            if match:
                return (
                    f"https://www.youtube.com/feeds/videos.xml"
                    f"?channel_id={match.group(1)}"
                )
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
                    "pool":    "YouTube",
                })
            print(f"  {handle}: {len(feed.entries[:5])} videos fetched")
        except Exception as e:
            print(f"  YouTube RSS error ({handle}): {e}")
    return articles


def fetch_medium_articles(urls: list[str]) -> list[dict]:
    """Scrape recent article titles and links from Medium profile pages."""
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
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": "",
                        "source":  url,
                        "image":   img,
                        "pool":    "Medium",
                    })
        except Exception as e:
            print(f"  Medium scrape error ({url}): {e}")
    return articles[:10]


def fetch_blog_articles(urls: list[str]) -> list[dict]:
    """Scrape article titles and links from PM blogs."""
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
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": "",
                        "source":  url,
                        "image":   img,
                        "pool":    "Blog",
                    })
        except Exception as e:
            print(f"  Blog scrape error ({url}): {e}")
    return articles[:10]


# ── CLAUDE ────────────────────────────────────────────────────────────────────

def pick_best(client, articles: list[dict], source_label: str) -> dict:
    """One Claude call: pick the single best article and write a LinkedIn post."""
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

Write a LinkedIn post of 150-200 words: strong hook, 3 punchy insights,
closing question. Tone: professional but conversational.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

LINKEDIN POST:
[full post text]"""

    import time
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 2:
                print(f"  Anthropic overloaded, retrying in 30s... (attempt {attempt+1})")
                time.sleep(30)
            else:
                raise

    response_text = message.content[0].text

    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", response_text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(articles):
            picked_index = idx

    return {
        "article":  articles[picked_index],
        "response": response_text,
    }


def rank_and_draft(
    reddit: list[dict],
    google_other: list[dict],
    new_sources: list[dict],
) -> list[dict]:
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

    print("  Article 4 — wildcard best from all sources...")
    picked_urls = {r["article"]["link"] for r in results}
    remaining = [
        a for a in (reddit + google_other + new_sources)
        if a["link"] not in picked_urls
    ]
    r4 = pick_best(client, remaining, "ALL SOURCES — wildcard best pick")
    if r4:
        results.append(r4)

    return results


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def build_html_email(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    sections = []

    for i, result in enumerate(results):
        article  = result["article"]
        response = result["response"]
        pool     = article.get("pool", "Unknown")
        meta     = POOL_META.get(pool, POOL_META["Unknown"])
        color    = meta["color"]
        emoji    = meta["emoji"]
        bg       = meta["bg"]

        post_match = re.search(
            r"LINKEDIN POST:\s*\n([\s\S]+?)(?:\n---|\Z)", response
        )
        linkedin_post = post_match.group(1).strip() if post_match else response

        why_match = re.search(r"Why picked:\s*(.+)", response)
        why = why_match.group(1).strip() if why_match else ""

        image_html = ""
        if article.get("image"):
            image_html = f"""
            <div style="margin:16px 0;border-radius:10px;overflow:hidden;
                        box-shadow:0 2px 8px rgba(0,0,0,0.08);">
              <img src="{article['image']}" alt="Article image"
                   style="width:100%;max-height:280px;object-fit:cover;display:block;">
            </div>"""

        post_lines = (
            linkedin_post
            .replace("\n\n", "<br><br>")
            .replace("\n", "<br>")
        )

        source_badge = f"""
        <span style="display:inline-block;background:{color};color:#fff;
                     font-size:11px;font-weight:700;padding:3px 10px;
                     border-radius:20px;letter-spacing:0.5px;">
          {emoji} {pool}
        </span>"""

        article_num_label = f"Article {i+1} of {len(results)}"

        sections.append(f"""
<div style="background:{bg};border:1px solid #e8e8e8;border-radius:14px;
            margin-bottom:32px;overflow:hidden;
            box-shadow:0 4px 16px rgba(0,0,0,0.06);">

  <!-- Colour strip header -->
  <div style="background:{color};padding:12px 24px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="color:#fff;font-size:13px;font-weight:600;
                   letter-spacing:0.5px;opacity:0.9;">{article_num_label}</td>
        <td align="right" style="color:#fff;font-size:12px;opacity:0.75;">
          {datetime.now().strftime("%a, %d %b %Y")}
        </td>
      </tr>
    </table>
  </div>

  <div style="padding:24px;">

    <!-- Source badge -->
    <div style="margin-bottom:12px;">{source_badge}</div>

    <!-- Title -->
    <h2 style="margin:0 0 10px;font-size:20px;line-height:1.35;font-weight:700;">
      <a href="{article['link']}"
         style="color:#111;text-decoration:none;">{article['title']}</a>
    </h2>

    <!-- Source name -->
    <p style="color:#888;font-size:12px;margin:0 0 4px;">
      🔗 {article['source']}
    </p>

    <!-- Why picked -->
    {"<p style='color:#666;font-size:13px;font-style:italic;margin:6px 0 0;'>💡 " + why + "</p>" if why else ""}

    <!-- Image -->
    {image_html}

    <!-- Divider -->
    <div style="border-top:1px solid #e0e0e0;margin:20px 0;"></div>

    <!-- LinkedIn post label -->
    <div style="margin-bottom:10px;">
      <span style="font-size:12px;font-weight:700;color:{color};
                   text-transform:uppercase;letter-spacing:0.8px;">
        ✍️ LinkedIn Post Draft
      </span>
    </div>

    <!-- Post body -->
    <div style="background:#fff;border-left:4px solid {color};
                padding:18px 20px;border-radius:0 10px 10px 0;
                font-size:14px;line-height:1.85;color:#333;
                box-shadow:0 1px 4px rgba(0,0,0,0.05);">
      {post_lines}
    </div>

    <!-- CTA row -->
    <div style="margin-top:18px;">
      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding-right:10px;">
            <a href="{article['link']}"
               style="background:{color};color:#fff;padding:10px 22px;
                      border-radius:8px;text-decoration:none;font-size:13px;
                      font-weight:600;display:inline-block;">
              Read Full Article →
            </a>
          </td>
          <td>
            <span style="background:#f0f0f0;color:#555;padding:10px 16px;
                         border-radius:8px;font-size:12px;display:inline-block;">
              📋 Copy &amp; paste into LinkedIn
            </span>
          </td>
        </tr>
      </table>
    </div>

  </div>
</div>""")

    # Source pills for the quick-nav bar
    source_pills = "".join([
        f'<span style="background:{POOL_META.get(r["article"].get("pool","Unknown"), POOL_META["Unknown"])["color"]};'
        f'color:#fff;padding:4px 12px;border-radius:20px;font-size:12px;'
        f'font-weight:600;display:inline-block;margin:3px;">'
        f'{POOL_META.get(r["article"].get("pool","Unknown"), POOL_META["Unknown"])["emoji"]} '
        f'{r["article"].get("pool","Unknown")}</span>'
        for r in results
    ])

    unique_sources = len(set(r["article"].get("pool", "") for r in results))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Your Daily LinkedIn Content</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">

  <div style="max-width:680px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0077b5 0%,#005885 100%);
                padding:36px 32px;border-radius:16px;margin-bottom:28px;
                text-align:center;box-shadow:0 8px 24px rgba(0,119,181,0.25);">
      <div style="font-size:40px;margin-bottom:10px;">📰</div>
      <h1 style="color:#fff;margin:0 0 8px;font-size:24px;font-weight:700;
                 letter-spacing:-0.5px;">Your Daily LinkedIn Content</h1>
      <p style="color:#cce5ff;margin:0 0 16px;font-size:15px;">{date_str}</p>
      <div style="display:inline-block;background:rgba(255,255,255,0.15);
                  padding:6px 20px;border-radius:20px;">
        <span style="color:#fff;font-size:13px;">
          {len(results)} articles curated across {unique_sources} source types
        </span>
      </div>
    </div>

    <!-- Source pills -->
    <div style="background:#fff;padding:16px 20px;border-radius:12px;
                margin-bottom:28px;border:1px solid #e8e8e8;
                box-shadow:0 2px 8px rgba(0,0,0,0.04);">
      <p style="margin:0 0 10px;font-size:11px;color:#888;
                text-transform:uppercase;letter-spacing:0.8px;font-weight:600;">
        Today's sources
      </p>
      <div>{source_pills}</div>
    </div>

    <!-- Article cards -->
    {"".join(sections)}

    <!-- Footer -->
    <div style="text-align:center;padding:24px 0;
                border-top:1px solid #e0e0e0;margin-top:8px;">
      <p style="color:#aaa;font-size:12px;margin:0 0 4px;">
        Generated by your LinkedIn Content Agent
      </p>
      <p style="color:#bbb;font-size:11px;margin:0;">
        Powered by Claude Haiku &middot; Running on GitHub Actions
      </p>
    </div>

  </div>
</body>
</html>"""


def send_email(results: list[dict]):
    sender    = os.environ["GMAIL_ADDRESS"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001F4F0 Your LinkedIn posts for "
        f"{datetime.now().strftime('%b %d, %Y')} \u2014 "
        f"{len(results)} articles ready"
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
    for a in reddit:
        a["pool"] = "Reddit"
    print(f"  {len(reddit)} articles")

    print("Step 2/6 — Google News RSS (last 48 h)...")
    google = fetch_rss_articles(GOOGLE_NEWS_FEEDS, max_age_hours=48)
    for a in google:
        a["pool"] = "Google News"
    print(f"  {len(google)} articles")

    print("Step 3/6 — Medium profiles...")
    medium = fetch_medium_articles(MEDIUM_URLS)
    print(f"  {len(medium)} articles")

    print("Step 4/6 — PM blogs...")
    blogs = fetch_blog_articles(BLOG_URLS)
    print(f"  {len(blogs)} articles")

    print("Step 5/6 — LinkedIn / Pinterest / YouTube...")
    linkedin = fetch_rss_articles(LINKEDIN_RSS_FEEDS, max_age_hours=None)
    for a in linkedin:
        a["pool"] = "LinkedIn"
    print(f"  LinkedIn (RSSHub): {len(linkedin)} posts")

    pinterest = fetch_rss_articles(PINTEREST_RSS_FEEDS, max_age_hours=None)
    for a in pinterest:
        a["pool"] = "Pinterest"
    print(f"  Pinterest (RSSHub): {len(pinterest)} pins")

    youtube = fetch_youtube_articles(YOUTUBE_HANDLES)
    print(f"  YouTube: {len(youtube)} videos")

    google_other = google + medium + blogs
    new_sources  = linkedin + pinterest + youtube

    print(
        f"\nTotals — Reddit: {len(reddit)} | "
        f"Google/Medium/Blogs: {len(google_other)} | "
        f"LinkedIn/Pinterest/YouTube: {len(new_sources)}"
    )

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

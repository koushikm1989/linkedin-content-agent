import feedparser
import anthropic
import requests
import smtplib
import os
import re
import time
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
    "https://news.google.com/rss/search?q=artificial+intelligence+breakthrough&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=science+discovery&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=technology+innovation&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=education+future+learning&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=sports+inspiring+comeback&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=motivational+success+story&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=startup+founder+story&hl=en-IN&gl=IN&ceid=IN:en",
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
    "Google News": {"color": "#1a73e8", "emoji": "📰", "bg": "#f6f9ff"},
    "Medium":      {"color": "#292929", "emoji": "✍️", "bg": "#f7f7f7"},
    "Blog":        {"color": "#0f5bbf", "emoji": "📝", "bg": "#f6f9ff"},
    "LinkedIn":    {"color": "#0077b5", "emoji": "💼", "bg": "#f0f7fb"},
    "Pinterest":   {"color": "#ad081b", "emoji": "📌", "bg": "#fff6f7"},
    "YouTube":     {"color": "#cc0000", "emoji": "▶️", "bg": "#fff8f8"},
    "Unknown":     {"color": "#444444", "emoji": "🔗", "bg": "#fafafa"},
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
FEEDPARSER_AGENT = HEADERS["User-Agent"]


def extract_image(entry) -> str:
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
            print(f"  {handle}: {len(feed.entries[:5])} videos")
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
                    articles.append({
                        "title": title, "link": link, "summary": "",
                        "source": url, "image": img, "pool": "Medium",
                    })
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
                    articles.append({
                        "title": title, "link": link, "summary": "",
                        "source": url, "image": img, "pool": "Blog",
                    })
        except Exception as e:
            print(f"  Blog scrape error ({url}): {e}")
    return articles[:10]


# ── CLAUDE ────────────────────────────────────────────────────────────────────

def pick_best(client, articles: list[dict], source_label: str) -> dict:
    """One Claude call: pick the single best article and write a LinkedIn post in Koushik's voice."""
    if not articles:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\n"
        f"URL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(articles[:20])
    ])

    prompt = f"""You are writing a LinkedIn post in the voice of Koushik Mukherjee, a Lead Product Owner (B2B SaaS).

Today is {datetime.now().strftime('%B %d, %Y')}.
Source pool: {source_label}

From the list below, pick the SINGLE best article for a thoughtful PM / tech professional audience.
Prioritise: a sharp insight, a counterintuitive angle, AI in product, career growth, or a genuinely witty/motivational hook from science, tech, education, or sports.

{numbered}

KOUSHIK'S VOICE — study and match it closely:
- Open with a bold, punchy one-line thesis. Often a contrast: "brilliant at X, still figuring out Y." No throat-clearing.
- Two registers depending on the article:
  (a) ANALYTICAL TEARDOWN for PM/tech/business articles — decode the situation, cite specific numbers if available, name the tension, offer a crisp insight. Use phrases like "Here's what made this land for me" or "the quietly uncomfortable bit".
  (b) WITTY OBSERVER for lighter/meme/motivational/sports articles — dry, self-aware, a little playful. Sparing use of !!! and an emoji like 😬 or 🥳 is fine here (max 1-2 emojis, never more).
- First person and personal. He shares his own take and "places his bet". Optimistic and principled — he cares about building responsibly and making things better.
- Use arrow bullets (→) for any list of 2-4 points. Bold 1-2 key phrases max.
- ALWAYS end with a genuine open question that invites the reader to weigh in.
- Length 150-200 words. No corporate jargon, no hashtag stuffing (2-4 relevant hashtags max at the very end).
- Never fabricate statistics. Only cite numbers that appear in the article summary.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

LINKEDIN POST:
[full post in Koushik's voice]"""

    message = None
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=900,
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

    return {"article": articles[picked_index], "response": response_text}


def rank_and_draft(reddit, google_other, new_sources) -> list[dict]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = []
    picked_urls = set()

    def add_pick(pool, label):
        candidates = [a for a in pool if a["link"] not in picked_urls]
        if not candidates:
            return
        r = pick_best(client, candidates, label)
        if r:
            results.append(r)
            picked_urls.add(r["article"]["link"])

    # 2 from Reddit
    print("  Picks 1-2 — Reddit...")
    add_pick(reddit, "REDDIT")
    add_pick(reddit, "REDDIT")

    # 3 from Google News / Medium / Blogs
    print("  Picks 3-5 — Google News / Medium / Blogs...")
    add_pick(google_other, "GOOGLE NEWS / MEDIUM / BLOGS")
    add_pick(google_other, "GOOGLE NEWS / MEDIUM / BLOGS")
    add_pick(google_other, "GOOGLE NEWS / MEDIUM / BLOGS")

    # 3 from LinkedIn / Pinterest / YouTube
    print("  Picks 6-8 — LinkedIn / Pinterest / YouTube...")
    add_pick(new_sources, "LINKEDIN / PINTEREST / YOUTUBE")
    add_pick(new_sources, "LINKEDIN / PINTEREST / YOUTUBE")
    add_pick(new_sources, "LINKEDIN / PINTEREST / YOUTUBE")

    # 2 wildcards from everything remaining
    print("  Picks 9-10 — wildcard from all sources...")
    all_pool = reddit + google_other + new_sources
    add_pick(all_pool, "ALL SOURCES — wildcard")
    add_pick(all_pool, "ALL SOURCES — wildcard")

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
            <tr>
              <td style="padding:0 0 18px 0;line-height:0;">
                <img src="{article['image']}" alt="" width="100%"
                     style="display:block;width:100%;max-height:260px;
                            object-fit:cover;border-radius:10px;">
              </td>
            </tr>"""

        post_lines = (
            linkedin_post
            .replace("\n\n", "<br><br>")
            .replace("\n", "<br>")
        )

        sections.append(f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-bottom:28px;border-radius:14px;overflow:hidden;
              border:1px solid #e8e8e8;
              box-shadow:0 4px 16px rgba(0,0,0,0.06);">

  <!-- Colour strip header -->
  <tr>
    <td style="background:{color};padding:12px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:Arial,sans-serif;color:#ffffff;
                     font-size:13px;font-weight:700;letter-spacing:0.5px;">
            Article {i+1} of {len(results)}
          </td>
          <td align="right">
            <span style="font-family:Arial,sans-serif;
                         background:rgba(255,255,255,0.22);color:#ffffff;
                         font-size:11px;font-weight:700;padding:3px 10px;
                         border-radius:20px;">
              {emoji} {pool}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Card body -->
  <tr>
    <td style="background:{bg};padding:24px;">
      <table width="100%" cellpadding="0" cellspacing="0">

        {image_html}

        <tr>
          <td style="padding-bottom:8px;">
            <h2 style="font-family:Arial,sans-serif;margin:0;
                       font-size:19px;line-height:1.35;font-weight:800;
                       color:#111111;">
              <a href="{article['link']}" target="_blank"
                 style="color:#111111;text-decoration:none;">{article['title']}</a>
            </h2>
          </td>
        </tr>

        <tr>
          <td style="padding-bottom:6px;">
            <span style="font-family:Arial,sans-serif;font-size:12px;
                         color:#888888;">🔗 {article['source'][:60]}</span>
          </td>
        </tr>

        {"<tr><td style='padding-bottom:6px;'><span style='font-family:Arial,sans-serif;font-size:13px;font-style:italic;color:#666666;'>💡 " + why + "</span></td></tr>" if why else ""}

        <tr>
          <td style="padding:14px 0;">
            <div style="border-top:1px solid #e0e0e0;"></div>
          </td>
        </tr>

        <tr>
          <td style="padding-bottom:10px;">
            <span style="font-family:Arial,sans-serif;font-size:12px;
                         font-weight:700;color:{color};
                         text-transform:uppercase;letter-spacing:0.8px;">
              ✍️ LinkedIn Post Draft
            </span>
          </td>
        </tr>

        <tr>
          <td style="background:#ffffff;border-left:4px solid {color};
                     padding:16px 18px;border-radius:0 10px 10px 0;">
            <p style="font-family:Arial,sans-serif;margin:0;font-size:14px;
                      line-height:1.85;color:#333333;">
              {post_lines}
            </p>
          </td>
        </tr>

        <tr>
          <td style="padding-top:18px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:{color};border-radius:8px;">
                  <a href="{article['link']}" target="_blank"
                     style="font-family:Arial,sans-serif;display:inline-block;
                            color:#ffffff !important;font-size:13px;
                            font-weight:700;padding:11px 22px;
                            text-decoration:none;border-radius:8px;">
                    Read Full Article &rarr;
                  </a>
                </td>
                <td style="padding-left:10px;">
                  <span style="font-family:Arial,sans-serif;background:#f0f0f0;
                               color:#555555;padding:11px 16px;
                               border-radius:8px;font-size:12px;
                               display:inline-block;">
                    📋 Copy &amp; paste into LinkedIn
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>""")

    source_pills = "".join([
        f'<span style="font-family:Arial,sans-serif;display:inline-block;'
        f'background:{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]};'
        f'color:#ffffff;padding:4px 12px;border-radius:20px;font-size:12px;'
        f'font-weight:700;margin:3px;">'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["emoji"]} '
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
<body style="margin:0;padding:0;background:#f4f6f9;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;">

        <!-- Header -->
        <tr>
          <td style="background:#0077b5;padding:36px 32px;border-radius:16px;
                     text-align:center;">
            <div style="font-size:40px;margin-bottom:10px;">📰</div>
            <h1 style="font-family:Arial,sans-serif;color:#ffffff;margin:0 0 8px;
                       font-size:24px;font-weight:800;letter-spacing:-0.5px;">
              Your Daily LinkedIn Content
            </h1>
            <p style="font-family:Arial,sans-serif;color:#cce5ff;margin:0 0 16px;
                       font-size:15px;">{date_str}</p>
            <span style="font-family:Arial,sans-serif;display:inline-block;
                         background:rgba(255,255,255,0.15);padding:6px 20px;
                         border-radius:20px;color:#ffffff;font-size:13px;">
              {len(results)} articles curated across {unique_sources} source types
            </span>
          </td>
        </tr>

        <tr><td style="height:24px;">&nbsp;</td></tr>

        <!-- Source pills -->
        <tr>
          <td style="background:#ffffff;padding:16px 20px;border-radius:12px;
                     border:1px solid #e8e8e8;">
            <p style="font-family:Arial,sans-serif;margin:0 0 10px;font-size:11px;
                       color:#888888;text-transform:uppercase;
                       letter-spacing:0.8px;font-weight:700;">
              Today's sources
            </p>
            <div>{source_pills}</div>
          </td>
        </tr>

        <tr><td style="height:28px;">&nbsp;</td></tr>

        <!-- Article cards -->
        <tr>
          <td>
            {"".join(sections)}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="text-align:center;padding:24px 0;
                     border-top:1px solid #e0e0e0;">
            <p style="font-family:Arial,sans-serif;color:#aaaaaa;font-size:12px;
                       margin:0 0 4px;">
              Generated by your LinkedIn Content Agent
            </p>
            <p style="font-family:Arial,sans-serif;color:#bbbbbb;font-size:11px;
                       margin:0;">
              Pioneered by Koushik &middot; Powered by Claude Haiku &middot;
              Running on GitHub Actions
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

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

    print("\nStep 6/6 — Claude Haiku: 10 independent picks...")
    results = rank_and_draft(reddit, google_other, new_sources)
    print(f"  {len(results)} articles selected")

    print("\nSending HTML email with images...")
    send_email(results)
    print("Done!")


if __name__ == "__main__":
    main()

import feedparser
import anthropic
import requests
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── SOURCES ──────────────────────────────────────────────────────────────────

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

# ── HELPERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_rss_articles(feeds: list[str], max_age_hours: int = None) -> list[dict]:
    """Fetch articles from RSS feeds. If max_age_hours is set, filters by recency."""
    articles = []
    cutoff = datetime.now() - timedelta(hours=max_age_hours) if max_age_hours else None

    for url in feeds:
        try:
            feed = feedparser.parse(url)
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
                })
        except Exception as e:
            print(f"RSS error ({url}): {e}")

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
                if title and len(title) > 15:
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": "",
                        "source":  url,
                    })

        except Exception as e:
            print(f"Medium scrape error ({url}): {e}")

    return articles[:10]


def fetch_blog_articles(urls: list[str]) -> list[dict]:
    """Scrape article titles and links from The Product Folks and Jefago."""
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
                if title and len(title) > 15:
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": "",
                        "source":  url,
                    })

        except Exception as e:
            print(f"Blog scrape error ({url}): {e}")

    return articles[:10]


# ── CLAUDE ───────────────────────────────────────────────────────────────────

def rank_and_draft(reddit_articles: list[dict], other_articles: list[dict]) -> str:
    """Send articles to Claude Haiku. Force 1 from Reddit, 1 from other sources."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def format_list(articles, label):
        return f"── {label} ──\n\n" + "\n\n".join([
            f"[{i+1}] Title: {a['title']}\n"
            f"Source: {a['source']}\n"
            f"URL: {a['link']}\n"
            f"Summary: {a['summary'] or 'No summary available'}"
            for i, a in enumerate(articles[:20])
        ])

    reddit_block = format_list(reddit_articles, "REDDIT ARTICLES (pick exactly 1)")
    other_block  = format_list(other_articles,  "OTHER SOURCES — Google News / Medium / Blogs (pick exactly 1)")

    prompt = f"""You are a LinkedIn content strategist for a Product Manager based in India.
Today is {datetime.now().strftime('%B %d, %Y')}.

You MUST pick exactly:
- 1 article from the REDDIT section
- 1 article from the OTHER SOURCES section

For each article write a LinkedIn post of 150-200 words: strong hook, 3 punchy insights, closing question to drive comments. Tone: professional but conversational.

{reddit_block}

{other_block}

Respond in this exact format and nothing else:

ARTICLE 1 (from Reddit):
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

LINKEDIN POST 1:
[full post text]

---

ARTICLE 2 (from Other Sources):
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

LINKEDIN POST 2:
[full post text]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def send_email(content: str):
    """Send the ranked articles and LinkedIn drafts via Gmail SMTP."""
    sender    = os.environ["GMAIL_ADDRESS"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001F4F0 Your LinkedIn posts for "
        f"{datetime.now().strftime('%b %d, %Y')} — ready to publish"
    )
    msg["From"] = sender
    msg["To"]   = recipient

    body = (
        f"Good morning! Here are your top 2 articles and LinkedIn drafts for today.\n\n"
        f"{'='*60}\n\n"
        f"{content}\n\n"
        f"{'='*60}\n"
        f"Generated by your LinkedIn Content Agent\n"
    )

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print("Email sent successfully.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/5 — Fetching Reddit RSS (historical, no date limit)...")
    reddit_articles = fetch_rss_articles(REDDIT_FEEDS, max_age_hours=None)
    print(f"  Found {len(reddit_articles)} Reddit articles")

    print("Step 2/5 — Fetching Google News RSS (recent 48 hours only)...")
    google_articles = fetch_rss_articles(GOOGLE_NEWS_FEEDS, max_age_hours=48)
    print(f"  Found {len(google_articles)} Google News articles")

    print("Step 3/5 — Scraping Medium profiles (historical)...")
    medium_articles = fetch_medium_articles(MEDIUM_URLS)
    print(f"  Found {len(medium_articles)} Medium articles")

    print("Step 4/5 — Scraping PM blogs (historical)...")
    blog_articles = fetch_blog_articles(BLOG_URLS)
    print(f"  Found {len(blog_articles)} blog articles")

    other_articles = google_articles + medium_articles + blog_articles

    print(f"\nTotal — Reddit: {len(reddit_articles)} | Others: {len(other_articles)}")

    if not reddit_articles and not other_articles:
        print("No articles found today. Exiting.")
        return

    print("\nStep 5/5 — Sending to Claude Haiku for ranking and drafting...")
    content = rank_and_draft(reddit_articles, other_articles)

    print("\nSending email...")
    send_email(content)
    print("Done!")


if __name__ == "__main__":
    main()

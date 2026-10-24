#!/usr/bin/env python3
"""Scrape the public Telegram preview of @offerssuperfast into data/posts.json.

Free, no API keys. Uses https://t.me/s/<channel> and pages back with ?before=<id>.
Affiliate links are kept exactly as posted.
Usage: python scripts/scrape.py [--channel offerssuperfast] [--limit 60]
"""
import argparse, html, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone
from bs4 import BeautifulSoup, NavigableString, Tag

UA = "Mozilla/5.0 (compatible; OffersSuperFastSite/1.0)"
STORE_PATTERNS = [
    ("amazon", re.compile(r"(?:^|\.)(amazon\.[a-z.]+|amzn\.to|amzn\.in|amzn\.eu|a\.co)$", re.I)),
    ("flipkart", re.compile(r"(?:^|\.)(flipkart\.com|fkrt\.it|fkrt\.co|fkrt\.cc|dl\.flipkart\.com)$", re.I)),
]
ALLOWED_TAGS = {"a", "br", "b", "strong", "i", "em", "u", "s", "code", "pre", "tg-emoji"}
BG_RE = re.compile(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)")


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            print(f"fetch failed ({e}), retry {i+1}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"could not fetch {url}")


def store_of(url):
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return None
    for name, rx in STORE_PATTERNS:
        if rx.search(host.lower()):
            return name
    return None


def safe_html(node):
    """Rebuild message HTML keeping only basic formatting + links (href untouched)."""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(html.escape(str(child), quote=False))
        elif isinstance(child, Tag):
            name = child.name.lower()
            if name == "br":
                out.append("<br>")
            elif name == "a":
                href = child.get("href", "")
                if TME_MENTION.match(href):  # Telegram turns "@1149" into a fake mention link
                    out.append(safe_html(child))
                elif href.startswith(("http://", "https://", "tg://")):
                    out.append(f'<a href="{html.escape(href)}" target="_blank" rel="noopener nofollow sponsored">{safe_html(child)}</a>')
                else:
                    out.append(safe_html(child))
            elif name in ALLOWED_TAGS and name != "tg-emoji":
                out.append(f"<{name}>{safe_html(child)}</{name}>")
            elif name == "i" or "emoji" in (child.get("class") or []):
                out.append(safe_html(child))
            else:
                out.append(safe_html(child))
    return "".join(out)


PRICE_RES = [
    re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I),
    re.compile(r"@\s*(?:₹|rs\.?)?\s*([0-9][0-9,]*(?:\.\d+)?)", re.I),
]
OFF_CONTEXT = re.compile(r"(off|cashback|coupon|discount|save)", re.I)


DEAL_RE = re.compile(r"(?:deal|price|fast|loot)\W{0,6}(?:₹|rs\.?)?\s*([0-9][0-9,]{1,8})\b", re.I)
BARE_RE = re.compile(r"^\W{0,3}([0-9][0-9,]{1,8})(?:/-)?\s*(?::|$|https?://)", re.I)
MRP_RE = re.compile(r"(?:regular|mrp|m\.r\.p)\W{0,6}(?:₹|rs\.?)?\s*([0-9][0-9,]{1,8})", re.I)
TME_MENTION = re.compile(r"^https?://t\.me/\d+/?$")
URL_RE = re.compile(r"https?://\S+")


def detect_mrp(text):
    m = MRP_RE.search(text)
    return m.group(1) if m else None


def make_title(text, store):
    for line in text.split("\n"):
        clean = URL_RE.sub("", line).strip(" :|-–📎🔗👇➡️⚡️")
        # skip lines that are just numbers / punctuation / emoji
        if sum(ch.isalpha() for ch in clean) >= 4 and not re.match(r"^(\(?final\)?\s*\|?|regular|mrp)\W", clean, re.I):
            return clean[:160]
    return f"{(store or 'Hot').title()} Deal"


def detect_price(text):
    for line in text.split("\n"):
        m = BARE_RE.search(line.strip())
        if m and not OFF_CONTEXT.search(line):
            return m.group(1)
    m = DEAL_RE.search(text)
    if m and not OFF_CONTEXT.search(text[m.start():m.end() + 6]):
        return m.group(1)
    return _detect_price(text)


def _detect_price(text):
    first = text.strip().split("\n")[0] if text.strip() else ""
    # Prefer '@price' anywhere (channel convention), then ₹ in first line, then any ₹ not about discounts.
    m = PRICE_RES[1].search(text)
    if m:
        return m.group(1).rstrip(".,")
    m = PRICE_RES[0].search(first)
    if m:
        return m.group(1).rstrip(".,")
    for line in text.split("\n"):
        if OFF_CONTEXT.search(line):
            continue
        m = PRICE_RES[0].search(line)
        if m:
            return m.group(1).rstrip(".,")
    return None


def parse_page(page_html, channel):
    soup = BeautifulSoup(page_html, "html.parser")
    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        msg = wrap.select_one(".tgme_widget_message[data-post]")
        if not msg:
            continue
        try:
            pid = int(msg["data-post"].split("/")[-1])
        except ValueError:
            continue
        text_el = msg.select_one(".tgme_widget_message_text")
        text = ""
        body_html = ""
        links = []
        if text_el:
            body_html = safe_html(text_el)
            tmp = BeautifulSoup(str(text_el), "html.parser")
            for br in tmp.find_all("br"):
                br.replace_with("\n")
            text = tmp.get_text().strip()
            for a in text_el.find_all("a", href=True):
                if a["href"] not in links and not TME_MENTION.match(a["href"]):
                    links.append(a["href"])
        # also catch bare urls in text not wrapped in <a>
        for u in re.findall(r"https?://[^\s<>\"]+", text):
            if u not in links and not TME_MENTION.match(u):
                links.append(u)
        # images: photos, video thumbs, link previews
        images = []
        for el in msg.select(".tgme_widget_message_photo_wrap, .tgme_widget_message_video_thumb, .link_preview_image, .tgme_widget_message_link_preview .link_preview_right_image"):
            m = BG_RE.search(el.get("style", ""))
            if m and m.group(1) not in images:
                images.append(m.group(1))
        t = msg.select_one("time[datetime]")
        date = t["datetime"] if t else None
        store_links = [{"store": store_of(u), "url": u} for u in links if store_of(u)]
        other_links = [u for u in links if not store_of(u) and "t.me/" not in u]
        store = store_links[0]["store"] if store_links else None
        views = msg.select_one(".tgme_widget_message_views")
        posts.append({
            "id": pid,
            "url": f"https://t.me/{channel}/{pid}",
            "date": date,
            "title": make_title(text, store),
            "text": text,
            "html": body_html,
            "image": images[0] if images else None,
            "images": images,
            "price": detect_price(text),
            "mrp": detect_mrp(text),
            "links": links,
            "store_links": store_links,
            "store": store or ("other" if other_links else None),
            "buy_url": store_links[0]["url"] if store_links else (other_links[0] if other_links else None),
            "views": views.get_text(strip=True) if views else None,
        })
    return posts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="offerssuperfast")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "posts.json"))
    args = ap.parse_args()

    collected = {}
    before = None
    for _ in range(15):  # safety cap on pages
        url = f"https://t.me/s/{args.channel}" + (f"?before={before}" if before else "")
        page = parse_page(fetch(url), args.channel)
        if not page:
            break
        for p in page:
            collected[p["id"]] = p
        oldest = min(p["id"] for p in page)
        if len(collected) >= args.limit or (before is not None and oldest >= before):
            break
        before = oldest
        time.sleep(1)

    posts = sorted(collected.values(), key=lambda p: p["id"], reverse=True)
    # skip empty service posts (no text and no image)
    posts = [p for p in posts if p["text"] or p["image"]][: args.limit]
    out = {
        "channel": args.channel,
        "channel_url": f"https://t.me/{args.channel}",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(posts),
        "posts": posts,
    }
    # Don't rewrite the file if only view counts changed (keeps git history quiet).
    def sig(ps):
        return [{k: v for k, v in p.items() if k != "views"} for p in ps]
    try:
        with open(args.out, encoding="utf-8") as f:
            old = json.load(f)
        if sig(old.get("posts", [])) == sig(posts):
            print(f"No new deals ({len(posts)} posts unchanged); not rewriting {args.out}")
            return
    except (FileNotFoundError, ValueError):
        pass
    if not posts:
        sys.exit("Scraped 0 posts - refusing to overwrite existing data")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)
    with_link = sum(1 for p in posts if p["buy_url"])
    print(f"Saved {len(posts)} posts ({with_link} with store links, {sum(1 for p in posts if p['image'])} with images) -> {args.out}")


if __name__ == "__main__":
    import urllib.parse  # noqa
    main()

# Offers SuperFast – deals website

A free, static deals site that mirrors the public Telegram channel
[t.me/offerssuperfast](https://t.me/offerssuperfast). New posts appear on the site automatically
(about every 15 minutes). Affiliate links are kept exactly as posted.

```
index.html                 the page
assets/style.css, app.js   design + logic (search, Amazon/Flipkart filters, auto-refresh)
data/posts.json            latest ~60 posts (written by the scraper)
scripts/scrape.py          scraper for https://t.me/s/offerssuperfast (no API key needed)
.github/workflows/update.yml   runs the scraper every 15 min and commits posts.json
```

## Run locally
```bash
pip install -r requirements.txt
python scripts/scrape.py            # updates data/posts.json
python -m http.server 8000          # open http://localhost:8000
```
(Opening index.html directly from disk won't load posts.json; use a local server.)

## Deploy for free (auto-updating)
1. Create a free GitHub account and a new **public** repository (e.g. `offerssuperfast-site`).
2. Upload all files from this folder (keep the `.github` folder) to the `main` branch.
3. In the repo: **Settings → Actions → General → Workflow permissions → "Read and write"** → Save.
4. **Actions** tab → enable workflows → "Update deals from Telegram" → **Run workflow** once to test.
5. Host it (pick one):
   - **GitHub Pages:** Settings → Pages → Source "Deploy from a branch" → `main` / root.
     Site: `https://<username>.github.io/offerssuperfast-site/`
   - **Netlify / Cloudflare Pages:** "Import from GitHub", pick the repo, no build command,
     publish directory `/`. Every commit from the workflow redeploys automatically.
6. Optional custom domain (e.g. `offerssuperfast.in`, ~₹500–900/yr): add it in the host's
   domain settings, then update the `canonical` URL in `index.html`.

Notes
- GitHub can delay scheduled runs by a few minutes; and it pauses schedules in repos with no
  activity for 60 days (the bot's own commits count as activity while deals are posted).
- Change how many posts are kept with `--limit` in the workflow file.
- The page re-checks posts.json every 5 minutes, so open tabs update by themselves.

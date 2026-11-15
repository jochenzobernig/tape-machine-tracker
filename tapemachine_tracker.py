import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import os
import feedparser

st.set_page_config(page_title="Tape Radar", page_icon="📼", layout="wide")

HISTORY_FILE = os.path.expanduser("~/tape_radar_history.json")

DEFAULT_MODELS = ["Tascam ATR60", "Tascam MS16", "Otari MX-70"]
PLATFORMS = {
    "Willhaben.at": "willhaben.at",
    "Kleinanzeigen.de": "kleinanzeigen.de",
    "Reverb.com": "reverb.com"
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(urls):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(set(urls)), f, indent=2)

def fetch_google_rss(query, site_domain):
    search_term = f'"{query}" site:{site_domain}'
    encoded_query = urllib.parse.quote(search_term)
    rss_url = f"https://google.com{encoded_query}&hl=de&gl=AT&ceid=AT:de"
    feed = feedparser.parse(rss_url)
    results = []
    for entry in feed.entries:
        results.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.get("published", "Unbekanntes Datum"),
            "source": site_domain,
            "model": query
        })
    return results

def fetch_kleinanzeigen_direct(query):
    results = []
    slug = query.lower().replace(" ", "-")
    url = f"https://kleinanzeigen.de{slug}/k0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("article.aditem"):
                title_el = item.select_one("a.ellipsis")
                price_el = item.select_one("p.aditem-main--middle--price-shipping--price")
                loc_el = item.select_one("div.aditem-main--top--left")
                if title_el:
                    href = title_el.get("href", "")
                    full_link = f"https://kleinanzeigen.de{href}" if href.startswith("/") else href
                    price = price_el.get_text(strip=True) if price_el else "VB / k.A."
                    loc = loc_el.get_text(strip=True) if loc_el else ""
                    results.append({
                        "title": f"{title_el.get_text(strip=True)} ({price} | {loc})",
                        "link": full_link,
                        "published": "Aktuell gelistet",
                        "source": "kleinanzeigen.de",
                        "model": query
                    })
    except Exception:
        pass
    return results

def get_direct_search_links(query):
    q_enc = urllib.parse.quote(query)
    return {
        "Willhaben.at": f"https://willhaben.at{q_enc}",
        "Kleinanzeigen.de": f"https://kleinanzeigen.de{query.lower().replace(' ', '-')}/k0",
        "Reverb.com": f"https://reverb.com{q_enc}"
    }

st.title("📼 Tape Radar – Bandmaschinen Monitor")
st.markdown("Überwacht **Willhaben.at**, **Kleinanzeigen.de** und **Reverb.com** nach deinen gesuchten Maschinen.")

st.sidebar.header("Such-Einstellungen")
models_input = st.sidebar.text_area(
    "Gesuchte Modelle (eine pro Zeile):",
    value="\n".join(DEFAULT_MODELS),
    height=120
)
models = [m.strip() for m in models_input.split("\n") if m.strip()]

selected_platforms = st.sidebar.multiselect(
    "Plattformen:",
    options=list(PLATFORMS.keys()),
    default=list(PLATFORMS.keys())
)

if st.sidebar.button("Verlauf zurücksetzen (alle als neu markieren)"):
    save_history([])
    st.sidebar.success("Verlauf gelöscht!")

with st.expander("🔗 Direkt-Links zu den Suchergebnissen (Live-Ansicht)", expanded=False):
    cols = st.columns(len(models) if models else 1)
    for idx, model in enumerate(models):
        with cols[idx % len(cols)]:
            st.subheader(model)
            links = get_direct_search_links(model)
            for p_name, p_url in links.items():
                if p_name in selected_platforms:
                    st.markdown(f"- [{p_name} öffnen]({p_url})")

st.divider()

if st.button("🔍 Jetzt nach Inseraten suchen", type="primary"):
    seen_urls = load_history()
    all_results = []

    with st.spinner("Durchsuche Plattformen und Indexe..."):
        for model in models:
            for p_name in selected_platforms:
                domain = PLATFORMS[p_name]
                rss_hits = fetch_google_rss(model, domain)
                all_results.extend(rss_hits)

                if domain == "kleinanzeigen.de":
                    direct_hits = fetch_kleinanzeigen_direct(model)
                    all_results.extend(direct_hits)

    unique_results = []
    seen_in_run = set()
    for r in all_results:
        if r["link"] not in seen_in_run:
            seen_in_run.add(r["link"])
            unique_results.append(r)

    new_count = sum(1 for r in unique_results if r["link"] not in seen_urls)

    st.subheader(f"Gefundene Treffer: {len(unique_results)} (davon {new_count} neu)")

    if not unique_results:
        st.info("Aktuell keine neuen Index-Treffer gefunden. Nutze oben die Direkt-Links für die Live-Suche.")
    else:
        for item in unique_results:
            is_new = item["link"] not in seen_urls
            badge = "🆕 **NEU** | " if is_new else ""
            with st.container(border=True):
                st.markdown(f"{badge}**[{item['model']}]** [{item['title']}]({item['link']})")
                st.caption(f"Plattform: {item['source']} • Gefunden/Datum: {item['published']}")

        updated_history = seen_urls + [r["link"] for r in unique_results]
        save_history(updated_history)
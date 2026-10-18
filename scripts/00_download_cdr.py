"""Download CDR "Call Reports -- Single Period" bulk ZIPs (tab delimited) for every quarter
in a range, straight into data/cdr_bulk/. Standard library only; run it in your own Terminal.

Usage:  python3 scripts/00_download_cdr.py                 # 2015Q1 .. latest
        python3 scripts/00_download_cdr.py 2015 2026        # year range
Skips quarters already present (as a ZIP or an unzipped folder).
"""
import http.cookiejar
import re
import sys
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
OUT = Path(__file__).resolve().parents[1] / "data" / "cdr_bulk"
OUT.mkdir(parents=True, exist_ok=True)
P = "ctl00$MainContentHolder$"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (Fintech590 coursework bulk download)")]


def hidden_fields(html):
    out = {}
    for tag in re.findall(r"<input[^>]+type=\"hidden\"[^>]*>", html):
        name = re.search(r'name="([^"]+)"', tag)
        val = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = unescape(val.group(1)) if val else ""
    return out


def post(fields):
    data = urllib.parse.urlencode(fields).encode()
    return opener.open(urllib.request.Request(URL, data=data), timeout=300)


def session():
    """Load the page and select 'Call Reports -- Single Period' so the date list populates."""
    html = opener.open(URL, timeout=60).read().decode("utf-8", "replace")
    st = hidden_fields(html)
    st.update({"__EVENTTARGET": P + "ListBox1", "__EVENTARGUMENT": "",
               P + "ListBox1": "ReportingSeriesSinglePeriod"})
    html = post(st).read().decode("utf-8", "replace")
    sel = re.search(r'<select[^>]+id="DatesDropDownList".*?</select>', html, re.S).group(0)
    dates = {text: val for val, text in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([\d/]+)</option>', sel)}
    return hidden_fields(html), dates


def main():
    y0, y1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (2015, 9999)
    st, dates = session()
    wanted = sorted((d for d in dates if y0 <= int(d[-4:]) <= y1), key=lambda d: (d[-4:], d[:5]))
    print(f"{len(wanted)} quarters available in range")
    for d in wanted:
        tag = d.replace("/", "")                             # 03/31/2026 -> 03312026
        if any(tag in p.name for p in OUT.iterdir()):
            print(f"  {d}: already have it, skipping")
            continue
        fields = dict(st)
        fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "",
                       P + "ListBox1": "ReportingSeriesSinglePeriod",
                       P + "DatesDropDownList": dates[d],
                       P + "FormatType": "TSVRadioButton",
                       P + "TabStrip1$Download_0": "Download"})
        for attempt in range(3):
            try:
                r = post(fields)
                cd = r.headers.get("Content-Disposition", "")
                if "attachment" not in cd:                   # got the form back: session expired
                    st, dates = session()
                    raise RuntimeError("no attachment, refreshed session")
                name = re.search(r'filename="?([^";]+)', cd).group(1)
                tmp = OUT / (name + ".part")
                tmp.write_bytes(r.read())
                tmp.rename(OUT / name)
                print(f"  {d}: {name} ({(OUT / name).stat().st_size / 1e6:.1f} MB)")
                break
            except Exception as e:
                print(f"  {d}: attempt {attempt + 1} failed ({e})")
                time.sleep(5)
        time.sleep(1)                                        # be polite to the server
    print(f"done -> {OUT}")


if __name__ == "__main__":
    main()

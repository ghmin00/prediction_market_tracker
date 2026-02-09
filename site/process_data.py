#!/usr/bin/env python3
"""Pre-process kalshi_polymarket_merged.csv into JSON files for the website."""

import csv
import json
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "kalshi_polymarket_merged.csv"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def read_csv():
    rows = []
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["notional_volume_usd"] = float(row["notional_volume_usd"] or 0)
            row["open_interest_usd"] = float(row["open_interest_usd"] or 0)
            row["category"] = row["category"].strip('"')
            row["subcategory"] = row["subcategory"].strip('"')
            row["subsubcategory"] = row["subsubcategory"].strip('"')
            row["date"] = row["timestamp"][:10]
            row["month"] = row["timestamp"][:7]
            rows.append(row)
    return rows


def page1_platform_war(rows):
    """Monthly volume by source, overall and per-category."""
    monthly = defaultdict(lambda: defaultdict(float))
    monthly_cat = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    for r in rows:
        monthly[r["month"]][r["source"]] += r["notional_volume_usd"]
        monthly_cat[r["month"]][r["category"]][r["source"]] += r["notional_volume_usd"]

    months = sorted(monthly.keys())
    categories = sorted({r["category"] for r in rows} - {"UNKNOWN", "Unknown", "Early Polymarket Trades"})

    overall = []
    for m in months:
        kv = monthly[m].get("Kalshi", 0)
        pv = monthly[m].get("Polymarket", 0)
        total = kv + pv
        overall.append({
            "month": m,
            "kalshi": round(kv),
            "polymarket": round(pv),
            "total": round(total),
            "kalshi_pct": round(kv / total * 100, 1) if total else 0,
            "poly_pct": round(pv / total * 100, 1) if total else 0,
        })

    by_category = {}
    for cat in categories:
        cat_data = []
        for m in months:
            kv = monthly_cat[m].get(cat, {}).get("Kalshi", 0)
            pv = monthly_cat[m].get(cat, {}).get("Polymarket", 0)
            total = kv + pv
            if total > 0:
                cat_data.append({
                    "month": m,
                    "kalshi": round(kv),
                    "polymarket": round(pv),
                    "kalshi_pct": round(kv / total * 100, 1) if total else 0,
                    "poly_pct": round(pv / total * 100, 1) if total else 0,
                })
        by_category[cat] = cat_data

    with open(DATA_DIR / "platform_war.json", "w") as f:
        json.dump({"overall": overall, "by_category": by_category, "categories": categories}, f)


def page2_arbitrage(rows):
    """Cross-platform volume ratios at subcategory level."""
    kalshi = defaultdict(float)
    poly = defaultdict(float)

    for r in rows:
        key = f"{r['category']}|{r['subcategory']}"
        if r["source"] == "Kalshi":
            kalshi[key] += r["notional_volume_usd"]
        else:
            poly[key] += r["notional_volume_usd"]

    all_keys = set(list(kalshi.keys()) + list(poly.keys()))
    markets = []
    for k in all_keys:
        cat, sub = k.split("|", 1)
        if cat in ("UNKNOWN", "Unknown", "Early Polymarket Trades"):
            continue
        kv = kalshi.get(k, 0)
        pv = poly.get(k, 0)
        total = kv + pv
        if total < 10000:
            continue
        if kv == 0:
            ratio = None
            leader = "Polymarket-only"
        elif pv == 0:
            ratio = None
            leader = "Kalshi-only"
        else:
            ratio = round(max(pv / kv, kv / pv), 1)
            leader = "Polymarket" if pv > kv else "Kalshi"
        markets.append({
            "category": cat,
            "subcategory": sub,
            "kalshi": round(kv),
            "polymarket": round(pv),
            "total": round(total),
            "ratio": ratio,
            "leader": leader,
        })

    markets.sort(key=lambda x: -(x["ratio"] or 999999))

    with open(DATA_DIR / "arbitrage.json", "w") as f:
        json.dump(markets, f)


def page3_wash_trading(rows):
    """Turnover ratios at subsubcategory level."""
    data = defaultdict(lambda: {
        "kalshi_vol": 0, "poly_vol": 0,
        "kalshi_oi": 0, "poly_oi": 0,
        "kalshi_days": 0, "poly_days": 0,
    })

    for r in rows:
        key = f"{r['category']}|{r['subcategory']}|{r['subsubcategory']}"
        src = r["source"]
        if src == "Kalshi":
            data[key]["kalshi_vol"] += r["notional_volume_usd"]
            data[key]["kalshi_oi"] += r["open_interest_usd"]
            if r["notional_volume_usd"] > 0:
                data[key]["kalshi_days"] += 1
        else:
            data[key]["poly_vol"] += r["notional_volume_usd"]
            data[key]["poly_oi"] += r["open_interest_usd"]
            if r["notional_volume_usd"] > 0:
                data[key]["poly_days"] += 1

    results = []
    for key, d in data.items():
        parts = key.split("|", 2)
        cat, sub, sub3 = parts[0], parts[1], parts[2]
        if cat in ("UNKNOWN", "Unknown", "Early Polymarket Trades"):
            continue

        for src in ["Kalshi", "Polymarket"]:
            vol = d["kalshi_vol"] if src == "Kalshi" else d["poly_vol"]
            oi = d["kalshi_oi"] if src == "Kalshi" else d["poly_oi"]
            days = d["kalshi_days"] if src == "Kalshi" else d["poly_days"]
            if vol < 1_000_000 or oi < 100_000 or days == 0:
                continue
            avg_oi = oi / days
            turnover = vol / avg_oi if avg_oi > 0 else 0
            results.append({
                "source": src,
                "category": cat,
                "subcategory": sub,
                "market": sub3,
                "volume": round(vol),
                "avg_oi": round(avg_oi),
                "days": days,
                "turnover": round(turnover, 1),
            })

    results.sort(key=lambda x: -x["turnover"])

    with open(DATA_DIR / "wash_trading.json", "w") as f:
        json.dump(results, f)


def page4_election(rows):
    """Daily volume for politics/elections around election events."""
    # Daily total volume by platform
    daily_total = defaultdict(lambda: defaultdict(float))
    # Daily politics volume
    daily_politics = defaultdict(lambda: defaultdict(float))
    # Daily US elections volume
    daily_elections = defaultdict(lambda: defaultdict(float))

    for r in rows:
        daily_total[r["date"]][r["source"]] += r["notional_volume_usd"]
        if r["category"] == "Politics":
            daily_politics[r["date"]][r["source"]] += r["notional_volume_usd"]
        if r["subcategory"] == "US Elections":
            daily_elections[r["date"]][r["source"]] += r["notional_volume_usd"]

    dates = sorted(set(list(daily_total.keys())))

    def build_series(data_dict):
        series = []
        for d in dates:
            kv = data_dict.get(d, {}).get("Kalshi", 0)
            pv = data_dict.get(d, {}).get("Polymarket", 0)
            if kv > 0 or pv > 0:
                series.append({"date": d, "kalshi": round(kv), "polymarket": round(pv)})
        return series

    elections = [
        {"date": "2024-11-05", "label": "2024 US Presidential Election"},
        {"date": "2022-11-08", "label": "2022 US Midterms"},
    ]

    with open(DATA_DIR / "election.json", "w") as f:
        json.dump({
            "total": build_series(daily_total),
            "politics": build_series(daily_politics),
            "us_elections": build_series(daily_elections),
            "election_events": elections,
        }, f)


def page5_concentration(rows):
    """Volume concentration by category and subcategory."""
    cat_vol = defaultdict(float)
    sub_vol = defaultdict(lambda: defaultdict(float))
    cat_src = defaultdict(lambda: defaultdict(float))

    for r in rows:
        if r["category"] in ("UNKNOWN", "Unknown", "Early Polymarket Trades"):
            continue
        cat_vol[r["category"]] += r["notional_volume_usd"]
        sub_vol[r["category"]][r["subcategory"]] += r["notional_volume_usd"]
        cat_src[r["category"]][r["source"]] += r["notional_volume_usd"]

    grand_total = sum(cat_vol.values())

    treemap = []
    for cat in sorted(cat_vol, key=lambda c: -cat_vol[c]):
        children = []
        for sub in sorted(sub_vol[cat], key=lambda s: -sub_vol[cat][s]):
            sv = sub_vol[cat][sub]
            if sv < 100000:
                continue
            children.append({
                "name": sub,
                "value": round(sv),
                "pct": round(sv / grand_total * 100, 2),
            })
        treemap.append({
            "name": cat,
            "value": round(cat_vol[cat]),
            "pct": round(cat_vol[cat] / grand_total * 100, 1),
            "kalshi_pct": round(cat_src[cat].get("Kalshi", 0) / cat_vol[cat] * 100, 1) if cat_vol[cat] else 0,
            "children": children,
        })

    with open(DATA_DIR / "concentration.json", "w") as f:
        json.dump({"total": round(grand_total), "categories": treemap}, f)


def page6_timelapse(rows):
    """Daily volume by subcategory in compact format for animated treemap."""
    skip_cats = {"UNKNOWN", "Unknown", "Early Polymarket Trades"}

    # 1. Accumulate total volume per subcategory key to filter later
    total_by_key = defaultdict(float)
    daily_vol = defaultdict(lambda: defaultdict(float))

    for r in rows:
        if r["category"] in skip_cats:
            continue
        key = (r["category"], r["subcategory"])
        total_by_key[key] += r["notional_volume_usd"]
        daily_vol[r["date"]][key] += r["notional_volume_usd"]

    # 2. Filter subcategories with >= $100K total volume, sorted by total desc
    keys = sorted(
        [k for k, v in total_by_key.items() if v >= 100_000],
        key=lambda k: -total_by_key[k],
    )
    subcategories = [{"cat": k[0], "sub": k[1]} for k in keys]

    # 3. Build date list and 2D volume array
    dates = sorted(daily_vol.keys())
    volumes = []
    for d in dates:
        day_data = daily_vol[d]
        volumes.append([round(day_data.get(k, 0)) for k in keys])

    result = {
        "subcategories": subcategories,
        "dates": dates,
        "volumes": volumes,
    }

    with open(DATA_DIR / "timelapse.json", "w") as f:
        json.dump(result, f)

    print(f"  {len(subcategories)} subcategories, {len(dates)} days")


if __name__ == "__main__":
    print("Reading CSV...")
    rows = read_csv()
    print(f"  {len(rows)} rows loaded")

    print("Generating page 1: Platform War...")
    page1_platform_war(rows)

    print("Generating page 2: Arbitrage Map...")
    page2_arbitrage(rows)

    print("Generating page 3: Wash Trading...")
    page3_wash_trading(rows)

    print("Generating page 4: Election Impact...")
    page4_election(rows)

    print("Generating page 5: Concentration...")
    page5_concentration(rows)

    print("Generating page 6: Time Lapse...")
    page6_timelapse(rows)

    print("Done! JSON files written to data/")

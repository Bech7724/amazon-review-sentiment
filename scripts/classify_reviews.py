#!/usr/bin/env python3
"""
classify_reviews.py — three-class sentiment scoring for the Amazon Gift Cards reviews.

Pipeline:
  1. Load (or auto-download) the Amazon Reviews '23 "Gift Cards" JSONL gz file.
  2. Pull a balanced sample: 50 reviews per class (POSITIVE=4-5*, NEUTRAL=3*, NEGATIVE=1-2*),
     fixed seed so the same set comes up every run.
  3. Ask the LLM endpoint to classify each review by TITLE + TEXT ONLY (never the rating),
     all reviews in one numbered message (a separate user turn per review makes the model
     answer only once — see README bug notes).
  4. Score predictions against the rating-derived ground truth; write raw output, the parsed
     predictions, and the agreement/confusion numbers.

The rubric (professor's rule):  4-5* -> POSITIVE | 3* -> NEUTRAL | 1-2* -> NEGATIVE

Auth: the endpoint key is read ONLY from the DOBOLYI_KEY environment variable — it is never
hard-coded or written into any output file.

Usage:
    export DOBOLYI_KEY=your-key
    python scripts/classify_reviews.py            # balanced 150 (50/class), seed 2026
    python scripts/classify_reviews.py --n 30     # smaller sample for a quick test
    python scripts/classify_reviews.py --seed 7   # choose your own fixed seed
"""

import argparse, gzip, json, os, random, re, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Gift_Cards.jsonl.gz"
DATA_PATH = os.path.join(HERE, "data", "Gift_Cards.jsonl.gz")
EMO_KEY_ENV = "DOBOLYI_KEY"

def label_of(rating: float) -> str:
    if rating >= 4: return "POSITIVE"
    if rating < 3: return "NEGATIVE"
    return "NEUTRAL"  # 3.0

def load_reviews(max_rows=None):
    if not os.path.exists(DATA_PATH):
        print("downloading gift card reviews ...")
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, DATA_PATH)
    rows = []
    with gzip.open(DATA_PATH, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows and i >= max_rows: break
            line = line.strip()
            if not line: continue
            o = json.loads(line)
            rows.append({"idx": i, "title": o.get("title") or "", "text": o.get("text") or "",
                         "rating": o.get("rating")})
    return rows

def build_balanced_sample(rows, per_class=50, seed=2026):
    pools = {"POSITIVE": [], "NEUTRAL": [], "NEGATIVE": []}
    for r in rows:
        pools[label_of(r["rating"])].append(r)
    rng = random.Random(seed)
    sample = []
    for cls in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
        sample += rng.sample(pools[cls], per_class)
    rng.shuffle(sample)
    for r in sample:
        r["true"] = label_of(r["rating"])
    return sample

def build_prompt(sample):
    blocks = []
    for i, r in enumerate(sample, 1):
        txt = r["text"].replace("<br />", " ").replace("<br/>", " ").replace("&#34;", '"')
        blocks.append(f"Review {i}:\nTitle: {r['title']}\nText: {txt}")
    return ("Below are %d product reviews. For EACH one classify the overall sentiment as EXACTLY ONE of: "
            "POSITIVE, NEUTRAL, or NEGATIVE.\n"
            "- POSITIVE: clearly favorable\n- NEUTRAL: mixed, matter-of-fact, or unremarkable\n"
            "- NEGATIVE: clearly unfavorable\n\n"
            "Reply strictly as a numbered list, one per line, in the format: 1: POSITIVE\n"
            "Use only the words POSITIVE, NEUTRAL, or NEGATIVE. No other text.\n\n" % len(sample)
            + "\n\n".join(blocks))

def call_endpoint(messages):
    key = os.environ.get(EMO_KEY_ENV)
    if not key:
        sys.exit(f"Set {EMO_KEY_ENV} to the endpoint key before running.")
    url = os.environ.get("DOBOLYI_URL", "http://dobolyi.com:9001/v1/chat/completions")
    model = os.environ.get("DOBOLYI_MODEL", "cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit")
    payload = {"model": model, "messages": messages, "temperature": 0.0,
               "max_tokens": 2000, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())

def parse_predictions(raw, n):
    preds = {}
    for m in re.finditer(r"(\d+)\s*[:.\-]\s*(POSITIVE|NEUTRAL|NEGATIVE)", raw):
        preds[int(m.group(1))] = m.group(2)
    out = []
    for i in range(1, n + 1):
        out.append(preds.get(i))  # None => model gave no parseable label for that row
    return out

def score(sample, preds, cls_order=("POSITIVE", "NEUTRAL", "NEGATIVE")):
    n = len(sample)
    agree = sum(1 for r, p in zip(sample, preds) if r["true"] == p)
    result = {"n": n, "agree": agree, "agree_pct": round(agree / n * 100, 1)}
    cm = {t: {p: 0 for p in cls_order} for t in cls_order}
    for r, p in zip(sample, preds):
        cm[r["true"]][p or "N/A"] = cm[r["true"]].get(p or "N/A", 0) + 1
    result["confusion"] = cm
    result["recall"] = {}
    result["precision"] = {}
    for c in cls_order:
        trues = [r for r in sample if r["true"] == c]
        hit = sum(1 for r in trues if r["pred"] == c)
        result["recall"][c] = {"correct": hit, "total": len(trues),
                               "pct": round(hit / len(trues) * 100, 1) if trues else None}
    for c in cls_order:
        preds_c = [r for r in sample if r["pred"] == c]
        hit = sum(1 for r in preds_c if r["true"] == c)
        result["precision"][c] = {"correct": hit, "total": len(preds_c),
                                  "pct": round(hit / len(preds_c) * 100, 1) if preds_c else None}
    result["misclassified"] = sum(1 for r, p in zip(sample, preds) if r["true"] != p)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="reviews per class (default 50)")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    rows = load_reviews()
    sample = build_balanced_sample(rows, per_class=args.n, seed=args.seed)
    print(f"balanced sample: {len(sample)} reviews (50/50/50): "
          f"{sorted({r['true'] for r in sample})}")

    prompt = build_prompt(sample)
    messages = [{"role": "system",
                 "content": "You classify review sentiment into three classes: POSITIVE, NEUTRAL, NEGATIVE."},
                {"role": "user", "content": prompt}]
    resp = call_endpoint(messages)

    # capture RAW model output (the deliverable "one balanced run's raw output")
    raw = resp["choices"][0]["message"]["content"]
    runs_dir = os.path.join(HERE, "runs"); os.makedirs(runs_dir, exist_ok=True)
    with open(os.path.join(runs_dir, "balanced3_raw_model_output.txt"), "w", encoding="utf-8") as f:
        f.write(raw)
    with open(os.path.join(runs_dir, "balanced3_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)

    preds = parse_predictions(raw, len(sample))
    for r, p in zip(sample, preds):
        r["pred"] = p

    scores = score(sample, preds)
    # drop the giant text field from the predictions JSON unless wanted; keep a slim copy too
    slim = [{k: r[k] for k in ("idx", "title", "text", "rating", "true", "pred")} for r in sample]
    with open(os.path.join(runs_dir, "balanced3_predictions.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"n_per_class": args.n, "seed": args.seed, "scores": scores},
                   "reviews": slim}, f, indent=2)

    print(json.dumps(scores, indent=2))
    print("wrote runs/balanced3_raw_model_output.txt, balanced3_prompt.txt, balanced3_predictions.json")

if __name__ == "__main__":
    main()

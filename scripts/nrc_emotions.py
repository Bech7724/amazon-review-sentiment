#!/usr/bin/env python3
"""
nrc_emotions.py — word-list emotion detector using the NRC Emotion Lexicon (EmoLex).

Reads a reviews JSON (default: runs/balanced3_predictions.json produced by classify_reviews.py),
tokenizes each review's title + text, and for every token adds the emotion associations the
lexicon flags (a word can associate with several of the 8 basic emotions). The per-emotion sums
are saved, and the emotion with the highest total is the "primary emotion" (argmax). Ties break
by a fixed order. This needs no model calls.

8 emotions (Plutchik): anger, anticipation, disgust, fear, joy, sadness, surprise, trust.

The NRC lexicon file (data/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt) is the public
"Word-Emotion Association Lexicon" (Mohammad & Turney, 2013).
"""

import argparse, json, os, re
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(HERE, "data", "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt")
EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
TOKEN = re.compile(r"[\w']+")

def load_lexicon():
    lex = {}
    with open(LEX, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) != 3:
                continue
            word, cat, flag = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
            if cat in EMOTIONS and flag == "1":
                lex.setdefault(word, set()).add(cat)
    return lex

def nrc_emotion(lex, text):
    scores = Counter()
    for token in TOKEN.findall((text or "").lower()):
        for e in lex.get(token, ()):
            scores[e] += 1
    if not scores:
        return None, dict(scores)
    mx = max(scores.values())
    for e in EMOTIONS:  # fixed tie-break order
        if scores[e] == mx:
            return e, dict(scores)
    return None, dict(scores)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(HERE, "runs", "balanced3_predictions.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "nrc_emotions.csv"))
    args = ap.parse_args()

    lex = load_lexicon()
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    import csv
    rows = data["reviews"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["idx", "title", "text", "rating", "true", "pred", "nrc_emotion"] +
                   ["score_" + e for e in EMOTIONS] + ["agree"])
        for r in rows:
            emo, scores = nrc_emotion(lex, r["title"] + " " + r["text"])
            w.writerow([r["idx"], r["title"], r["text"], r["rating"], r["true"], r["pred"],
                        emo or "NO_SIGNAL"] + [scores.get(e, 0) for e in EMOTIONS] +
                       [r["true"] == r["pred"]])

    dist = Counter(r.get("true") for r in rows)  # placeholder
    nemo = Counter()
    for r in rows:
        e, _ = nrc_emotion(lex, r["title"] + " " + r["text"])
        nemo[e] += 1
    print("NRC emotion distribution over", len(rows), "reviews:")
    print(dict(nemo))
    print("wrote", args.out)

if __name__ == "__main__":
    main()

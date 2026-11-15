"""
Upgrade 2: Bangla Handwritten Visual-Grapheme Confusion Matrix & Land Geo-Gazetteer.
Normalizes noisy handwritten Bangla OCR tokens while strictly preserving raw_ocr_text.
"""

# Visually similar Bangla characters in cursive Moharar (Deed Writer) handwriting
VISUAL_CONFUSION_GROUPS = [
    {"স", "ম", "ষ", "শ"},
    {"ব", "র", "ক", "ধ"},
    {"ড", "ড়", "ঙ", "উ"},
    {"ন", "ল", "ণ"},
    {"ত", "৩", "ও", "ভ"},
    {"প", "গ"},
    {"ট", "ঢ", "ঠ"},
    {"য", "ষ", "য়"},
    {"৪", "8", "b"},
    {"০", "O", "o", "0"},
    {"১", "৭", "1"},
    {"৫", "৬", "5"},
    {"া", "ো", "ে"},
]

def _substitution_cost(c1, c2):
    if c1 == c2:
        return 0.0
    for grp in VISUAL_CONFUSION_GROUPS:
        if c1 in grp and c2 in grp:
            return 0.18  # Low penalty for known handwritten visual lookalikes
    return 1.0

def weighted_grapheme_distance(s1, s2):
    """
    Computes weighted edit distance between noisy OCR token s1 and canonical dictionary entry s2.
    """
    m, n = len(s1), len(s2)
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i * 0.8
    for j in range(n + 1):
        dp[0][j] = j * 0.8

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = _substitution_cost(s1[i - 1], s2[j - 1])
            dp[i][j] = min(
                dp[i - 1][j] + 0.75,      # Deletion (e.g., dropped matra/kar)
                dp[i][j - 1] + 0.75,      # Insertion
                dp[i - 1][j - 1] + cost   # Visual substitution
            )
    return round(dp[m][n], 3)


class BangladeshLandGazetteer:
    """
    Authoritative local lexicon for Bangladesh Land Administration terms,
    Deed Categories, Land Units, and Gazipur/Dhaka/Tangail administrative hierarchy.
    """

    CATALOG = {
        "deed_type": [
            "বেল এওয়াজে হেবা দলিল",
            "সাফ কবলা দলিল",
            "বায়নাপত্র দলিল",
            "বণ্টননামা দলিল",
            "দানপত্র দলিল",
            "বন্ধকী দলিল",
            "এওয়াজ বদল দলিল"
        ],
        "mouza": [
            "বারেন্ডা",
            "সারদাগঞ্জ",
            "কাশিমপুর",
            "কোনাবাড়ী",
            "জয়দেবপুর",
            "টঙ্গী",
            "ধনবাড়ী",
            "মধুপুর"
        ],
        "union_parishad": [
            "কাশিমপুর",
            "বাসন",
            "কাউলতিয়া",
            "মির্জাপুর",
            "পাইস্কা"
        ],
        "thana_upazila": [
            "গাজীপুর সদর",
            "কালিয়াকৈর",
            "শ্রীপুর",
            "কাপাসিয়া",
            "কালীগঞ্জ",
            "ধনবাড়ী",
            "সাভার"
        ],
        "district": [
            "গাজীপুর",
            "ঢাকা",
            "টাঙ্গাইল",
            "নারায়ণগঞ্জ",
            "ময়মনসিংহ"
        ],
        "land_unit": [
            "শতাংশ",
            "অযুতাংশ",
            "কাঠা",
            "বিঘা",
            "একর",
            "ছটাক"
        ]
    }

    @classmethod
    def match_best(cls, raw_token, category):
        raw_clean = raw_token.strip()
        candidates = cls.CATALOG.get(category, [])
        if not candidates or not raw_clean:
            return {
                "raw_ocr_text": raw_token,
                "normalized_value": raw_clean,
                "weighted_distance": 0.0,
                "confidence": 0.50,
                "match_status": "UNMATCHED_CATEGORY"
            }

        best_cand = raw_clean
        best_dist = 999.0
        for cand in candidates:
            d = weighted_grapheme_distance(raw_clean, cand)
            if d < best_dist:
                best_dist = d
                best_cand = cand

        max_len = max(len(raw_clean), len(best_cand), 1)
        norm_score = max(0.0, 1.0 - (best_dist / max_len))
        confidence = round(min(0.99, 0.55 + 0.44 * norm_score), 2)

        status = "EXACT_LEXICON_MATCH" if best_dist == 0 else (
            "FUZZY_GRAPHEME_CORRECTED" if best_dist <= 2.2 else "LOW_CONFIDENCE_NEEDS_REVIEW"
        )
        return {
            "raw_ocr_text": raw_token,
            "normalized_value": best_cand if best_dist <= 2.5 else raw_clean,
            "weighted_distance": best_dist,
            "confidence": confidence,
            "match_status": status
        }

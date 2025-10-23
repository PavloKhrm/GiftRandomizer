def normalize_channel(s: str):
    s = str(s or "").strip()
    if s.startswith("@"):
        return s
    if s.startswith("-100"):
        return s
    return s

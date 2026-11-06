"""Signal-first reporting.

Default output is FINDINGS ONLY — the categories that actually matter, with the
evidence that justifies them. The full per-call log (every request, every tier)
is opt-in via --trace, because that log is mostly noise (protected endpoints).
"""

import csv

FINDINGS_FIELDS = [
    "category", "confidence", "level", "endpoint", "method",
    "params_values", "tiers", "similarity", "evidence",
]

TRACE_FIELDS = [
    "endpoint", "method", "tier", "params_values", "status",
    "body_len", "attempt", "error",
]

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    OPENPYXL = True
except ImportError:
    OPENPYXL = False


def counts(verdicts):
    """Return {category: n} and the count of signal findings."""
    by_cat = {}
    signal = 0
    for v in verdicts:
        by_cat[v.category] = by_cat.get(v.category, 0) + 1
        if v.signal:
            signal += 1
    return by_cat, signal


def console_summary(verdicts, http=None, findings_file=None):
    by_cat, signal = counts(verdicts)
    total = len(verdicts)
    noise = total - signal
    # Signal categories, most interesting first.
    order = ["AUTHZ-BYPASS", "BFLA-PRIVESC", "OPEN-2XX-SENSITIVE", "OPEN-2XX-REVIEW"]
    parts = [f"{by_cat[c]} {c}" for c in order if by_cat.get(c)]
    print("\n" + "=" * 60)
    if parts:
        print("SIGNAL:  " + "   ".join(parts))
    else:
        print("SIGNAL:  none (no unauthenticated/privileged exposure detected)")
    print(f"NOISE:   {noise} protected / non-signal (suppressed)")
    unverified = by_cat.get("UNVERIFIED-RATELIMITED", 0)
    if unverified:
        print(f"UNVERIFIED: {unverified} (rate-limited, retries exhausted)")
    if http is not None and getattr(http, "throttle_hits", 0):
        print(f"RATE-LIMITS: {http.throttle_hits} throttle hit(s), "
              f"{http.retries_done} re-run(s)")
    print(f"VERDICTS: {total} total")
    if findings_file:
        print(f"Findings -> {findings_file}")
    print("=" * 60)


def write_findings(path, verdicts):
    signals = [v for v in verdicts if v.signal]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FINDINGS_FIELDS)
        w.writeheader()
        for v in signals:
            w.writerow({
                "category": v.category,
                "confidence": v.confidence,
                "level": v.level,
                "endpoint": v.endpoint,
                "method": v.method,
                "params_values": v.params_values,
                "tiers": ",".join(f"{k}={val}" for k, val in v.tiers.items()),
                "similarity": (f"{v.similarity:.2f}" if v.similarity is not None else ""),
                "evidence": v.evidence,
            })
    return len(signals)


def write_trace(path, probes):
    """Write the full per-call log (every probe / tier) as CSV, plus .xlsx if openpyxl."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRACE_FIELDS)
        w.writeheader()
        for p in probes:
            w.writerow({
                "endpoint": p.endpoint,
                "method": p.method,
                "tier": p.tier,
                "params_values": p.params_values,
                "status": p.status,
                "body_len": p.body_len,
                "attempt": p.attempt,
                "error": p.error or "",
            })

    if OPENPYXL:
        try:
            _write_trace_xlsx(path, probes)
        except Exception:
            pass


def _write_trace_xlsx(path, probes):
    wb = Workbook()
    ws = wb.active
    ws.title = "trace"
    ws.append(TRACE_FIELDS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="366092")
    for p in probes:
        ws.append([p.endpoint, p.method, p.tier, p.params_values, p.status,
                   p.body_len, p.attempt, p.error or ""])
    wb.save(path.replace(".csv", ".xlsx"))

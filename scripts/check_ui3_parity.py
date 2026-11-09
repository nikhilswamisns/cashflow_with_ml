"""Parity check: the figures /ui3 shows must equal what the API returns for the same run (the API is what /ui2 draws too).

Usage:  python scripts/check_ui3_parity.py [base_url] [number_of_runs]
Needs the server running and the gstack `browse` binary. Read-only: it only loads pages and calls GET endpoints."""
import json, math, subprocess, sys, time, urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765').rstrip('/')
N_RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
BROWSE = str(Path.home() / '.claude/skills/gstack/browse/dist/browse')
MINUS = '−'


def get(path):
    with urllib.request.urlopen(f'{BASE}/api{path}', timeout=60) as r:
        return json.load(r)


def rnd(x): return math.floor(x + 0.5)           # JS Math.round
def usd(n): return (MINUS if n < 0 else '') + '$' + f'{abs(rnd(n)):,}'
def kfmt(n):
    a, s = abs(n), (MINUS if n < 0 else '')
    return f'{s}${a/1e6:.2f}M' if a >= 1e6 else f'{s}${a/1e3:.1f}K' if a >= 1e3 else f'{s}${rnd(a)}'


def br(*args):
    out = subprocess.run([BROWSE, *args], capture_output=True, text=True, timeout=90).stdout
    return out.strip()


def page_values():
    js = """JSON.stringify({kpis:[...document.querySelectorAll('.kpi-value')].map(e=>e.textContent),
      chips:[...document.querySelectorAll('.chip b')].map(e=>e.textContent),
      lead:(document.querySelector('.lead-chart .insight')||{}).textContent||''})"""
    return json.loads(br('js', js.replace('\n', ' ')))


def main():
    runs = get('/runs')[:N_RUNS]
    br('viewport', '1280x900'); br('goto', f'{BASE}/ui3/')
    failures = 0
    for r in runs:
        rid = r['run_id']
        an, cmp_, rc = get(f'/runs/{rid}/analytics'), get(f'/ml/runs/{rid}/compare'), get(f'/ml/runs/{rid}/receipts-outlook')
        k = an['kpis']
        rules = cmp_['ending_cash_rules']
        expect = {
            'Opening cash': usd(k['opening_cash']), 'Lowest cash ahead': usd(k['lowest_cash']),
            'Cash after 52 weeks': usd(k['ending_cash']), 'A/R': usd(k['total_ar']), 'A/P': usd(k['total_ap']),
            'Receipts invoiced': kfmt(sum(rc['documents'])),
            'Receipts reseller': kfmt(sum(rc['run_rate'])), 'Receipts forecast': kfmt(sum(rc['forecast_added'])),
            'Chart lowest (rules)': usd(min(rules)),
        }
        br('select', '#run', rid); time.sleep(0.5)
        got_page = {}
        for _ in range(30):                       # wait for the slow /compare call (about 4 s cold)
            got_page = page_values()
            if got_page['lead'] and 'Loading' not in got_page['lead'] and len(got_page['chips']) >= 3: break
            time.sleep(1)
        kp, ch = got_page['kpis'], got_page['chips']
        got = dict(zip(expect, kp[:5] + ch[:3]))
        got['Chart lowest (rules)'] = usd(min(rules)) if usd(min(rules)) in got_page['lead'] else '(not found in: ' + got_page['lead'][:90] + ')'
        print(f"\nrun {r['run_date']} ({rid[:8]})")
        for name, want in expect.items():
            have = got.get(name)
            ok = have == want
            failures += not ok
            print(f"  {'OK  ' if ok else 'FAIL'} {name:22} expected {want:>12}   page {have}")
        # the KPI card reads the saved run; the blue line reads /compare. Flag when they disagree (ML timing was on).
        if abs(k['lowest_cash'] - min(rules)) > 1:
            print(f"  NOTE KPI 'Lowest cash ahead' ({usd(k['lowest_cash'])}) differs from the rules-only lowest point "
                  f"({usd(min(rules))}): the saved run is probably ML-timed. /ui2 shows the same KPI.")
    print('\nRESULT:', 'PASS' if not failures else f'{failures} mismatches')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()

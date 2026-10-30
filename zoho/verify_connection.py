from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from zoho.client import ZohoClient
from zoho.auth import ZohoAuth, ZohoAuthError

def test_connection():
    try:
        auth = ZohoAuth()
        auth.validate_configuration(require_refresh_token=True)
    except ZohoAuthError as e:
        print(f"❌ Configuration Error: {e}")
        return False

    client = ZohoClient(auth=auth)
    
    print("1. Testing OAuth Token Refresh...")
    try:
        token = auth.get_access_token(force_refresh=True)
        print("   ✅ Access token generated successfully.")
    except Exception as e:
        print(f"   ❌ Failed to generate access token: {e}")
        return False

    print("\n2. Testing Real Data Endpoints (Read-Only):")
    endpoints = [
        ("invoices", "invoices"),
        ("bills", "bills"),
        ("salesorders", "salesorders"),
        ("purchaseorders", "purchaseorders"),
        ("bankaccounts", "bankaccounts"),
        ("contacts", "contacts"),
        ("expenses", "expenses"),
    ]

    success = True
    for ep, key in endpoints:
        try:
            res = client.get(ep, params={"per_page": 5})
            if res.get("code") == 0:
                records = res.get(key, [])
                page_ctx = res.get("page_context", {})
                has_more = page_ctx.get("has_more_page", False)
                print(f"   ✅ {ep:<18} Accessible | Sample: {len(records)} records | Has more: {has_more}")
            else:
                print(f"   ⚠️  {ep:<18} code={res.get('code')} msg={res.get('message')}")
                success = False
        except Exception as e:
            print(f"   ❌ {ep:<18} Error: {e}")
            success = False

    print("\n3. Testing Bank Account Live Balances:")
    try:
        res = client.get("bankaccounts")
        if res.get("code") == 0:
            for acc in res.get("bankaccounts", []):
                if acc.get("account_type") in ("bank", "credit_card"):
                    print(f"   🏦 {acc.get('account_name'):<35} [{acc.get('account_type')}]: ${acc.get('bcy_balance', 0):,.2f}")
    except Exception as e:
        print(f"   ⚠️  Bank accounts error: {e}")

    print("\n4. Testing the forecast snapshot pull (read-only, same calls as 'Sync Live from Zoho'):")
    try:
        import json
        from datetime import date
        from zoho.snapshot import pull_snapshot
        from app.transforms.date_bucketing import prev_friday
        snap = pull_snapshot(client, prev_friday(date.today()))
        for k, v in snap.items():
            if isinstance(v, list):
                print(f"   ✅ {k:<18} {len(v)} records")
        if not snap["card_transactions"]:
            print("   ⚠️  card_transactions returned 0 rows - card itemization will fall back to the last known cycle.")
        missing_terms = [p["number"] for p in snap["purchase_orders"] if p.get("payment_terms_days") is None]
        if missing_terms:
            print(f"   ⚠️  POs without Zoho payment terms (default +30 used): {', '.join(missing_terms)}")
        out = Path(__file__).parent.parent / "data" / "last_snapshot.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(snap, indent=1, default=str), encoding="utf-8")
        print(f"   💾 Snapshot saved to {out} (send this file for review if numbers look wrong)")
    except Exception as e:
        print(f"   ❌ Snapshot pull failed: {e}")
        success = False

    return success

if __name__ == "__main__":
    ok = test_connection()
    sys.exit(0 if ok else 1)

"""
utils/admin.py
Operator commands (run on the server with the production env vars loaded):

    python -m utils.admin list
    python -m utils.admin grant someone@company.co.uk pro --months 12
    python -m utils.admin grant someone@company.co.uk trial      # revoke a manual plan
    python -m utils.admin sync someone@company.co.uk             # re-check Stripe now
"""

import argparse

from dotenv import load_dotenv

load_dotenv()

from utils.account_tracker import grant_plan, list_accounts, refresh_entitlements  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m utils.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("grant")
    g.add_argument("email")
    g.add_argument("tier", choices=["trial", "pro", "agency"])
    g.add_argument("--months", type=int, default=1)
    s = sub.add_parser("sync")
    s.add_argument("email")
    args = p.parse_args()

    if args.cmd == "list":
        for a in list_accounts():
            print(f"{a['email']:<40} {a['tier']:<7} {a['plan_source']:<7} "
                  f"{a['resumes_used']:>5}/{a['max_resumes']:<5} {a.get('company') or ''}")
    elif args.cmd == "grant":
        a = grant_plan(args.email, args.tier, months=args.months)
        print(f"{a['email']}: {a['tier']} ({a['remaining']}/{a['max_resumes']} CVs), "
              f"expires {a.get('plan_expires_at')}")
    elif args.cmd == "sync":
        a, warn = refresh_entitlements(args.email, force=True, report=True)
        print(a or "No such account", warn)


if __name__ == "__main__":
    main()

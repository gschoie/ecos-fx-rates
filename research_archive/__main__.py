# -*- coding: utf-8 -*-
"""CLI 진입점.

사용법:
  python -m research_archive test  --limit 15 [--local]   # 최근 보고서 N건 테스트
  python -m research_archive backfill [--limit 100] [--local]  # 과거 전체(재개 가능)
  python -m research_archive daily [--local]              # 새 게시물만 (매일 9시 cron)

--local : Google Drive 대신 ./archive_out/ 에 저장 (검증용)
"""
from __future__ import annotations

import argparse
import sys

from . import telegram
from .pipeline import LocalStore, Pipeline


def make_store(local: bool):
    if local:
        return LocalStore()
    from .gdrive import DriveStore
    return DriveStore()


def cmd_test(args):
    """최근 게시물부터 과거로 훑어 보고서 limit건만 처리."""
    pipe = Pipeline(make_store(args.local))
    done = 0
    try:
        for page in telegram.iter_history():
            for post in reversed(page):          # 최신부터
                if not post.is_report or pipe.seen(post):
                    continue
                if pipe.process_post(post):
                    done += 1
                if done >= args.limit:
                    raise StopIteration
    except StopIteration:
        pass
    finally:
        pipe.save()
    print(f"\n테스트 완료: 보고서 {done}건 처리")


def cmd_backfill(args):
    """과거 방향 전체 순회. state의 backfill_before 커서로 중단 후 재개 가능."""
    pipe = Pipeline(make_store(args.local))
    cursor = pipe.state.get("backfill_before")  # None이면 최신부터
    done = pages = 0
    try:
        for page in telegram.iter_history(start_before=cursor):
            pages += 1
            for post in reversed(page):
                if pipe.process_post(post):
                    done += 1
                if args.limit and done >= args.limit:
                    raise StopIteration
            # 이 페이지까지 완료 → 커서 전진(과거 방향)
            pipe.state["backfill_before"] = page[0].msg_id
            if pages % 5 == 0:
                pipe.save()
        pipe.state["backfill_done"] = True
        print("\nBackfill 완료: 채널 처음까지 도달")
    except StopIteration:
        print(f"\nBackfill 일시 중단 (limit {args.limit} 도달). "
              "재실행하면 이어서 처리됩니다.")
    finally:
        pipe.save()
    print(f"이번 실행 처리: 보고서 {done}건")


def cmd_daily(args):
    """마지막으로 본 message id 이후의 새 게시물 처리."""
    pipe = Pipeline(make_store(args.local))
    since = pipe.state.get("last_seen_id", 0)
    posts = telegram.fetch_new(since_id=since) if since else []
    if not since:
        # 최초 실행: 최신 1페이지만 기준점으로 삼음
        page = telegram.fetch_page()
        posts = page
    done = 0
    for post in posts:
        if pipe.process_post(post):
            done += 1
        pipe.state["last_seen_id"] = max(pipe.state.get("last_seen_id", 0),
                                         post.msg_id)
    pipe.save()
    print(f"\nDaily 실행 완료: 새 게시물 {len(posts)}건 중 보고서 {done}건 처리")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="research_archive")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("test", help="최근 보고서 N건 테스트 처리")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--local", action="store_true")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("backfill", help="과거 게시물 전체 처리(재개 가능)")
    p.add_argument("--limit", type=int, default=0, help="0=무제한")
    p.add_argument("--local", action="store_true")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("daily", help="새 게시물만 처리")
    p.add_argument("--local", action="store_true")
    p.set_defaults(func=cmd_daily)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""Generate AI replies ahead of time, for a demo that cannot be broken by the LLM.

Picks the most urgent open complaints that have no AI reply yet (or only the
template fallback) and generates one for each, one at a time, paced to stay
inside free-tier rate limits. Once generated, content is stored: showing it
later needs no LLM call, so a provider outage or used-up quota on demo day
changes nothing.

    make pregenerate                  # the 10 most urgent
    make pregenerate n=25             # more
    docker compose run --rm api python -m app.pregenerate --include-demo
"""

import argparse
import sys
import time

from app.core.database import get_session_factory
from app.core.exceptions import LLMRateLimitedError, LLMUnavailableError
from app.repositories.generated_content_repo import GeneratedContentRepository
from app.services.generated_content_service import GeneratedContentService

PAUSE_SECONDS = 13  # ~4.5 complaints a minute, 2 requests each


def run(limit: int, include_demo: bool, pause: float = PAUSE_SECONDS) -> tuple[int, int]:
    """Returns (generated, failed)."""
    db = get_session_factory()()
    try:
        service = GeneratedContentService(db)
        if not service.llm_available:
            print("No LLM is configured (LLM_PROVIDER in .env). Nothing to do.")
            return 0, 0
        ids = GeneratedContentRepository(db).complaints_needing_content(limit, include_demo)
        if not ids:
            print("Every open complaint already has an AI reply.")
            return 0, 0
        print(f"Generating AI replies for {len(ids)} complaints, about {pause:.0f}s apart.")
        done = failed = 0
        for i, cid in enumerate(ids, start=1):
            for attempt in (1, 2):
                try:
                    content = service.generate(cid, allow_fallback=False)
                except LLMRateLimitedError as exc:
                    db.rollback()
                    if exc.daily or attempt == 2:
                        print(f"  stopped: {exc.message}. Try again later or switch LLM_MODEL.")
                        return done, failed + 1
                    print(f"  rate limited, waiting {exc.retry_after}s")
                    time.sleep(exc.retry_after)
                    continue
                except LLMUnavailableError as exc:
                    db.rollback()
                    failed += 1
                    print(f"  [{i}/{len(ids)}] {cid}: failed ({exc.message})")
                    break
                done += 1
                print(f"  [{i}/{len(ids)}] {cid}: {content.tone} reply, "
                      f"{len(content.cited_article_ids or [])} article(s) cited")
                break
            if i < len(ids):
                time.sleep(pause)
        print(f"Done: {done} generated, {failed} failed.")
        return done, failed
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI replies ahead of a demo.")
    parser.add_argument("-n", "--limit", type=int, default=10)
    parser.add_argument("--include-demo", action="store_true",
                        help="also the synthetic complaints from make seed-history")
    args = parser.parse_args()
    _, failures = run(args.limit, args.include_demo)
    sys.exit(1 if failures else 0)

"""Prompt registry reads (A26, kit form).

A slug resolves to its single active revision: model id, system text, and an
optional user template. Reads are cached in-process for a short TTL and the
last good value is kept as a fallback, so a transient database error does not
take down every node that needs a prompt. Editing a prompt is an INSERT plus
flipping is_active; the next cache miss picks it up. No redeploy, no proxy.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from agent import settings
from agent.db import platform_txn

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptRevision:
    slug: str
    revision: int
    model_id: str | None   # resolved Bedrock id, or None = defer to the agent row's model_size
    system_text: str
    user_template: str | None

    def render_user(self, **values: str) -> str | None:
        if self.user_template is None:
            return None
        text = self.user_template
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        return text


_cache: dict[str, tuple[float, PromptRevision]] = {}
_last_good: dict[str, PromptRevision] = {}


def _resolve_model(model_id: str | None) -> str | None:
    """A revision may name a size alias (MODEL_SMALL/MODEL_MEDIUM), a real id, or nothing."""
    if model_id is None:
        return None
    return {"MODEL_SMALL": settings.MODEL_SMALL, "MODEL_MEDIUM": settings.MODEL_MEDIUM}.get(model_id, model_id)


def get_prompt(slug: str) -> PromptRevision:
    now = time.monotonic()
    hit = _cache.get(slug)
    if hit and hit[0] > now:
        return hit[1]
    try:
        with platform_txn() as cur:
            cur.execute(
                """select slug, revision, model_id, system_text, user_template
                   from prompt_revisions where slug = %s and is_active""",
                (slug,),
            )
            row = cur.fetchone()
    except Exception as e:  # noqa: BLE001 - any DB failure falls back to last-known-good
        if slug in _last_good:
            logger.warning("prompt %s: DB read failed (%s); serving last-known-good", slug, e)
            return _last_good[slug]
        raise
    if row is None:
        raise LookupError(f"no active revision for prompt slug {slug!r}")
    rev = PromptRevision(
        slug=row["slug"],
        revision=row["revision"],
        model_id=_resolve_model(row["model_id"]),
        system_text=row["system_text"],
        user_template=row["user_template"],
    )
    _cache[slug] = (now + settings.PROMPT_CACHE_TTL_SECONDS, rev)
    _last_good[slug] = rev
    return rev


def invalidate(slug: str | None = None) -> None:
    if slug is None:
        _cache.clear()
    else:
        _cache.pop(slug, None)

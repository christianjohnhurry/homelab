"""Branch names for tickets: hml-42-add-login-flow."""

import re

SLUG_MAX = 40


def slugify(text: str, max_length: int = SLUG_MAX) -> str:
    """Lowercase, non-alphanumerics to single dashes, cut at a dash to max_length."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) <= max_length:
        return slug
    cut = slug[:max_length]
    # Prefer ending on a whole word; fall back to a hard cut for one long word
    if "-" in cut and slug[max_length] != "-":
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def branch_name(ticket_key: str, ticket_name: str) -> str:
    """`HML-42` + `Add login flow!` -> `hml-42-add-login-flow`. No type prefix."""
    slug = slugify(ticket_name)
    prefix = ticket_key.lower()
    return f"{prefix}-{slug}" if slug else prefix

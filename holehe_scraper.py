import asyncio

import httpx
from holehe.core import import_submodules, get_functions, launch_module

from nodes import OnlineAccount


async def _check_email(email: str) -> list[dict]:
    out: list[dict] = []
    modules = import_submodules("holehe.modules")
    websites = get_functions(modules)
    async with httpx.AsyncClient() as client:
        # launch_module catches per-module exceptions (a module raising shouldn't
        # abort every other module's in-flight check via asyncio.gather).
        await asyncio.gather(*(launch_module(module, email, client, out) for module in websites))
    return out


def lookup(email: str) -> list[OnlineAccount]:
    """
    Runs every holehe checker module against `email` and returns one OnlineAccount
    per module that reported the email exists on that site. Modules that errored or
    hit a rate limit are silently dropped — per-module failure is normal for holehe,
    unlike Recherche d'entreprises where a single HTTP error blocks the whole search.
    """
    raw_results = asyncio.run(_check_email(email))
    return [
        OnlineAccount(site=r.get("name"), domain=r.get("domain"), method=r.get("method"), source="holehe")
        for r in raw_results
        if r.get("exists") is True
    ]

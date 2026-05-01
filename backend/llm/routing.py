"""Provider load balancing: weighted random and round-robin selection."""
import asyncio
import random
import threading
from collections import defaultdict
from backend.llm.base import LLMProvider
from backend.llm.registry import get_provider

# Per-job-type state: round-robin pointer + lock
_rr_lock = threading.Lock()
_rr_pointers: dict[str, int] = defaultdict(int)  # job_type -> index into enabled list
_rr_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def select_provider(job_type: str, enabled_providers: list[tuple[str, float]]) -> str:
    """
    Select a provider for the given job_type using the configured strategy.

    Strategy is determined by whether weights are uniform (round-robin) or
    varied (weighted random).

    Args:
        job_type: currently always "ocr"
        enabled_providers: list of (provider_name, weight) tuples, sorted by name

    Returns:
        provider name string
    """
    if not enabled_providers:
        return "fastflowlm"

    names = [p[0] for p in enabled_providers]
    weights = [p[1] for p in enabled_providers]

    # Detect strategy: if all weights are equal, use round-robin; else weighted random
    if len(set(weights)) == 1:
        # Round-robin
        ptr_key = job_type
        lock = _rr_locks[ptr_key]
        with lock:
            idx = _rr_pointers[ptr_key] % len(names)
            _rr_pointers[ptr_key] = idx + 1
        return names[idx]
    else:
        # Weighted random (weights are relative — normalize internally)
        total = sum(weights)
        r = random.random() * total
        cumulative = 0.0
        for name, weight in enabled_providers:
            cumulative += weight
            if r <= cumulative:
                return name
        return names[-1]  # fallback

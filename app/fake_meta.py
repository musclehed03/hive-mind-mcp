"""FAKE Meta client (Blocks 3-4). No network, no credentials, no model.

This is the ONLY client the build and tests ever use. It returns
canned, deterministic responses and records every call so tests can
assert exactly how many (zero-network) calls were made. It reads no
environment variables and contains no API key names or values.

The LIVE Meta Model API gate is deliberately NOT implemented here:
it lives only as documented Sonja-side commands in the README
(Block 4, UNVERIFIED). Any real client must be added on Sonja's
machine, after the $150 free-credit / $100 spend-warning guard, and
must never be committed with a key in it.
"""

FAKE_MODEL = "muse-spark-1.3-fake"


class FakeMetaClient:
    """Canned Meta client. call_count is the audit trail."""

    def __init__(self):
        self.call_count = 0
        self.calls = []

    def verify(self, candidate_fact, domain_repo):
        """Canned pillar check: deterministic, content-keyed, no LLM.

        A candidate containing the word 'unsafe' fails the security
        pillar; one containing 'contradiction' is flagged conflicting;
        everything else passes all six pillars. These markers exist
        only so the cross-hatch logic can be tested end to end without
        a live model — the fake never claims a real verification.
        """
        self.call_count += 1
        self.calls.append({
            "method": "verify",
            "candidate_fact": candidate_fact,
            "domain_repo": domain_repo,
            "model": FAKE_MODEL,
            "live": False,
        })
        lowered = candidate_fact.lower()
        if "unsafe" in lowered:
            verdict = "rejected"
            pillar_failures = ["security"]
        elif "contradiction" in lowered:
            verdict = "conflicting"
            pillar_failures = []
        else:
            verdict = "consistent"
            pillar_failures = []
        return {
            "model": FAKE_MODEL,
            "live": False,
            "verdict": verdict,
            "pillar_failures": pillar_failures,
            "pillars_checked": [
                "computing-in-memory", "event-driven spiking",
                "extreme sparsity / dynamic routing",
                "continuous local learning", "accessibility", "security",
            ],
        }

    def compress(self, text):
        """Canned compression call, recorded for the zero-network audit."""
        self.call_count += 1
        self.calls.append({"method": "compress", "model": FAKE_MODEL, "live": False})
        return {"model": FAKE_MODEL, "live": False, "compressed": text}

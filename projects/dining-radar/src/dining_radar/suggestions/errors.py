"""Errors owned by ``suggestions``, independent of any concrete provider.

``web`` must not import ``dining_radar.integrations`` directly (see
``tests/test_structure.py``), so any adapter failure crossing into ``web`` is
translated into one of these types first.
"""


class CandidateSourceUnavailableError(RuntimeError):
    """A candidate source (for example, the Hot Pepper adapter) failed."""

"""Peers quarterly appendix pipeline.

The public surface is registered by :mod:`modules.peers_appendix.cli` as
``ir peers ...``.  Implementation modules deliberately have no standalone
``argparse`` entrypoints.
"""

from .steps import DOMAIN

__all__ = ["DOMAIN"]

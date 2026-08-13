"""Errori del Tool Server.

Ogni errore è **pulito e tipizzato**: una richiesta fuori dallo snapshot
congelato deve fallire in modo visibile, mai degradare silenziosamente su dati
live o su un default plausibile (CLAUDE.md §7).
"""

from __future__ import annotations


class ToolServerError(Exception):
    """Base di tutti gli errori del Tool Server."""

    code = "tool_server_error"


class SnapshotNotFound(ToolServerError):
    code = "snapshot_not_found"


class SnapshotCorrupted(ToolServerError):
    code = "snapshot_corrupted"


class UnknownTool(ToolServerError):
    code = "unknown_tool"


class UnknownAsset(ToolServerError):
    code = "unknown_asset"


class InvalidToolArguments(ToolServerError):
    code = "invalid_tool_arguments"


class OutOfSnapshotRequest(ToolServerError):
    """Richiesta che uscirebbe dai confini dello snapshot congelato."""

    code = "out_of_snapshot"


class FirewallViolation(ToolServerError):
    """Configurazione che romperebbe l'isolamento del Tool Server."""

    code = "firewall_violation"

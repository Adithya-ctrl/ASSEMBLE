"""Dependency-neutral domain errors shared across ASSEMBLE layers."""


class AnalyserContractError(RuntimeError):
    """Raised when a solver-backed analyser emits a malformed result."""

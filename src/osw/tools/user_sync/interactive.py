"""Interactive preview and conflict resolution for the sync.

Rendering is pure (returns strings). All terminal IO goes through ``Prompter``,
which wraps ``input`` / ``print`` so tests can script answers and capture output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Set

from .mapping import ProposedUser
from .reconcile import (
    CONFLICT,
    GAP_FILL,
    NEW,
    RECONCILED_FIELDS,
    UNCHANGED,
    ReconcilePlan,
    UserChange,
    proposed_fields,
)

_MARKERS = {NEW: "+", GAP_FILL: "~", CONFLICT: "!", UNCHANGED: "="}


def _is_empty(value: Any) -> bool:
    if value is None or value == "":
        return True
    return isinstance(value, (list, set, tuple)) and len(value) == 0


def nonempty_fields(proposed: ProposedUser) -> Set[str]:
    """Reconciled field names that carry a value on the proposed user."""
    pf = proposed_fields(proposed)
    return {name for name in RECONCILED_FIELDS if not _is_empty(pf[name])}


def render_preview(plan: ReconcilePlan) -> List[str]:
    """Human-readable preview: a header line plus one row per user."""
    counts = plan.counts()
    lines = [
        f"Users: {len(plan.changes)} | "
        f"new={counts[NEW]} gap_fill={counts[GAP_FILL]} "
        f"conflict={counts[CONFLICT]} unchanged={counts[UNCHANGED]}"
    ]
    for change in plan.changes:
        marker = _MARKERS[change.category]
        detail = ""
        if change.diffs:
            detail = " (" + ", ".join(d.name for d in change.diffs) + ")"
        placeholder = " [placeholder name]" if change.proposed.placeholder_name else ""
        lines.append(
            f"  {marker} {change.proposed.username} {change.category}{detail}{placeholder}"
        )
    return lines


def render_conflict(change: UserChange) -> List[str]:
    """Field-by-field display of one user's differences."""
    lines = [f"User {change.proposed.username}:"]
    for diff in change.diffs:
        lines.append(
            f"  {diff.name} [{diff.status}]: "
            f"existing={diff.existing!r} -> proposed={diff.proposed!r}"
        )
    return lines


class Prompter:
    """Thin IO seam over input/print for testable prompting."""

    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self._input = input_fn
        self._output = output_fn

    def write(self, text: str = "") -> None:
        self._output(text)

    def ask(self, prompt: str, choices: Sequence[str]) -> str:
        keys = "/".join(choices)
        while True:
            answer = self._input(f"{prompt} [{keys}]: ").strip().lower()
            if answer in choices:
                return answer
            self.write(f"Please choose one of: {keys}")

    def confirm(self, prompt: str, default: bool = False) -> bool:
        suffix = "[Y/n]" if default else "[y/N]"
        answer = self._input(f"{prompt} {suffix}: ").strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes")


@dataclass
class ResolvedChange:
    """A user change with the decided action and fields to write."""

    change: UserChange
    action: str  # "create" | "update" | "skip"
    apply_fields: Set[str] = field(default_factory=set)


@dataclass
class Resolution:
    """The outcome of resolving a plan: what to write and whether to proceed."""

    resolved: List[ResolvedChange] = field(default_factory=list)
    accepted: bool = False

    def creates(self) -> List[ResolvedChange]:
        return [r for r in self.resolved if r.action == "create"]

    def updates(self) -> List[ResolvedChange]:
        return [r for r in self.resolved if r.action == "update"]


def _review_user(change: UserChange, prompter: Prompter) -> Set[str]:
    """Resolve one conflicting user's fields, returning accepted conflict fields."""
    for line in render_conflict(change):
        prompter.write(line)
    conflict_diffs = [d for d in change.diffs if d.status == CONFLICT]
    choice = prompter.ask(
        "Take all new / Keep all existing / Field-by-field?", ("a", "k", "f")
    )
    if choice == "a":
        return {d.name for d in conflict_diffs}
    if choice == "k":
        return set()
    accepted: Set[str] = set()
    for diff in conflict_diffs:
        if prompter.ask(f"{diff.name}: keep or take new?", ("k", "n")) == "n":
            accepted.add(diff.name)
    return accepted


def resolve_plan(
    plan: ReconcilePlan,
    prompter: Prompter,
    dry_run: bool = False,
    assume_yes: bool = False,
    summary_lines: Optional[Sequence[str]] = None,
) -> Resolution:
    """Preview the plan and resolve conflicts into a write decision."""
    for line in render_preview(plan):
        prompter.write(line)
    for line in summary_lines or []:
        prompter.write(line)

    conflict_mode: Optional[str] = None
    if plan.conflicts and not dry_run:
        if assume_yes:
            conflict_mode = "keep"
        else:
            choice = prompter.ask(
                "Conflicts found: Apply all / Keep existing / Review each / Abort?",
                ("a", "k", "r", "x"),
            )
            if choice == "x":
                return Resolution(resolved=[], accepted=False)
            conflict_mode = {"a": "all", "k": "keep", "r": "review"}[choice]

    resolved: List[ResolvedChange] = []
    for change in plan.changes:
        if change.category == NEW:
            resolved.append(
                ResolvedChange(change, "create", nonempty_fields(change.proposed))
            )
        elif change.category == UNCHANGED:
            resolved.append(ResolvedChange(change, "skip"))
        elif change.category == GAP_FILL:
            resolved.append(
                ResolvedChange(change, "update", {d.name for d in change.diffs})
            )
        else:  # CONFLICT
            accepted = {d.name for d in change.diffs if d.status == GAP_FILL}
            if conflict_mode == "all":
                accepted |= {d.name for d in change.diffs if d.status == CONFLICT}
            elif conflict_mode == "review":
                accepted |= _review_user(change, prompter)
            action = "update" if accepted else "skip"
            resolved.append(ResolvedChange(change, action, accepted))

    if dry_run:
        accepted_run = False
    elif assume_yes:
        accepted_run = True
    else:
        n_create = sum(1 for r in resolved if r.action == "create")
        n_update = sum(1 for r in resolved if r.action == "update")
        accepted_run = prompter.confirm(
            f"Proceed to create {n_create} and update {n_update} user items?"
        )
    return Resolution(resolved=resolved, accepted=accepted_run)

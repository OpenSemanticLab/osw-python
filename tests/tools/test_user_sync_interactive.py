"""Unit tests for the interactive preview and conflict resolution."""

import uuid

from osw.tools.user_sync.interactive import (
    Prompter,
    nonempty_fields,
    render_preview,
    resolve_plan,
)
from osw.tools.user_sync.mapping import ProposedUser
from osw.tools.user_sync.reconcile import (
    CONFLICT,
    GAP_FILL,
    NEW,
    UNCHANGED,
    FieldDiff,
    ReconcilePlan,
    UserChange,
)


class FakeIO:
    def __init__(self, answers):
        self.answers = list(answers)
        self.outputs = []

    def input(self, prompt=""):
        return self.answers.pop(0)

    def output(self, text=""):
        self.outputs.append(text)


def _proposed(username="u", **kw):
    base = dict(
        uuid=uuid.uuid4(),
        username=username,
        first_name="F",
        surname="S",
        label="F S",
        orcid=None,
        emails=[],
        websites=[],
        organizations=[],
    )
    base.update(kw)
    return ProposedUser(**base)


def _change(category, username="u", diffs=None, placeholder=False):
    proposed = _proposed(username=username)
    proposed.placeholder_name = placeholder
    return UserChange(
        proposed=proposed,
        existing=None if category == NEW else object(),
        category=category,
        diffs=diffs or [],
    )


def _prompter(answers):
    io = FakeIO(answers)
    return Prompter(io.input, io.output), io


def test_render_preview():
    plan = ReconcilePlan(changes=[_change(NEW, "alice", placeholder=True)])
    lines = render_preview(plan)
    assert lines[0].startswith("Users: 1")
    assert "new=1" in lines[0]
    assert "+ alice new" in lines[1]
    assert "[placeholder name]" in lines[1]


def test_nonempty_fields():
    proposed = _proposed(orcid="https://orcid.org/x", emails=["e@x.org"])
    assert nonempty_fields(proposed) == {
        "label",
        "first_name",
        "surname",
        "orcid",
        "emails",
    }


def _mixed_plan():
    return ReconcilePlan(
        changes=[
            _change(NEW, "new1"),
            _change(GAP_FILL, "gap1", [FieldDiff("emails", set(), {"e"}, GAP_FILL)]),
            _change(CONFLICT, "con1", [FieldDiff("surname", "Old", "New", CONFLICT)]),
            _change(
                CONFLICT,
                "mix1",
                [
                    FieldDiff("emails", set(), {"e"}, GAP_FILL),
                    FieldDiff("surname", "Old", "New", CONFLICT),
                ],
            ),
            _change(UNCHANGED, "same1"),
        ]
    )


def test_resolve_keep_existing():
    prompter, _ = _prompter(["k", "y"])
    res = resolve_plan(_mixed_plan(), prompter)
    assert [r.change.proposed.username for r in res.creates()] == ["new1"]
    updates = {r.change.proposed.username: r.apply_fields for r in res.updates()}
    assert updates == {"gap1": {"emails"}, "mix1": {"emails"}}
    skipped = {r.change.proposed.username for r in res.resolved if r.action == "skip"}
    assert skipped == {"con1", "same1"}
    assert res.accepted is True


def test_resolve_apply_all():
    prompter, _ = _prompter(["a", "y"])
    res = resolve_plan(_mixed_plan(), prompter)
    updates = {r.change.proposed.username: r.apply_fields for r in res.updates()}
    assert updates["con1"] == {"surname"}
    assert updates["mix1"] == {"emails", "surname"}


def test_resolve_abort():
    prompter, _ = _prompter(["x"])
    res = resolve_plan(_mixed_plan(), prompter)
    assert res.resolved == []
    assert res.accepted is False


def test_resolve_dry_run_makes_no_writes_and_no_prompts():
    prompter, io = _prompter([])  # no answers available
    res = resolve_plan(_mixed_plan(), prompter, dry_run=True)
    assert res.accepted is False
    assert io.answers == []  # nothing was asked


def test_resolve_auto_apply_keeps_conflicts():
    prompter, io = _prompter([])
    res = resolve_plan(_mixed_plan(), prompter, auto_apply=True)
    assert res.accepted is True
    updates = {r.change.proposed.username: r.apply_fields for r in res.updates()}
    assert updates == {"gap1": {"emails"}, "mix1": {"emails"}}
    assert io.answers == []


def test_resolve_review_field_by_field():
    plan = ReconcilePlan(
        changes=[
            _change(
                CONFLICT,
                "con1",
                [
                    FieldDiff("surname", "Old", "New", CONFLICT),
                    FieldDiff("label", "L1", "L2", CONFLICT),
                ],
            )
        ]
    )
    prompter, _ = _prompter(["r", "f", "n", "k", "y"])
    res = resolve_plan(plan, prompter)
    assert res.updates()[0].apply_fields == {"surname"}
    assert res.accepted is True


def test_resolve_review_take_all_for_user():
    plan = ReconcilePlan(
        changes=[
            _change(
                CONFLICT,
                "con1",
                [
                    FieldDiff("surname", "Old", "New", CONFLICT),
                    FieldDiff("label", "L1", "L2", CONFLICT),
                ],
            )
        ]
    )
    prompter, _ = _prompter(["r", "a", "y"])
    res = resolve_plan(plan, prompter)
    assert res.updates()[0].apply_fields == {"surname", "label"}


def test_final_confirm_no():
    plan = ReconcilePlan(changes=[_change(NEW, "new1")])
    prompter, _ = _prompter(["n"])
    res = resolve_plan(plan, prompter)
    assert res.accepted is False
    assert res.creates()[0].change.proposed.username == "new1"


def test_prompter_reprompts_on_invalid():
    prompter, io = _prompter(["z", "k"])
    assert prompter.ask("q", ("k", "n")) == "k"
    assert any("Please choose one of" in o for o in io.outputs)

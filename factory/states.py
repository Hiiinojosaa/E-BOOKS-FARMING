"""Book state machine and pipeline steps (single source of truth).

A *step* is a unit of work done by one specialist. Each step moves a book
   from_state  --claim-->  working_state  --complete-->  done_state
and on failure/release returns the book to the from_state it was claimed in.
"""

STATES = [
    "IDEA",
    "RESEARCH_PENDING", "RESEARCHING", "RESEARCH_COMPLETE",
    "BRIEFING", "BRIEF_READY",
    "WRITING_PENDING", "WRITING", "DRAFT_COMPLETE",
    "TRANSLATION_PENDING", "TRANSLATING", "TRANSLATED",
    "EDITING", "EDITED",
    "FACT_CHECKING", "FACT_CHECKED",
    "METADATA_IN_PROGRESS",
    "DESIGN_PENDING", "DESIGNING", "DESIGN_COMPLETE",
    "FORMATTING",
    "QC_PENDING", "QC", "QC_FAILED", "QC_PASSED", "FIXING",
    "HUMAN_REVIEW", "CHANGES_REQUIRED", "APPROVED", "REJECTED",
    "READY_FOR_PUBLISHING", "PUBLISHED",
    "BLOCKED",
]

TERMINAL = {"REJECTED", "PUBLISHED"}

# step -> definition. role = specialist agent that does it. auto = run by script.
STEPS = {
    "RESEARCH":   {"from": ["RESEARCH_PENDING"], "working": "RESEARCHING", "done": "RESEARCH_COMPLETE", "role": "RESEARCH_AGENT", "auto": False},
    "BRIEF":      {"from": ["RESEARCH_COMPLETE"], "working": "BRIEFING", "done": "BRIEF_READY", "role": "RESEARCH_AGENT", "auto": False},
    "WRITE":      {"from": ["WRITING_PENDING"], "working": "WRITING", "done": "DRAFT_COMPLETE", "role": "WRITER_AGENT", "auto": False},
    "TRANSLATE":  {"from": ["TRANSLATION_PENDING"], "working": "TRANSLATING", "done": "TRANSLATED", "role": "TRANSLATOR_AGENT", "auto": False},
    "EDIT":       {"from": ["DRAFT_COMPLETE", "TRANSLATED"], "working": "EDITING", "done": "EDITED", "role": "EDITOR_AGENT", "auto": False},
    "FACT_CHECK": {"from": ["EDITED"], "working": "FACT_CHECKING", "done": "FACT_CHECKED", "role": "FACT_CHECK_AGENT", "auto": False},
    "METADATA":   {"from": ["FACT_CHECKED"], "working": "METADATA_IN_PROGRESS", "done": "DESIGN_PENDING", "role": "MARKET_AGENT", "auto": False},
    "DESIGN":     {"from": ["DESIGN_PENDING"], "working": "DESIGNING", "done": "DESIGN_COMPLETE", "role": "DESIGN_AGENT", "auto": False},
    "FORMAT":     {"from": ["DESIGN_COMPLETE"], "working": "FORMATTING", "done": "QC_PENDING", "role": "FORMAT_AGENT", "auto": True},
    "QC":         {"from": ["QC_PENDING"], "working": "QC", "done": "QC_PASSED", "fail_done": "QC_FAILED", "role": "QC_AGENT", "auto": False},
    "FIX":        {"from": ["QC_FAILED"], "working": "FIXING", "done": "DESIGN_COMPLETE", "role": "EDITOR_AGENT", "auto": False},
}

PRIORITIES = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}

# Transitions done by the orchestrator or by humans (not by step claims).
EXTRA_TRANSITIONS = {
    ("IDEA", "RESEARCH_PENDING"),
    ("BRIEF_READY", "WRITING_PENDING"),
    ("QC_PASSED", "HUMAN_REVIEW"),
    ("HUMAN_REVIEW", "APPROVED"),
    ("HUMAN_REVIEW", "CHANGES_REQUIRED"),
    ("HUMAN_REVIEW", "REJECTED"),
    ("APPROVED", "READY_FOR_PUBLISHING"),
    ("READY_FOR_PUBLISHING", "PUBLISHED"),
    ("IDEA", "REJECTED"),
    ("BRIEF_READY", "REJECTED"),
    ("BRIEF_READY", "CHANGES_REQUIRED"),
}
# CHANGES_REQUIRED may restart at the from-state of any step.
RESTART_STATES = {s["from"][0] for s in STEPS.values()}


def allowed_transitions():
    allowed = set(EXTRA_TRANSITIONS)
    for st in STEPS.values():
        for f in st["from"]:
            allowed.add((f, st["working"]))
            allowed.add((st["working"], f))  # release / retry
        allowed.add((st["working"], st["done"]))
        if "fail_done" in st:
            allowed.add((st["working"], st["fail_done"]))
    for s in RESTART_STATES:
        allowed.add(("CHANGES_REQUIRED", s))
    for s in STATES:
        if s not in TERMINAL and s != "BLOCKED":
            allowed.add((s, "BLOCKED"))
    return allowed


ALLOWED = allowed_transitions()


def can_transition(frm, to):
    if frm == "BLOCKED":
        return to != "BLOCKED"  # unblocking is a human/explicit action
    return (frm, to) in ALLOWED


def step_for_state(state):
    """Which step should be queued for a book sitting in `state` (or None)."""
    for name, st in STEPS.items():
        if state in st["from"]:
            return name
    return None


def working_states():
    return {st["working"]: name for name, st in STEPS.items()}


# Grouping used by the dashboard.
DASHBOARD_GROUPS = {
    "IDEAS": ["IDEA"],
    "RESEARCH": ["RESEARCH_PENDING", "RESEARCHING", "RESEARCH_COMPLETE", "BRIEFING", "BRIEF_READY"],
    "WRITING": ["WRITING_PENDING", "WRITING", "DRAFT_COMPLETE"],
    "EDITING": ["EDITING", "EDITED", "FACT_CHECKING", "FACT_CHECKED", "FIXING"],
    "TRANSLATION": ["TRANSLATION_PENDING", "TRANSLATING", "TRANSLATED"],
    "DESIGN": ["METADATA_IN_PROGRESS", "DESIGN_PENDING", "DESIGNING", "DESIGN_COMPLETE", "FORMATTING"],
    "QC": ["QC_PENDING", "QC", "QC_PASSED"],
    "HUMAN REVIEW": ["HUMAN_REVIEW", "CHANGES_REQUIRED", "APPROVED"],
    "READY TO PUBLISH": ["READY_FOR_PUBLISHING"],
    "PUBLISHED": ["PUBLISHED"],
    "FAILED": ["QC_FAILED", "REJECTED"],
    "BLOCKED": ["BLOCKED"],
}

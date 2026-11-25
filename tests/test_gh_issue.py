"""src/gh_issue.py: forecast-log-ийн мэдэгдлийн issue давхардахгүй (ADR 0016, #46). Хуурамч GitHub API, сүлжээгүй.  pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import gh_issue  # noqa: E402

REPO = "Monho12/trandVIZ"
TITLE = "forecast-log: 2 өдөр дараалан цоорхой"


class FakeGitHub:
    """REST API-ийн оронд: нээлттэй issue-ууд (PR ч issue-ийн жагсаалтад ирдэг), 100-аар хуудаслана."""

    def __init__(self, open_items):
        self.items, self.calls = list(open_items), []

    def __call__(self, method, path, data=None):
        self.calls.append((method, path, data))
        if method == "GET":
            page = int(path.rsplit("&page=", 1)[1])
            return self.items[(page - 1) * 100:page * 100]
        if path.endswith("/issues"):
            self.items.append({"number": 900, "title": data["title"]})
            return {"number": 900}
        return {"id": 1}


def filler(n):
    return [{"number": i, "title": f"бусад {i}"} for i in range(1, n + 1)]


def test_opens_a_new_issue_when_none_is_open():
    gh = FakeGitHub(filler(3))
    assert gh_issue.open_or_comment(gh, REPO, TITLE, "тайлбар") == ("opened", 900)
    assert [(m, p) for m, p, _ in gh.calls if m == "POST"] == [("POST", f"repos/{REPO}/issues")]
    assert gh.calls[-1][2] == {"title": TITLE, "body": "тайлбар"}


def test_comments_on_the_open_issue_with_the_same_title_instead_of_duplicating():
    """Ижил гарчигтай нээлттэй issue 2-р хуудсанд байна (101 дэх), ижил гарчигтай PR-ийг тоохгүй."""
    pr = {"number": 7, "title": TITLE, "pull_request": {}}
    gh = FakeGitHub([pr] + filler(100) + [{"number": 150, "title": TITLE}])
    assert gh_issue.open_or_comment(gh, REPO, TITLE, "дахин") == ("commented", 150)
    posts = [(p, d) for m, p, d in gh.calls if m == "POST"]
    assert posts == [(f"repos/{REPO}/issues/150/comments", {"body": "дахин"})]
    gh_issue.open_or_comment(gh, REPO, TITLE, "гурав дахь")
    assert sum(1 for i in gh.items if i["title"] == TITLE and "pull_request" not in i) == 1

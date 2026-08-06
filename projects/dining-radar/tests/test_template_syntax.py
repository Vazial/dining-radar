"""Guards a defect class: Django's ``{# ... #}`` comment syntax is
single-line only.

Django's template tokenizer matches ``{#...#}`` with a regex that has no
``DOTALL`` flag, so ``.`` never matches a newline. A ``{#`` left unclosed on
its own line therefore is *not* recognized as a comment tag at all -- the
literal ``{#``, the intended comment body, and the eventual ``#}`` all render
as ordinary page text instead of being stripped. A multi-line comment must
use ``{% comment %}...{% endcomment %}`` instead.

This was found only by a human real-device measurement (orchestrator
real-device review, 2026-08-06): three such comments in
``web/templates/web/home.html`` inflated the authenticated header to 755px
and pushed the map below the fold. No existing machine check caught it,
because the existing tests either check for the *presence* of specific
substrings/test ids (``assertContains``, acceptance ``present``/``absent``
observations) -- which still holds when unrelated extra text is also
rendered -- or never read rendered output for stray template delimiters at
all. This file adds that check at the source level (every template,
regardless of whether any current view test happens to render it) and at
the rendered-output level (defense in depth, in case some other mechanism
ever leaks the same characters).
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
COMMENT_OPEN = "{#"
COMMENT_CLOSE = "#}"


def _html_templates() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.html"))


class SingleLineCommentSyntaxSourceTests(SimpleTestCase):
    """Static, render-independent check: read every template's raw source."""

    def test_every_html_template_exists(self) -> None:
        # A guard against the glob silently matching nothing (for example if
        # the template directory layout ever moves), which would otherwise
        # make the check below vacuously pass.
        self.assertGreaterEqual(len(_html_templates()), 5)

    def test_every_open_comment_marker_is_closed_on_the_same_line(self) -> None:
        for template_path in _html_templates():
            lines = template_path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                search_from = 0
                while True:
                    start = line.find(COMMENT_OPEN, search_from)
                    if start == -1:
                        break
                    with self.subTest(template=str(template_path), line=line_number):
                        self.assertIn(
                            COMMENT_CLOSE,
                            line[start + len(COMMENT_OPEN) :],
                            f"{template_path}:{line_number} opens a `{{#` comment that is "
                            "not closed (`#}`) on the same line. Django's `{# #}` syntax "
                            "cannot span multiple lines -- the comment body would render "
                            "as literal page text. Use {% comment %}...{% endcomment %} "
                            "for a multi-line comment instead.",
                        )
                    search_from = start + len(COMMENT_OPEN)


class RenderedTemplateSyntaxLeakTests(TestCase):
    """Defense in depth: the actual rendered output of key pages must never
    contain a raw Django template delimiter, regardless of the mechanism
    that could leak one.
    """

    DELIMITERS = ("{#", "#}", "{% comment %}", "{% endcomment %}")

    def setUp(self) -> None:
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="template-syntax-organizer", password=self.password
        )
        self.client = Client()

    def _assert_no_leaked_delimiters(self, response) -> None:
        body = response.content.decode("utf-8")
        for delimiter in self.DELIMITERS:
            self.assertNotIn(
                delimiter,
                body,
                f"rendered response leaked a raw template delimiter ({delimiter!r})",
            )

    def test_unauthenticated_login_page_has_no_leaked_delimiters(self) -> None:
        response = self.client.get(reverse("authentication:login"))
        self._assert_no_leaked_delimiters(response)

    def test_authenticated_candidate_screen_has_no_leaked_delimiters(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("web:home"))
        self._assert_no_leaked_delimiters(response)

    def test_password_change_pages_have_no_leaked_delimiters(self) -> None:
        self.client.force_login(self.user)
        self._assert_no_leaked_delimiters(
            self.client.get(reverse("authentication:password_change"))
        )
        self._assert_no_leaked_delimiters(
            self.client.get(reverse("authentication:password_change_done"))
        )

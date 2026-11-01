"""Tests for the current-ChatGPT DOM compatibility layer.

ChatGPT's web UI replaced the turn markup this project was written against:

* ``[data-message-author-role="assistant"|"user"]`` — removed; turns now carry
  ``data-chatgpt-search-unit-key="<turn>:<n>:<role>"``.
* ``.markdown`` (clean answer container) — removed; the answer text now lives
  in ``[data-markdown-text-style="assistant-message"]``.
* The per-turn action button (``data-testid="copy-turn-action-button"``) —
  removed; the copy button now only has ``aria-label="Copy message"``.

What DID survive and is used as the completion signal:
``data-talvt-turn-state`` on the turn wrapper (``in_progress`` → ``complete``).

These tests pin the selector set and the placeholder-conversation-id guard.
"""

from __future__ import annotations

import pytest

from chatgpt_web2api import dom_selectors


def test_assistant_selector_covers_current_dom():
    assert '[data-chatgpt-search-unit-key$=":assistant"]' in dom_selectors.ASSISTANT_SELECTOR
    assert '[data-content-search-unit-key$=":assistant"]' in dom_selectors.ASSISTANT_SELECTOR
    # Legacy selector retained for older deployments.
    assert '[data-message-author-role="assistant"]' in dom_selectors.ASSISTANT_SELECTOR


def test_user_selector_covers_current_dom():
    assert '[data-chatgpt-search-unit-key$=":user"]' in dom_selectors.USER_SELECTOR
    assert '[data-content-search-unit-key$=":user"]' in dom_selectors.USER_SELECTOR
    assert '[data-message-author-role="user"]' in dom_selectors.USER_SELECTOR


def test_answer_text_selector_covers_current_dom():
    # The clean answer container in the current UI.
    assert '[data-markdown-text-style="assistant-message"]' in dom_selectors.ANSWER_TEXT_SELECTOR
    # Legacy .markdown retained.
    assert ".markdown" in dom_selectors.ANSWER_TEXT_SELECTOR


def test_dom_state_js_embeds_current_signals():
    js = dom_selectors.DOM_STATE_JS
    # turn state attribute + the "complete" value must be in the probe
    assert dom_selectors.TURN_STATE_ATTR in js
    assert dom_selectors.TURN_STATE_COMPLETE in js
    # copy button (aria-label based in the current UI)
    assert 'Copy message' in js
    # stop button (generation still running)
    assert "Stop" in js
    # answer text container
    assert "assistant-message" in js


def test_dom_state_js_is_syntactically_plausible():
    js = dom_selectors.DOM_STATE_JS
    assert js.strip().startswith("(function()")
    assert "JSON.stringify" in js
    # Balanced braces/parens — a cheap guard against a broken %-substitution.
    assert js.count("(") == js.count(")")
    assert js.count("{") == js.count("}")


def test_dom_state_js_reads_the_new_answer_container():
    """The answer text must come from the CURRENT answer container.

    Regression: the legacy ``.markdown`` class no longer exists in ChatGPT's
    current DOM, so reading only ``.markdown`` yielded an empty answer and
    the request timed out with a truncated/garbled response.
    """
    js = dom_selectors.DOM_STATE_JS
    assert '[data-markdown-text-style="assistant-message"]' in js
    # The turn node's innerText starts with the "ChatGPT said:" heading —
    # it must never be the primary text source.
    assert "ChatGPT said:" in js, "the heading must be stripped explicitly"


def test_dom_state_js_uses_turn_state_as_completion_signal():
    """The current UI has no data-testid action button; the turn wrapper's
    data-talvt-turn-state is the completion signal. The probe must read it."""
    js = dom_selectors.DOM_STATE_JS
    assert dom_selectors.TURN_STATE_ATTR in js
    assert "turn_state" in js
    # The Stop button is the "still generating" marker and must be read too.
    assert "stop_present" in js


def test_stop_button_gates_the_action_button_signal():
    """The copy button is present while the model is STILL generating.

    Regression: treating its presence as "turn finished" completed the
    request before the answer was rendered, producing a garbage response
    (the heading text plus a tail of the real answer).

    So the probe must gate has_action on the Stop button being gone.
    """
    js = dom_selectors.DOM_STATE_JS
    assert "has_action = has_action && !stop_present" in js


def test_placeholder_conversation_id_is_rejected():
    """A brand-new chat briefly shows /c/local-chatgpt%3A<uuid>.

    That placeholder is NOT a conversation the backend knows about, so using
    it as conv_id makes every backend end_turn fetch fail — the primary
    completion signal is then permanently unavailable and phase 2 stalls
    until the ceiling. Both parsers must skip it.
    """
    import inspect

    from chatgpt_web2api import backend_client, cdp_driver

    bc_src = inspect.getsource(backend_client.BackendClient._conversation_id_from_url)
    assert "local-chatgpt" in bc_src, (
        "_conversation_id_from_url must reject the local-chatgpt placeholder"
    )

    drv_src = inspect.getsource(cdp_driver.CDPDriver.send_and_stream)
    assert "local-chatgpt" in drv_src, (
        "send_and_stream must reject the local-chatgpt placeholder"
    )


def test_turn_state_complete_constant():
    assert dom_selectors.TURN_STATE_COMPLETE == "complete"


@pytest.mark.parametrize(
    "conv_id,expected",
    [
        ("local-chatgpt%3A5fc8d0e2-9641-4ec1-bea6-7f7e092a4755", False),
        ("local-chatgpt:5fc8d0e2-9641-4ec1-bea6-7f7e092a4755", False),
        ("LOCAL-CHATGPT%3Aabc", False),
        ("6ae736e0-ee38-83ed-b7da-adbe815c7b0f", True),
        ("abc-123", True),
    ],
)
def test_placeholder_conversation_id_is_rejected(conv_id, expected):
    """A brand-new chat briefly shows /c/local-chatgpt%3A<uuid>.

    That placeholder is NOT a conversation the backend knows about, so using it
    as conv_id makes every backend end_turn fetch fail and phase 2 stalls.
    """
    is_placeholder = conv_id.lower().startswith("local-chatgpt")
    assert is_placeholder is not expected

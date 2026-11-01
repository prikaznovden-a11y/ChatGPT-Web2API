"""Current-ChatGPT DOM compatibility layer.

ChatGPT's web UI changed its turn markup. The legacy attributes this project
was written against are gone:

* ``[data-message-author-role="assistant"]`` — REMOVED. The assistant turn is
  now marked with ``data-chatgpt-search-unit-key="<turn>:<n>:assistant"``
  (mirrored by ``data-content-search-unit-key``), or, for the rendered answer
  block, ``data-markdown-text-style="assistant-message"``.
* ``[data-message-author-role="user"]`` — REMOVED. The user turn carries
  ``data-chatgpt-search-unit-key="<turn>:<n>:user"``.
* ``.markdown`` (the clean answer container) — REMOVED. The answer text now
  lives in the element carrying ``data-markdown-text-style="assistant-message"``.
* The per-turn action row (``data-testid="copy-turn-action-button"`` & co.) —
  REMOVED. The copy button now only carries ``aria-label="Copy message"``.

Two robust signals DID survive and are used here:

* ``data-talvt-turn-state`` on the turn wrapper — ``"in_progress"`` while the
  model streams, ``"complete"`` once the turn finished. This is the authoritative
  completion signal.
* ``button[aria-label="Copy message"]`` — present only on a finished message.

Everything in this module is additive: the legacy selectors are kept alongside
the new ones so an older DOM still works.
"""

from __future__ import annotations

# ── Turn-role selectors ────────────────────────────────────────────────
# A turn node is matched if it carries ANY of these. Order matters only for
# readability; querySelectorAll returns document order regardless.

ASSISTANT_SELECTOR = (
    '[data-message-author-role="assistant"], '
    '[data-content-search-unit-key$=":assistant"], '
    '[data-chatgpt-search-unit-key$=":assistant"]'
)

USER_SELECTOR = (
    '[data-message-author-role="user"], '
    '[data-content-search-unit-key$=":user"], '
    '[data-chatgpt-search-unit-key$=":user"]'
)

# ── Answer-text containers ──────────────────────────────────────────────
# The clean answer text (no "ChatGPT said:" label, no reasoning label).

ANSWER_TEXT_SELECTOR = (
    '.markdown, '
    '[data-markdown-text-style="assistant-message"]'
)

# ── Completion signals ──────────────────────────────────────────────────

# The turn wrapper attribute + the value that means "generation finished".
TURN_STATE_ATTR = "data-talvt-turn-state"
TURN_STATE_COMPLETE = "complete"

# The finished-message copy button (aria-label based; no data-testid anymore).
COPY_BUTTON_SELECTOR = 'button[aria-label="Copy message"]'

# The Stop button is present only while the model is generating.
STOP_BUTTON_SELECTOR = 'button[aria-label*="Stop" i]'


def turn_state_js() -> str:
    """JS expression: the turn state of the LAST assistant node.

    Walks up from the last assistant turn node to the nearest ancestor
    carrying ``data-talvt-turn-state``. Returns the attribute value, or
    ``""`` when the DOM does not expose it (older UI).

    Expects a JS variable ``msgs`` (array of assistant nodes) in scope.
    """
    return (
        "(function(){"
        "  var m = window.__w2a_last_assistant;"
        "  if (!m) {"
        "    var all = document.querySelectorAll(" + _js(ASSISTANT_SELECTOR) + ");"
        "    m = all.length ? all[all.length - 1] : null;"
        "  }"
        "  if (!m) return '';"
        "  var p = m;"
        "  while (p) {"
        "    var v = p.getAttribute && p.getAttribute('" + TURN_STATE_ATTR + "');"
        "    if (v) return v;"
        "    p = p.parentElement;"
        "  }"
        "  return '';"
        "})()"
    )


def _js(value: str) -> str:
    """Quote a selector for safe embedding into a JS string literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


# ── The composite state probe ───────────────────────────────────────────
#
# One JS blob that returns everything the completion detector needs from the
# live DOM. Replaces the previous inline blob in completion_detector.py,
# which only knew the legacy selectors.

DOM_STATE_JS = """
(function() {
  var SEL = %(assistant)s;
  var msgs = document.querySelectorAll(SEL);
  if (!msgs.length) {
    return JSON.stringify({
      text: '', md_text: '', html_len: 0, child_count: 0,
      has_action: false, is_thinking: false, turn_state: ''
    });
  }
  var last = msgs[msgs.length - 1];

  // Clean answer text. The current UI marks the answer container with
  // data-markdown-text-style="assistant-message"; the legacy UI used the
  // .markdown class. The two are read differently ON PURPOSE:
  //
  //   * new container -> innerText. It holds the answer and nothing else,
  //     and it fills as the answer renders.
  //   * legacy .markdown -> textContent. Upstream uses textContent here
  //     because .markdown's innerText also carries the reasoning label
  //     ("Thinking..."), which must never leak into the answer.
  //
  // When the clean container EXISTS we never fall back to the turn node's
  // innerText: that innerText starts with the "ChatGPT said:" heading, and
  // emitting it would corrupt the answer (the final reconciliation then
  // appends only the tail of the real answer).
  var mdNew = last.querySelector('[data-markdown-text-style="assistant-message"]');
  var mdLegacy = mdNew ? null : last.querySelector('.markdown');
  var mdText = '';
  if (mdNew) {
    mdText = (mdNew.innerText || mdNew.textContent || '').trim();
  } else if (mdLegacy) {
    mdText = (mdLegacy.textContent || '').trim();
  }

  // innerText of the turn node — used ONLY for reasoning/thinking detection
  // and as a last-resort text source when no clean container exists at all.
  var rawText = (last.innerText || '').trim()
    .replace(/^ChatGPT said:\\s*/i, '')
    .replace(/^Think(ing|\\s+for)[^\\n]*\\n?/i, '');
  var text = (mdNew || mdLegacy) ? mdText : rawText;

  var html_len = last.innerHTML.length;
  var child_count = last.children.length;

  // Turn state: nearest ancestor carrying data-talvt-turn-state.
  // "complete" = the turn finished; "in_progress" = still generating.
  var turn_state = '';
  var p = last;
  while (p) {
    var v = p.getAttribute && p.getAttribute('%(turn_state_attr)s');
    if (v) { turn_state = v; break; }
    p = p.parentElement;
  }

  // Finished-message action button: aria-label based in the current UI
  // (the legacy data-testid variants are kept for older deployments).
  var ACT = '%(act_selectors)s';
  var has_action = false;
  (function() {
    var lastRect = last.getBoundingClientRect();
    var scope = last;
    for (var d = 0; scope && d <= 8; d++, scope = scope.parentElement) {
      var btns = Array.prototype.filter.call(
        scope.querySelectorAll(ACT),
        function(el) { return el.offsetParent !== null || el.getClientRects().length > 0; }
      );
      for (var i = 0; i < btns.length; i++) {
        var r = btns[i].getBoundingClientRect();
        if (r.top >= lastRect.top - 180 && r.top <= lastRect.bottom + 240) {
          has_action = true;
          return;
        }
      }
    }
  })();

  // Stop button present = generation still running.
  var stop_present = document.querySelectorAll(%(stop)s).length > 0;

  // The copy button ("Copy message") is already in the DOM while the model
  // is still generating, so its presence ALONE does not mean "turn finished".
  // The Stop button is the authoritative "still running" marker — require it
  // to be gone before treating the action button as a completion signal.
  var has_action = has_action && !stop_present;

  // is_thinking: the model is actively reasoning. Gated on has_action and on
  // the turn state, so a stale collapsed "Thought process" block cannot pin
  // is_thinking=true forever.
  var hasThinkingEl = !!last.querySelector('.result-thinking');
  var visibleThinking = /^(thinking|reasoning)\\b/i.test(rawText.trim());
  var is_thinking = !has_action
    && turn_state !== '%(turn_state_complete)s'
    && !stop_present
    && (hasThinkingEl || (visibleThinking && !mdText));

  return JSON.stringify({
    text: text,
    md_text: mdText,
    html_len: html_len,
    child_count: child_count,
    has_action: has_action,
    is_thinking: is_thinking,
    turn_state: turn_state,
    stop_present: stop_present
  });
})()
""" % {
    "assistant": _js(ASSISTANT_SELECTOR),
    "turn_state_attr": TURN_STATE_ATTR,
    "act_selectors": (
        '[data-testid="copy-turn-action-button"],'
        '[data-testid="good-response-turn-action-button"],'
        '[data-testid="bad-response-turn-action-button"],'
        '[data-testid*="turn-action-button"],'
        '[data-testid*="response-turn"],'
        'button[aria-label="Copy message"]'
    ),
    "stop": _js(STOP_BUTTON_SELECTOR),
    "turn_state_complete": TURN_STATE_COMPLETE,
}

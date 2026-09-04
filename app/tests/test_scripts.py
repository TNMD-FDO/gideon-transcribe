"""What the browser scripts must not do, checked without a browser.

Each of these files is one long function, on purpose: nothing it defines
reaches the page. The cost of that shape is that `var` belongs to the whole
function it is written in and not to the block, so two blocks that each keep
their own flag under the same name are in fact sharing one.

That is not a style question. It cost a working feature. The timeline's
`dragging` and the picture-resize grip's `dragging` were one variable; the
grip cancels its drag on any pointerup, and a browser sends pointerup before
mouseup, so every click on the timeline of a video was cancelled before the
timeline could act on it. A recording with no picture has no grip, so audio
scrubbed and video did not, which made it look like a fault in video
playback. It took a day to find.
"""

import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "static"

A_NAME = re.compile(r"[A-Za-z_$][\w$]*")


def every_script():
    return sorted(SCRIPTS.glob("*.js"))


def without_words_or_comments(text: str) -> str:
    """The code with strings and comments blanked, so a scan sees only code."""
    out = []
    in_string = None
    line_comment = block_comment = False
    previous = ""
    for character in text:
        keep = " "
        if line_comment:
            if character == "\n":
                line_comment = False
                keep = "\n"
        elif block_comment:
            if previous == "*" and character == "/":
                block_comment = False
            elif character == "\n":
                keep = "\n"
        elif in_string:
            if character == in_string and previous != "\\":
                in_string = None
        elif previous == "/" and character == "/":
            line_comment = True
            out[-1] = " "
        elif previous == "/" and character == "*":
            block_comment = True
            out[-1] = " "
        elif character in "\"'`":
            in_string = character
        else:
            keep = character
        out.append(keep)
        previous = character
    return "".join(out)


def declared_twice(text: str) -> list[str]:
    """Names declared with `var` twice in one function's scope.

    A `{` that follows the word `function` or an arrow opens a new scope for
    `var`; every other `{` is a block, which does not.
    """
    code = without_words_or_comments(text)
    scopes = [{}]
    depths = [0]
    depth = 0
    opens_a_scope = False
    trouble = set()

    for match in re.finditer(r"\bfunction\b|=>|[{}]|\bvar\s+([A-Za-z_$][\w$]*)", code):
        piece = match.group(0)
        if piece in ("function", "=>"):
            opens_a_scope = True
        elif piece == "{":
            depth += 1
            if opens_a_scope:
                scopes.append({})
                depths.append(depth)
                opens_a_scope = False
        elif piece == "}":
            if len(depths) > 1 and depth == depths[-1]:
                scopes.pop()
                depths.pop()
            depth -= 1
        else:
            name = match.group(1)
            here = scopes[-1]
            if name in here:
                trouble.add(name)
            here[name] = True

    return sorted(trouble)


def test_there_are_scripts_to_check():
    assert len(every_script()) > 3


def test_no_name_is_declared_twice_in_one_scope():
    trouble = []
    for script in every_script():
        again = declared_twice(script.read_text(encoding="utf-8"))
        if again:
            trouble.append(f"{script.name}: {', '.join(again)}")

    assert not trouble, (
        "these names are declared twice in one function's scope, and `var` "
        "belongs to the function and not the block, so each pair is one "
        "variable shared by two pieces of code that each believe it is "
        "theirs:\n" + "\n".join(trouble)
    )


def test_the_check_catches_what_it_is_for():
    # The exact shape of the fault it exists to prevent.
    assert declared_twice(
        "(function () {"
        "  if (a) { var dragging = false; }"
        "  if (b) { var dragging = false; }"
        "}());"
    ) == ["dragging"]


def test_the_check_leaves_separate_functions_alone():
    # Two functions may each keep their own, because each is its own scope.
    assert (
        declared_twice(
            "function one() { var here = 1; } function two() { var here = 2; }"
        )
        == []
    )
    assert (
        declared_twice(
            "(function () { var a = 1; function inner() { var a = 2; } }());"
        )
        == []
    )


def test_the_check_is_not_fooled_by_words_or_comments():
    assert declared_twice('var a = 1; var s = "var a = 2";') == []
    assert declared_twice("var a = 1;\n// var a = 2\n") == []

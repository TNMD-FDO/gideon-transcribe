# The look

How every page of Gideon Transcribe is drawn, written down once (v1.107.0,
2 October 2026) so that a new page is styled by these rules and not on its
own day. The stylesheet is `app/static/app.css`; its head repeats this in
six lines, and every value below is a token there.

## Type

Five sizes, and nothing else a person reads:

| Size | Token | For |
| --- | --- | --- |
| 22 | `--t-title` | the page's title, one to a page |
| 17 | `--t-heading` | a section's heading (`h2`) |
| 15 | `--t-body` | the text |
| 13 | `--t-small` | the secondary words: facts under a name, a caption, a hint |
| 11 | `--t-label` | an uppercase label over a group, and the eyebrow of a page |

The display size (28) is for a figure, such as the incident's clock, never a
title. IBM Plex Sans for words, IBM Plex Mono for times and counts, with
tabular digits wherever digits line up.

Two more sizes, named since v1.178.0 and used nowhere else: `--t-count`
(20) for a count beside its words, as in the needs box, and `--t-reading`
(16) for the lines of a transcript being read on the recording page and the
Speakers page. Amended v1.178.0 at the maintainer's decision from
`docs/spec/mockups/phase-8-type-scale.html`: the tables, the rail's names
and buttons, the top bar's name, the tabs, the banner and the toast are the
body size (they were 14); the dense parts (the chips that narrow a list, a
voice's chain, a person card's chain, a chronology entry's line and its
sheet, the guided Speakers page's quoted samples) are the small size (they
were 12). The stylesheet writes no size in pixels but these tokens, and a
test keeps it so.

## Buttons

Four kinds at two sizes. A plain button is the **secondary** (outlined,
surface-coloured); **primary** is filled with the accent; **ghost** is text
in the accent with no border, for the quiet tool inside a panel; **danger**
is red text and stands last in a row. The sizes are regular (34 pixels
tall) and small (28). `tiny` is small and `big` is regular; the player bar's
Play is the one taller button, and it belongs to the bar.

One primary a page, beyond the rail's Upload files: the thing a person came
to do (New case on the Cases page, Add recordings on a case, Download all on
Clips). Where a page is several forms, each form may have its primary. A
row's own buttons (Open, Download, Keep) are secondary. A filter in force is
lit as a pressed button (`.on`), not as a primary.

Tabs are tabs, and the player bar is its own thing; neither is a button.

## Cards, tables and pills

One radius for anything that holds content (8, `--radius-lg`), one border
(`--line`), one inner padding (14 by 16). Buttons, inputs and the small
things take the smaller radius (6, `--radius`). Pills are one shape, and
their colour is the state: green, amber, red, grey; the orange "As an Admin"
pill is a warning and stays orange.

Under 700 pixels every row-per-thing table is a card: the name on its own
line, the facts in a muted line, the row's button at the top right.

## The head of a page

Every page opens the same way (`.page-head`): an eyebrow for where you are
(a link up, such as Cases, or the place, such as Panel), the title at the
title size, and the page's one main action at the right on the same line. A
lead sentence sits under them when the page has one. On a phone the action
drops under the title. Upload files and New recording had a larger, centred
title of their own; they take this one, and so does the document page
(v1.114.0), whose eyebrow holds the case's name and the ways back to the
incident or recording the report is for.

The recording page, a work page whose head sits beside the picture, keeps
the same order on two lines: the title line (back, the case, the title and
its pills) and the action line (find, New clip, Export, More), with Export
shrinking to its icon under 1200 wide.

## Nothing here

One pattern for an empty place: the icon, a heading that says what the place
is for, a sentence, and the one action that fills it. Inside a section that
has its own border (Home's sections) the same pattern sits without a second
box.

## Space

The reading pages (Home, Cases, a case, Clips, My recordings) are capped at
1400 pixels, so a desk monitor shows a wider list rather than a wider
margin. From 1600 wide Home stands Cases on the left (three fifths) and This
session on the right inside that cap, two lists of a like length stretched
to one height; under 1600 they are one list in that order. The work pages (the recording,
the Speakers page, an incident) take the whole width. The document page is
the pair it shows: the page picture at the window's height, the words beside
it at a reading measure (40rem), centred and never over 1600.

## Colour

The accent is for the primary button, links, and the current item (a tab, a
chip, a pressed filter). Everything that says a state says it in the pills'
four colours. Light and dark are two palettes for the same roles, not an
inversion, and a colour written into a rule rather than a token is a
mistake.

The borders are quiet on purpose (v1.179.0, from the dark walk): `--line` on
`--surface` sits near 1.4 to 1 in light and 1.5 in dark, and a pill's fill
near 1.2 in both, under the 3 to 1 an accessibility boundary asks for. A
control reads by its words, its fill against the page and its focus ring,
and a pill says its state in the colour of its words, which meet 4.5 to 1
on every page in both themes. Where the server names a colour by a hex for
the exports (the chronology's cameras), the page paints the same thing in
its own token, so dark gets the dark palette.

## The page change (v1.171.1)

Every press loads a whole page. The browser crossfades from the old page to
the new (cross-document view transitions, `@view-transition { navigation:
auto }` in `app.css`), with the top line, the rail and the case's tabs named
so they hold still while only the content fades; the root carries the theme's
background and the page declares both colour schemes, so the blank between
two paints is never white. A browser without view transitions keeps the plain
load; a person who asked their system for less motion gets no animation.
Nothing is prefetched or prerendered, on purpose: opening a page is a use of
the case, and for an Admin an audit row, and a hover must open nothing.

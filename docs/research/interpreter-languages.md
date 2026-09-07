# The Interpreter's languages: what each tool can do, per language

Read on 2026-09-07, before the build of Phase 3 chapter 3 (The Interpreter).
The chapter says the app ships a table of what it can do per language and the
Admin ticks the languages the office offers; this note is where that table
comes from and what each column rests on. Nothing here is office-specific.

## The four things a language needs

A Session hears the Visitor, writes English, writes the Visitor's language,
and, when the office wants it, speaks. Each is a different tool with its own
list of languages:

1. **Hears it.** Whisper, the model the WhisperX service runs (`large-v3-turbo`
   by default). Whisper's tokenizer names 99 languages, Cantonese among them
   as `yue`, and the model detects the language itself. Every language below is
   in that list.
2. **Aligns it.** WhisperX gives words their timing with a second model per
   language, and has one for 41 languages; for the rest, a Segment has its
   start and end and its words carry no timing. The service already lets an
   office name which alignment models to pull (`WHISPERX_ALIGN_LANGUAGES`,
   `en,es` by default). A Turn does not need word timing, so this column only
   decides whether the Session's transcript gets it.
3. **Translates into it.** Whisper translates any language it hears into
   English in one step (`task: translate`), and never out of English. English
   into the Visitor's language is the engine's job: the AI assistant's engine,
   the office's shared `Qwen3.8-27B-FP8` or the Local engine's `Qwen3.5-4B`.
   Qwen3 claims 119 languages and dialects in training and Qwen3.5 claims 201.
   A claim of coverage is not a measure of quality: the table marks this
   column "claimed" for every language, and the rule the chapter sets stands:
   **the office offers a language only after a bilingual reader has read a
   translated sample and said it is usable.** Spanish first.
4. **Speaks it.** A Voice for the language must be installed. Piper has voices
   for 43 locales; Kokoro for 9 languages. See `piper-voices.md` for the
   tools and their licences.

## The table

The languages an office in the United States is likeliest to meet at the
door, from what the tools publish. "Aligns" is WhisperX's default alignment
list; "Voice" names the Piper locale(s) or Kokoro code, or says none.

| Language | Hears (Whisper) | Aligns (WhisperX) | Translates into (engine) | Voice |
|---|---|---|---|---|
| Spanish | yes | yes (`es`) | claimed; check first | Piper `es_ES`, `es_MX`, `es_AR`; Kokoro `e` |
| Portuguese | yes | yes (`pt`) | claimed; check | Piper `pt_BR`, `pt_PT`; Kokoro `p` (Brazil) |
| French | yes | yes (`fr`) | claimed; check | Piper `fr_FR`; Kokoro `f` |
| Haitian Creole | yes (`ht`) | no | claimed; check | none |
| Chinese (Mandarin) | yes (`zh`) | yes (`zh`) | claimed; check | Piper `zh_CN`; Kokoro `z` |
| Cantonese | yes (`yue`) | no | claimed; check | none |
| Vietnamese | yes | yes (`vi`) | claimed; check | Piper `vi_VN` |
| Arabic | yes | yes (`ar`) | claimed; check | Piper `ar_JO` |
| Russian | yes | yes (`ru`) | claimed; check | Piper `ru_RU` |
| Ukrainian | yes | yes (`uk`) | claimed; check | Piper `uk_UA` |
| Korean | yes | yes (`ko`) | claimed; check | none |
| Somali | yes (`so`) | no | claimed; check | none |
| Swahili | yes (`sw`) | no | claimed; check | Piper `sw_CD` |
| Amharic | yes (`am`) | no | claimed; check | none |
| Hindi | yes | yes (`hi`) | claimed; check | Piper `hi_IN`; Kokoro `h` |
| Punjabi | yes (`pa`) | no | claimed; check | none |
| Tagalog | yes (`tl`) | yes (`tl`) | claimed; check | none |
| German | yes | yes (`de`) | claimed; check | Piper `de_DE` |
| Italian | yes | yes (`it`) | claimed; check | Piper `it_IT`; Kokoro `i` |
| Japanese | yes | yes (`ja`) | claimed; check | Kokoro `j` |

The full lists, for the app's own table: Whisper's 99 (the tokenizer), the 41
alignment codes (`en fr de es it ja zh nl uk pt ar cs ru pl hu fi fa el tr da
he vi ko ur te hi ca ml no nn sk sl hr ro eu gl ka lv tl sv id`), Piper's 43
locales (`ar_JO ca_ES cs_CZ cy_GB da_DK de_DE el_GR en_GB en_US es_AR es_ES
es_MX fa_IR fi_FI fr_FR hu_HU is_IS id_ID it_IT ka_GE kk_KZ lb_LU lv_LV ml_IN
hi_IN ne_NP nl_BE nl_NL no_NO pl_PL pt_BR pt_PT ro_RO ru_RU sk_SK sl_SI sr_RS
sv_SE sw_CD te_IN tr_TR uk_UA vi_VN zh_CN`), and Kokoro's 9 (`a` American
English, `b` British English, `e` Spanish, `f` French, `h` Hindi, `i` Italian,
`j` Japanese, `p` Brazilian Portuguese, `z` Mandarin).

## What this decides for the build

- **Spanish is the first and, at the start, the only offered language**, with
  three Piper voices to choose from (Spain, Mexico, Argentina) and Kokoro as a
  second opinion if Piper's Spanish disappoints a bilingual ear.
- **A language with no Voice is text-only** and the Languages settings page
  says so; that is most of the list beyond the twenty above.
- **A language with no alignment model** gets a transcript without word
  timing, which the viewer already handles (a translated transcript has none
  either). Nothing to build.
- **The "check first" column is a gate, not a flag.** The Languages page shows
  every language the tools cover, greyed until an Admin ticks it; the wording
  beside the tick says a bilingual reader should have read a sample. The app
  cannot check quality itself and does not pretend to.
- **Whisper's language detection** on a short Turn can be wrong; the chapter
  already says the chosen language is what the Readback is written in and a
  Turn heard in a third language is shown as heard, not translated.

## Sources

- Whisper's language list: <https://raw.githubusercontent.com/openai/whisper/main/whisper/tokenizer.py> (the `LANGUAGES` dict, 99 entries, and `TO_LANGUAGE_CODE` aliases), read 2026-09-07.
- WhisperX's default alignment models: <https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py> (`DEFAULT_ALIGN_MODELS_TORCH`, `DEFAULT_ALIGN_MODELS_HF`), read 2026-09-07.
- Qwen3's 119 languages: the Qwen3 technical report, <https://arxiv.org/abs/2505.09388>, and the release post <https://qwenlm.github.io/blog/qwen3/>; Qwen3.5's 201: the release coverage at <https://alternativeto.net/news/2026/2/alibaba-launches-qwen3-5-with-open-weight-397b-model-and-broader-language-support>, read 2026-09-07.
- Piper's voice locales: <https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md>, read 2026-09-07.
- Kokoro's languages: <https://raw.githubusercontent.com/hexgrad/kokoro/main/README.md> and <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md>, read 2026-09-07.

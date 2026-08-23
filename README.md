# job-screener

A browser button that reads the job posting you are looking at, sends it to an LLM
running on **your own machine**, and paints a structured verdict over the page:
GO / MAYBE / NO with a score, the fit, the concerns, the red flags, and the questions
you should ask in the interview.

No extension to install, no SaaS, no account, nothing leaves your network except the
model call itself.

```
Browser (Violentmonkey/Tampermonkey)        Your server
  [ Screen ]
     |
     |-- page text ------- POST /screen --> server.py
     |                                        |
     |                                        +-- profile.md + prompt ---> LLM
     |                                        |
     |<------------------ JSON verdict -------+
     |
     +-- overlay: verdict, fit, concerns, red flags, questions
```

---

## Why it is built this way

The obvious version of this is a browser extension that talks to a hosted API. This
one splits differently, and the split is the point:

**The browser is only a sensor and a display.** The userscript does one thing — grab
the visible text and render whatever comes back. It holds no prompt, no API key, no
model, no preferences. When a site changes its markup, the fix is in one file and
nothing else moves.

**The server owns the judgement.** `server.py` is a plain stdlib HTTP server that
composes the posting with `profile.md` and hands it to the model. It runs on a home
server, holds the credentials, and appends every verdict to a log.

**The tuning surface is a markdown file, not code.** When verdicts come out wrong,
you edit `profile.md` — what you are looking for, your dealbreakers, what counts as a
red flag. The server serves an editor for it at `/` so you can fix it from the same
browser you are screening in, Ctrl+S to save. In months of use I have edited the
profile many times and the scoring code approximately never.

**The prompt is a hard output contract.** `prompt.md` specifies strict JSON with a
fixed schema — verdict, score, company, role, salary, location, tldr, fit, concerns,
red_flags, questions — and forbids any prose around it, so `json.loads()` is the whole
parser. Anything unparseable surfaces in the overlay as an error with the raw text
rather than being silently swallowed.

---

## Endpoints

| | |
|---|---|
| `POST /screen` | job posting text -> JSON verdict |
| `GET /` | browser editor for `profile.md` |
| `GET/POST /profile` | read / write the profile |

---

## Running it

```bash
cp profile.example.md profile.md    # then edit it - this is the tuning surface
python3 server.py                   # listens on 0.0.0.0:8080
```

```bash
curl -X POST localhost:8080/screen \
     -H 'Content-Type: application/json' \
     -d '{"text":"We are hiring a Python developer in Prague...","url":"https://..."}'
```

Then install `screen.user.js` in Violentmonkey or Tampermonkey and set `SERVER_HOST`
at the top of the file to wherever `server.py` runs. Open a posting, press **Screen**.

To keep it running:

```bash
cp job-screener.service ~/.config/systemd/user/
systemctl --user enable --now job-screener
journalctl --user -u job-screener -f
```

No dependencies outside the standard library. The model is invoked through the
`claude` CLI (`claude -p`), so it runs on an existing subscription with no API key;
swapping that call for a hosted API is a few lines in `server.py`.

---

## Notes

- **`prompt.md` is in Czech**, because the verdicts are written in Czech for a Czech
  reader — that is the file's job. The schema it enforces is language-independent and
  documented above.
- A sibling version of this drives LinkedIn search results rather than single
  postings, with a two-stage pipeline: one cheap batched call triages a whole result
  page, and only survivors get an expensive per-posting call. That cost split is the
  interesting part of it, and the same server pattern carries it.
- **Scraping etiquette:** this reads the page you have already opened, only when you
  press the button. Automating a site further than that tends to violate its terms of
  service — check before you extend it.
- Built with AI pair-programming (Claude Code).

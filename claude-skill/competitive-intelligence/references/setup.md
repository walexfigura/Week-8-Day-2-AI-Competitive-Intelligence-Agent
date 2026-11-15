# Setup

## Install the Skill
1. Get `competitive-intelligence-skill.zip` (build it from the repository with
   `python run.py build-skill`; it is written to `dist/`).
2. In Claude, open the Skills area of your settings and upload the ZIP. Custom Skills
   require a plan with Skills and code execution enabled; menu names can change, so
   check Anthropic's help center if you cannot find the option.
3. Enable the Skill. Claude loads it automatically when a request matches its
   description (for example "What changed on PeakTrail's product page?").

## Try the fictional demo (Mode A)
Ask: *"Use the competitive-intelligence skill with its sample data. Did PeakTrail really
lower the price of the bottle that competes with Northstar's Summit 32 oz, and what do
its reviews say?"* Claude should read `sample-data/`, say the data is fictional, and
reach the conclusions in `example-scenarios.md`.

## Use your own business
Replace or supplement the demo context. Provide, in a message or uploaded files:
1. **Your products** — IDs, prices, sizes, **verified** features (with evidence),
   limitations. Template: `sample-data/northstar-context.md`.
2. **Customers** — the segments you serve and what they care about.
3. **Watchlist** — competitors, the specific variants that compete with your products,
   and how directly comparable each is (direct / partial / none).
4. **Priorities** — what counts as high, medium, low, and no-alert for you.
5. **Observations** — product-page captures with dates (copy/paste, saved HTML, PDFs, or
   spreadsheets), and review exports you are allowed to use.

To make your context permanent, edit `sample-data/northstar-context.md` (or add your own
file and reference it from SKILL.md), then rebuild and re-upload the ZIP.

## Limits
The Skill cannot schedule itself, monitor pages continuously, or access systems that
are not connected to this conversation. Each run analyzes what is available now.

<div align="center">

<img src="assets/banner.png" alt="Paper2XHS project banner: from arXiv papers to Xiaohongshu content (concept illustration)" width="100%">

# Paper2XHS

**Turn research papers into Xiaohongshu posts. Let feedback inform the next one.**

An Agent Skill for researchers and science creators working on reinforcement learning, embodied AI, and robot learning.


![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![Agent Skill](https://img.shields.io/badge/Agent-Skill-0066cc?style=flat-square)
[![GitHub stars](https://img.shields.io/github/stars/GetIT-Sunday/xhs-rl-paper-share?style=flat-square)](https://github.com/GetIT-Sunday/xhs-rl-paper-share)

[Quick start](#quick-start) · [Account setup](#account-setup-and-publishing) · [What you can do](#what-you-can-do) · [Feedback](#feedback-that-informs-decisions) · [Documentation](#documentation)

</div>

## Quick start

Send this to an Agent with GitHub Skill installation support:

```text
Help me install Paper2XHS from https://github.com/GetIT-Sunday/xhs-rl-paper-share with Skills. Install the repository root as the paper2xhs skill.
```

Open a new session or refresh Skills, then create a draft you can review:

```text
Use $paper2xhs to choose a recent robot-learning paper, write an evidence-grounded Chinese Xiaohongshu draft, and create a paper-page cover. Show me the result without publishing.
```

You get **a paper selection, an Evidence Pack, a Chinese draft, and a PDF first-page cover**. Your Agent writes the post; the scripts handle retrieval, evidence preparation, and files. Drafting needs no Xiaohongshu login or separate LLM API key.

**Requirements:** Python 3.10+, macOS/Linux or Windows WSL, and a Skill-capable Agent that can run local scripts. Dependency installation and paper retrieval need network access; account setup needs a browser.

<details>
<summary><strong>Install manually in Codex</strong></summary>

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/paper2xhs"
```

If that directory already exists, update or back it up first. Alternatively, extract a maintainer-provided `paper2xhs.zip` into your Skills directory. Keep the entire `paper2xhs/` folder, including its scripts and references.

</details>

## Account setup and publishing

When you are ready to publish, ask your Agent:

```text
Use $paper2xhs to open the account setup wizard. After login and account verification, show the draft and cover, then continue according to my publishing instructions.
```

| Step | Your action | What Paper2XHS does |
|---|---|---|
| 1. Check the environment | Open the local setup page provided by the Agent | Check dependencies and cached login; display readiness |
| 2. Sign in | Scan with the Xiaohongshu app and confirm on your phone | Read the authenticated account identity from the platform |
| 3. Confirm the account | Check the nickname, account ID, and profile; confirm | Save private local configuration and return status to the Agent |
| 4. Publish the draft | Review the account, title, text, and cover; specify your publishing intent | Recheck the account online before publishing and record the platform response |

The page supports checking an existing login and switching accounts. It listens only on localhost and closes after 15 minutes by default. Cookies stay out of chat, logs, and the Skill package. **Saving configuration does not publish a post or start scheduled tasks.**

An embedded browser can show the page beside the conversation; other hosts use a local browser. This is a local webpage launched by the Skill. Remote Agents need a local runtime or port forwarding. Live metrics still require a verified field mapping.


### The setup page beside your Agent

When the Skill finds that no account is configured, the Agent opens this local page beside the conversation. You scan, verify the account, and confirm there before returning to the conversation; the QR area and account details in this screenshot are redacted.

<img src="assets/setup-wizard.png" alt="Paper2XHS local account setup page opened beside the Agent conversation; QR and account details redacted" width="100%">

*UI example: the page runs locally; saving configuration does not publish a post.*

## What you can do

| Capability | What Paper2XHS provides |
|---|---|
| **Find a topic** | Retrieve arXiv candidates, deduplicate publication history, and rank papers using relevance, freshness, available evidence, and applicable strategy weights. |
| **Write from evidence** | Keep source links, abstract passages, numbers, and terms in an Evidence Pack; let the host Agent turn them into a Chinese draft. |
| **Configure and publish** | Sign in locally and verify the actual account; prepare a PDF cover and topic tags, then publish when requested. |
| **Learn from feedback** | Import metrics or use the configurable creator-center adapter, store timestamped snapshots, and update expression-strategy weights. |
| **Keep an audit trail** | Record the selected strategy and policy version; keep credentials, drafts, publication history, and metrics on your own machine. |

Try requests such as:

- “Use $paper2xhs to explain this arXiv paper for a robot-learning audience. Include the method, evidence, and limitations.”
- “Use $paper2xhs to import this creator-center export and explain how the feedback affects topic ranking.”
- “Use $paper2xhs to publish the draft I approved and record its strategy.”

**Skill writing and script generation are different:** the host Agent writes the complete Chinese post. The standalone generator and unattended script scheduler currently produce abstract-based templates.

## Example output

<img src="assets/screenshot_demo.png" alt="Example: an arXiv paper on the left and a published Chinese Xiaohongshu note on the right" width="820">

*From paper to published note — an existing project example, not a live metrics dashboard.*

## Evidence you can trace

An **Evidence Pack** is a local record of what the available paper material supports: source URLs, abstract passages, numbers, and terms. It lets the Agent check a draft against its source instead of inventing methods or results.

The bundled checker flags some unsupported numbers and English terms. It is not a full semantic fact checker, and the publisher currently treats findings as warnings. Claims beyond the abstract require reading the full paper and recording that evidence.

See the [content and attribution guide](references/skill-content.md) for the draft JSON format, strategy labels, and source requirements.

## Feedback that informs decisions

The feedback path is **metrics → timestamped snapshots → smoothed strategy weights → candidate ranking and draft strategy**.

- **Keep measurements distinct.** Missing counters remain unknown. Views are not impressions, and account-level net followers are not attributed to individual posts.
- **Compare at a similar age.** Learning takes one eligible observation per note, normally 24–30 hours after publication, with known impressions and an attributable strategy. Repeated polling does not create extra training samples.
- **Smooth sparse feedback.** Capped Gamma–Poisson event-rate estimates limit any one note's exposure contribution to 10,000 and update weights for the strategy actually used.
- **Record the decision.** Candidate ranking and template generation read the policy; the publishing scheduler reranks cached and new candidates and saves the selection record.

These weights describe observed association, not proven causal improvement. If there is no usable policy, drafting defaults to a neutral explanation style.

**Local CSV/JSON import is available. Live collection requires login and a verified field mapping.** The example mapping is synthetic and defaults to `unknown` counter scope. Only select `lifetime` after confirming the platform's cumulative-counter semantics. See the [operations guide](references/skill-operations.md) before enabling live collection or recurring publishing.

## Run it from the terminal

For contributors or users who prefer scripts:

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git
cd xhs-rl-paper-share
python3 scripts/paper2xhs.py doctor
python3 scripts/paper2xhs.py setup
python3 scripts/paper2xhs.py run fetch -- --count 5 --days 7
python3 scripts/paper2xhs.py prepare
```

`prepare` selects from available candidates and prints a draft path; it does not publish. `--count` controls retrieval per search keyword, not the final number of papers. If `python3` is older than 3.10, use an installed newer interpreter such as `python3.12`.

When login is needed, start the setup page in a separate terminal:

```bash
python3 scripts/paper2xhs.py configure
```

Open the `url` from the first JSON line and keep that terminal running. After confirming the account on the page, run `doctor` in another terminal to check `configuration_complete`. Skip this step for drafting alone. Publishing commands and metrics setup are in the [operations guide](references/skill-operations.md).

The default private workspace is `~/.local/share/paper2xhs/`:

| Location | Contents |
|---|---|
| `app/references/` | Candidate papers and drafts |
| `app/assets/covers/` | Generated paper-page covers |
| `data/` | Metrics snapshots, policy weights, reports, decisions, and publication records |
| `cookie.json` | Local login cache, when configured |
| `config.json` | Confirmed account and credential fingerprint |
| `configure-status.json` | Setup-session status for the Agent to resume your task |

Set `PAPER2XHS_HOME` to change the workspace; use a separate workspace for each account. `doctor` reports the resolved paths without displaying credentials. Updating the Skill refreshes program files while retaining private data.

<details>
<summary><strong>Offline setup and feedback reports</strong></summary>

`setup --skip-deps` prepares the standard-library workflows without installing third-party packages. It does not enable online publishing or PDF rendering.

```bash
python3 scripts/paper2xhs.py setup --skip-deps
python3 scripts/paper2xhs.py run feedback -- report
```

To import your own export, ask the Agent to use its absolute file path. Start with a dry run; verify timestamps, counter scope, account identity, and field mapping before updating the ledger.

</details>

## Current boundaries

| Area | Status |
|---|---|
| Online platform access | Uses an unofficial adapter. Login, signature compatibility, and current metric fields need verification on the user's account. |
| Publishing | Installation and local previews do not publish. `--private` creates a real private post on the platform. |
| Scheduling | `run schedule` may wait for a time slot and then publish one note. It is not an installed recurring service. |
| Optional integrations | The Skill currently blocks MCP/Bridge publishing: their separate login sessions cannot reuse this wizard’s account verification. |
| Advanced covers | Paper-page covers are included; model-generated covers require separately configured image capabilities. |

## FAQ

<details>
<summary><strong>The QR code expired or the setup page will not open.</strong></summary>

Generate a new QR code on the page. The setup service exits after 15 minutes by default; ask the Agent to reopen it when the link expires. With a remote Agent, your browser must be able to reach its local service. Do not expose the setup port publicly.

</details>

<details>
<summary><strong>I scanned the code. Why is publishing still blocked?</strong></summary>

The platform must return the authenticated account, and you must confirm it on the page. Verification challenges, signature errors, or an account change stop the check. Keep the draft and complete any required verification in Xiaohongshu before retrying. Setup completion does not prove every publishing or metrics endpoint works.

</details>

<details>
<summary><strong>Do I need to edit code when arXiv retrieval fails?</strong></summary>

Retrieval retries transient request failures. If it still fails, it reports the error and preserves cached candidates. Retry later, or ask the Agent to work from a specific paper and accessible source material.

</details>

## Documentation

| Read this | For |
|---|---|
| [Skill instructions](SKILL.md) | Agent entrypoint, supported tasks, and execution boundaries |
| [Content guide](references/skill-content.md) | Evidence, Chinese writing, and strategy attribution |
| [Operations guide](references/skill-operations.md) | Login, metrics mapping, private storage, and scheduling |
| [Metrics mapping example](examples/creator_metrics.config.example.json) | Starting a configuration after checking the real schema |
| [Tests](tests/) | Snapshot, policy, publication metadata, and isolated Skill-package checks |

The content and operations guides are currently written in Chinese.

Project structure:

```text
SKILL.md                     Agent tasks and execution rules
scripts/paper2xhs.py          Unified entrypoint and private runtime
scripts/configure.*          Local account setup page
scripts/account_state.py     Account confirmation and pre-publish verification
scripts/                     Retrieval, evidence, covers, publishing, feedback
references/                  Writing and operations guides
examples/                    Sanitized metrics-mapping examples
tests/                       Isolated install, account boundaries, feedback
```

Real account data stays in the private workspace and is not part of this distribution structure.

## Contributing

Report reproducible problems through [Issues](https://github.com/GetIT-Sunday/xhs-rl-paper-share/issues) or submit a pull request. For platform-adapter changes, describe the checked field semantics using sanitized examples; omit cookies and real account exports.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py
```

The packager writes `dist/paper2xhs.zip` from an explicit allowlist. It excludes historical posts, credentials, and operational metrics; publishing a Release is a separate maintainer action.

## License

Previous documentation stated MIT, but this checkout does not contain a `LICENSE` file. The maintainer needs to confirm the license and add its text before the licensing status is settled.

## Star history

[![Star History](https://api.star-history.com/svg?repos=GetIT-Sunday/xhs-rl-paper-share&type=Date)](https://star-history.com/#GetIT-Sunday/xhs-rl-paper-share&Date)

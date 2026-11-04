# Hive-Mind — submission form answers

Team: Dollhouse Deviants. Track: Indie Developer. Theme: Build for Your World.
Copy each block into its field. Items marked YOUR PICK need one tap from you — my suggestion is noted, the choice is yours.

## Which track are you submitting to?

Indie Developer

## Which problem statement did you build towards?

Build for Your World

## Most Viral Track X post link

Leave blank — not competing for the Most Viral Track.

## Project Description

Hive-Mind is a provider-neutral persistent memory layer for every AI you use — "Never Restate Yourself." Every AI assistant starts from zero and forgets what the last one knew, so people restate themselves to each one, every time. Hive-Mind ends that: one local-first memory store (SQLite + JSONL + Markdown vault) that any MCP client can read and write, so a fact captured once is available to every assistant, forever, without being retyped or re-explained.

Every capture passes a Burn-After-Reading scrubber before anything is stored or sent — API keys, passwords, and secrets are trapped and counted, never saved. Cross-Hatch verification checks each fact for consistency before it is trusted, and contradictions never overwrite silently: they wait for an explicit human yes, with the change written down. A Caveman shorthand layer compresses recall to save tokens, and a living nebula graph grows from a dust cloud to a Radiant Sun as memories arrive and get verified.

Accessibility and security are version-one features, not add-ons. The interface is built for neurodivergent users as well as everyone else: one-flick presets that change font, color, and spacing together for common dyslexic and ADHD needs without a settings maze, with finer controls underneath for those who want them — including dyslexia letter-spacing kept moderate and capped, because spacing pulled too wide breaks letter grouping. Typed color-blind palettes cover every type, a pure-grayscale achromatopsia mode verified by a grayscale-only user keeps every meaning readable without color, and fast tooltips explain every control in plain words. On security: storage is local-first, and the snapshot backup is a private, secure backend the user sets up themselves — nothing is hosted publicly, and no snapshot ever leaves the machine to a cloud the user did not configure with their own keys. Ultimate access always stays with the end user: the user's own keys and approvals gate every external connection, and nothing is sent anywhere without the scrubber and the user's own consent.

## Public GitHub Repository

https://github.com/musclehed03/hive-mind-mcp

## 3-Minute Demo Video

https://rumble.com/v7hueg0-hive-mind-your-ai-finally-remembers-never-restate-yourself-hive-mind-mcp-de.html
(v2 with lead-in title + scenario cards, 3:07. The v1 cold-open upload is a different link — do not use it.)

## Describe your use of Meta products to build the submitted project

Muse Spark, through the Meta Model API (OpenAI-compatible endpoint), does the two judgment jobs in Hive-Mind: Cross-Hatch verification — judging whether a candidate fact is consistent with, or contradicts, what is already stored — and Caveman compression, shrinking verified facts into token-saving shorthand for recall. Both run behind the local scrubber, so no unscrubbed text ever reaches the API, and both are capped by a hard 5-call-per-process budget in the live client. The live gates were verified end to end on November 1, 2026: three facts verified live via the API, and one snapshot backup uploaded to Supabase, hash-checked, and deleted — $0.02 of the $150 free credits used, $0.00 charged. Llama open weights are documented as the offline fallback architecture. Muse Code was not used to build this repo.

## Why are Meta's models important to your solution?

Verification is a judgment call, not a lookup. A local rules engine can match words; it cannot judge whether "the shop opens at 10am" contradicts "the shop opens at 9am," or compress a fact into shorthand without losing its meaning. Muse Spark does both, through one OpenAI-compatible API, with reasoning depth that made the verification verdicts trustworthy — and the free credits made it possible to prove the live path end to end before submitting, rather than claiming it. Without a model that can reason about consistency, Hive-Mind would be a notebook. With Spark, it is a memory that checks itself.

## Feedback from your experience using partner technologies (Fireworks, Modal, Baseten)

Did not use Fireworks, Modal, or Baseten on this project. No feedback to give on them.

## How likely are you to build with Meta Model API? (required)

YOUR PICK. Suggestion: Very likely — the OpenAI-compatible shape and the live verification results earned it.

## How would you describe your overall opinion of Meta Model API? (required)

YOUR PICK. Suggestion: Positive — with one real lesson learned: Spark is a reasoning model, and reasoning tokens count against max\_tokens, so a 256-token limit returned empty replies until the limit was raised to 1024. Documented in the repo so the next builder does not hit the same wall.

## Permission grant (use/publish/share submitted materials)

Accept — required to submit.

## How likely are you to recommend the Meta Model API to another developer or engineering team building with LLMs?

YOUR PICK. Suggestion: 9 out of 10 — would recommend for verification and judgment work behind a scrubber/budget gate; the max\_tokens reasoning lesson is the one thing to pass along with the recommendation.

## How likely are you to recommend Muse Code to another developer or engineering team?

Answer honestly: did not use it. If the question is a number scale with no "not applicable" option, pick the neutral/lowest value and write "Did not use Muse Code on this project" in the feedback field if one is offered. Do not recommend a tool you did not use.

## What was the biggest obstacle your team hit while building this project?

The reasoning-token trap. Muse Spark spent 254 of 256 max\_tokens reasoning and returned an empty message — no error, no verdict, just nothing. The live gate looked broken when the model was actually fine and the budget was the problem. Diagnosing it took a raw probe of the reply shape (finish\_reason: length, 254 reasoning tokens, content: null). Raising the limit to 1024 fixed it, and the finding is recorded in the code so it is visible to the next builder. Second obstacle: a wrong Supabase URL returned an empty HTTP 405 on the first live backup attempt — fixed by correcting the URL, and the failure is recorded honestly in the repo.

## Compared with other AI models your team has used for the same kind of work, how did Meta's models perform on this project?

Stronger than the local small models for this specific job — verification and compression need reasoning, and the local Gemma-class models on hand were too small to judge contradictions reliably. Comparable to other frontier APIs on output quality, with easier integration thanks to the OpenAI-compatible request shape. The one difference that mattered: the reasoning-token behavior above, which no other model in this workflow exhibited the same way and which cost real debugging time before it was understood.

## When your team chooses an AI model or coding tool, what matters most?

Verifiability first: can the output be checked, and can a wrong answer be caught before it lands in storage. Then cost and provider-neutrality — no lock-in, a local fallback must exist, and the tool must work without sending private data anywhere it does not need to go. Accessibility and security ship in version one, never bolted on later.

## What makes it hardest for your team to switch to a different AI model or coding tool?

Re-verification. Every model reasons differently, so prompts, token budgets, and verdict shapes tuned for one model have to be re-proven against the next — the max\_tokens lesson above is exactly the kind of thing that does not transfer. Pricing and credit structures differ too, and local-versus-cloud trade-offs change what can run on the household's own hardware.

## If your team took this project to production, what would most likely stop you from using Meta's models?

Three things, in order. First, Spark is closed-weight and cloud-only — there is no offline or self-hosted option, so a local-first product can never fully run on Meta models alone; the Llama fallback exists for that reason. Second, the free-credit terms allow content to be used for product improvement, which conflicts with a scrubber-first privacy promise for paying users. Third, billing has a spend notification but no hard cap — the $100 warning is the only threshold, so runaway spend is stopped by vigilance rather than by a limit. A hard cap and a local-weight option would remove all three blockers.
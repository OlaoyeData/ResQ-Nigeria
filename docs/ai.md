# AI assistance

`AIService` offers classify, extract location entities, summarize, identify missing details, and generate a follow-up prompt. Local implementation is deterministic keyword classification. It can emit HIGH/MEDIUM/LOW confidence bands and an urgency hint; these are not medical determinations. Location entity extraction does not resolve addresses to coordinates.

`AI_PROVIDER`, `AI_API_KEY`, and `AI_MODEL` are server-side provider settings for a future LLM adapter. No external provider was selected or credentials supplied. AI never mutates status, verifies coordinates, selects a unit, or dispatches. Operators make and audit those decisions.

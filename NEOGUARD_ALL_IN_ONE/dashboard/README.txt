NEOGUARD V16 — GROQ DIRECTED LOCAL ANIMATION

What changed:
- Groq is used as the animation director, not an image generator.
- The dashboard renders the animation locally on the Mac.
- The visual switches IMMEDIATELY on condition changes; it never waits for Groq.
- The local sensor classification is the source of truth.
- Groq can refine animation intensity/style in the background, but cannot turn a CRITICAL state into STABLE.
- The previous static PNG visual has been removed from the live scene so stale STABLE text cannot remain during a CRITICAL condition.
- The animated scene itself displays the current temperature, humidity, movement and vibration state.
- No camera is used.
- No OpenAI image credits are required.

Run:
  export GROQ_API_KEY="YOUR_KEY"
  export AI_PROVIDER="groq"
  export GROQ_MODEL="openai/gpt-oss-120b"
  python3 dashboard.py

The NORMAL / CRITICAL / RECOVERY controls are demo selectors. The actual live dashboard state can also drive the same animation automatically.

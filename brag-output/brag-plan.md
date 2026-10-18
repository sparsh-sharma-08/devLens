# Brag Plan: DevLens AI

## What is this app?
DevLens AI parses a GitHub repository into an Engineering Knowledge Graph via Tree-sitter AST, then lets developers chat with their codebase (with exact file/line citations), trace features through call graphs, visualize architecture, and get a real health report — all grounded in actual code structure, not LLM hallucinations.

## The angle
This isn't another "chunk and embed" tool. DevLens builds a real structural graph — functions, classes, imports, call chains — and every AI answer cites the exact file and line. The video should feel like watching a premium developer tool that just works: dark, confident, precise. The claim "Understand any codebase in 15 minutes" is the thesis; the chat with citations is the proof.

## Hook (first 2-3 seconds)
A tight question that every developer has felt: "50,000 lines of code. Where do you even start?" — typeset in Inter Black over the deep navy background, then a clean reveal to the DevLens answer.

## Key moments (the middle)
- The indexing pipeline ticking through stages: Cloning → Parsing → Building Knowledge Graph → Generating Embeddings — each stage appearing with a progress bar filling, showing the machine working.
- The Chat interface: a user asks "Where is authentication handled?" and the AI responds with a markdown answer plus clickable citation chips (`auth.py:42`, `models.py:132`) — this is the product's strongest visual moment.
- A quick flash of the four tabs (Chat / Architecture / Trace / Health Report) to show the breadth of what's been built.

## Outro / punchline
The tagline lands full-screen: "Understand any codebase in 15 minutes." Then the DevLens logo mark (indigo-to-cyan gradient square with the Zap icon) and name fade up. Clean. Confident.

## User flow worth showing
1. **Entry:** A GitHub URL being pasted into the import modal
2. **Key action:** The indexing pipeline stages progressing through parsing/graph/embeddings
3. **Result:** The Chat tab showing a grounded AI answer with citation chips linking to exact source lines

## Tone
- Preset: polished
- Creative direction: quiet premium developer tool reveal
- Interpretation: Fewer scenes, longer holds, generous whitespace. The confidence comes from restraint — no flashy cuts, no screaming text. Let the product's dark-mode UI and precision speak. Transitions are slow crossfades.

## Format: landscape — 1920x1080
## Duration: 20 seconds

## Visual identity (from the project)
- Background: #050912
- Accent: #6366f1 (indigo) → #06b6d4 (cyan) gradient
- Text: #f1f5f9
- Card surface: rgba(17, 24, 39, 0.8) with backdrop-filter blur
- Display font: Inter (weight 900, letter-spacing -0.04em)
- Body font: Inter (weight 400)
- Mono font: JetBrains Mono
- Strongest visual element: The glassmorphism card with indigo border glow, the gradient text treatment, and the chat interface with citation chips

## Share copy (draft)
DevLens AI parses your codebase into a knowledge graph, then answers questions with citations to the exact file and line. Understand any repo in 15 minutes.

## Audio direction
- Role: sparse professional accents
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` — steady, clean, warm business feel
- Music treatment: Start at 0s, volume 0.30, gentle fade-in over first 0.5s, subtle fade-out over last 1.5s
- Music cue guidance: Bundled preset, 109.96 BPM. Strong cues at 8.74s (for chat reveal), 13.11s (for tab breadth flash), 17.47s (for outro tagline landing). Beat grid for indexing stage sequence: 4.91s, 5.34s, 6.00s, 6.56s
- Audio-reactive treatment: subtle; use music RMS/bass to make the glassmorphism card glow breathe gently. No waveform/equalizer visuals.
- SFX posture: sparse; 2-3 polished accents only
- Audio-coupled moments: indexing stages ticking in one by one (interface drop sounds), chat response appearing (soft announcement cue), final logo landing (one clean bell)
- Restraint rule: Audio must never distract from the product. No stacking. No dense SFX. Every sound earns its place.

## Storyboard

### Scene 1 — Hook — 3s
Dark screen, #050912 background. The line "50,000 lines of code." fades up in Inter Black, white (#f1f5f9), centered. Hold 1.2s. Then below it: "Where do you even start?" in the indigo-to-cyan gradient text. Hold 1.5s.
Sequential/interaction: none
Audio intent: Quiet tension. The music bed enters softly.
Audio-coupled idea: none — let silence and the music bed build
Music: vol-12 fades in at 0.30 volume
Transition mood: soft → Scene 2

### Scene 2 — Pipeline — 5s
A recreated DevLens indexing pipeline card. Dark glassmorphism card centered on screen. Inside, pipeline stages appear one by one with progress:
1. "Cloning repository…" ✓
2. "Parsing source files…" ✓ (with a small Tree-sitter icon)
3. "Building knowledge graph…" ✓
4. "Generating embeddings…" ✓
A progress bar fills 0→100% across the bottom of the card as stages complete. The final state shows "Indexing complete!" in green (#10b981).
Sequential/interaction: yes — stages appear one by one, each with a subtle check animation. Progress bar fills smoothly.
Audio intent: Building momentum. Each stage landing is a small satisfying tick.
Audio-coupled idea: interface/drop sounds for each stage completion, snapped to beat grid at ~4.91s, 5.34s, 6.00s, 6.56s
Music: bed continues, energy building slightly
Transition mood: soft → Scene 3

### Scene 3 — Chat with Citations — 7s
The DevLens chat interface, recreated faithfully. Dark background. On the left, a user message bubble (indigo gradient): "Where is authentication handled?" Then the AI response appears in a dark card bubble with:
- A markdown-formatted answer mentioning JWT tokens, bcrypt hashing, and OAuth providers
- Below the response: citation chips in the indigo-tinted pill style: `auth.py:42` · `models.py:132` · `middleware.py:15`
The citation chips are the hero element — they glow softly, proving the answer is grounded in real code.
Sequential/interaction: yes — user message appears first, then after 0.8s the AI response types/fades in, then citation chips pop in one by one
Audio intent: The product's strongest moment. A soft announcement cue when the citations appear.
Audio-coupled idea: soft bell or announcement when citations reveal (beat-locked to ~8.74s strong cue); citation chips pop in with subtle interface sounds
Music: bed at full posture
Transition mood: soft → Scene 4

### Scene 4 — Tab Breadth — 2s
A tight shot of the DevLens tab bar: Chat · Architecture · Trace · Health Report — each tab icon glowing in its respective color (cyan, purple, green, amber) as a quick highlight sweeps across them left to right. Below, a faint glimpse of the architecture Mermaid diagram and the health score gauge (showing "87/100" in green).
Sequential/interaction: yes — tab highlights sweep left to right, ~0.4s apart
Audio intent: Quick, confident. "There's more here."
Audio-coupled idea: light interface click per tab highlight
Music: bed continues
Transition mood: soft → Scene 5

### Scene 5 — Outro/Tagline — 3s
Clean dark screen. The tagline lands in Inter Black: "Understand any codebase" on line 1, "in 15 minutes." in gradient text on line 2. Hold 1.5s. Then a subtle fade to the DevLens mark (indigo-to-cyan gradient rounded square + Zap icon) and "DevLens AI" in the logo treatment. Hold 1.2s.
Sequential/interaction: none
Audio intent: Confident landing. Music fades gently.
Audio-coupled idea: one clean impactBell_heavy for the tagline landing (beat-locked to ~17.47s strong cue)
Music: vol-12 begins gentle fade-out
Transition mood: end

**Music mood for this video:** polished, steady, warm
**Audio summary:** A clean, steady music bed enters softly and holds through the middle scenes, with sparse interface drops for the indexing pipeline, a soft bell for the citation reveal, and a single clean impact for the final tagline — then fades out under the logo.

# Hyperframes Composition Brief: DevLens AI

## Objective
Create a short, polished launch-style brag video for DevLens AI — a developer tool that parses codebases into knowledge graphs and answers questions with exact citations.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 20 seconds

## Source Material
- Project root: `/Users/sparsh/Documents/Coding/DevLens`
- Primary files read: `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/repos/[id]/page.tsx`, `frontend/src/app/repos/[id]/tabs/ChatTab.tsx`, `01-Project-Charter-and-Vision.md`, `CURRENT_STATUS_DEEP_DIVE.md`
- Product name: DevLens AI
- Tagline / strongest claim: "Understand any codebase in 15 minutes."
- Key UI or visual moment to recreate: The Chat interface with AI response bubble and citation chips (`auth.py:42`, `models.py:132`), and the indexing pipeline progress card
- Copy that must appear verbatim:
  - "50,000 lines of code."
  - "Where do you even start?"
  - "Understand any codebase in 15 minutes."
  - "DevLens AI"
  - "Where is authentication handled?" (chat user message)
  - Citation chips: `auth.py:42` · `models.py:132` · `middleware.py:15`

## Creative Direction
- Tone preset: polished
- Creative direction: quiet premium developer tool reveal
- Interpretation: Fewer scenes, longer holds, generous whitespace. Confidence through restraint — no flashy cuts, no screaming text. Slow crossfades. Let the dark-mode UI's precision speak for itself.
- Angle: This isn't another "chunk and embed" tool. DevLens builds a real structural graph and every AI answer cites the exact file and line. The video should feel like watching a premium developer tool that just works.
- Hook: "50,000 lines of code. Where do you even start?" — typeset in Inter Black over deep navy
- Outro / punchline: "Understand any codebase in 15 minutes." → DevLens AI logo mark
- Avoid:
  - Generic SaaS language ("streamline your workflow", "supercharge", "revolutionize")
  - Abstract filler visuals, particles, or generic motion graphics
  - Unrelated visual redesign — match the project's actual dark-mode palette

## Visual Identity
- Background: #050912
- Text: #f1f5f9
- Accent primary: #6366f1 (indigo-500)
- Accent secondary: #06b6d4 (cyan-500)
- Gradient: linear-gradient(135deg, #818cf8, #06b6d4) for highlight text
- Card surface: rgba(17, 24, 39, 0.8) with backdrop-filter blur(12px) and 1px border rgba(99, 102, 241, 0.15)
- Card hover glow: 0 0 40px rgba(99, 102, 241, 0.15)
- Success color: #10b981 (for "Indexing complete!")
- Display font: Inter (weight 900, letter-spacing -0.04em)
- Body font: Inter (weight 400)
- Mono font: JetBrains Mono (for citation chips and code)
- Button gradient: linear-gradient(135deg, #6366f1, #4f46e5)
- Visual references from the project: glassmorphism cards with indigo border glow, gradient text treatment, chat bubbles with avatar circles, citation chip pills, progress bar with indigo-to-cyan gradient fill

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 3s — "50,000 lines of code." then "Where do you even start?" in gradient text. Dark, centered, Inter Black.
2. Pipeline — 5s — Glassmorphism card with 4 indexing stages appearing one by one with checkmarks and progress bar filling to 100%. "Indexing complete!" in green.
3. Chat with Citations — 7s — Recreated chat interface. User asks "Where is authentication handled?", AI responds with markdown answer, citation chips (`auth.py:42` · `models.py:132` · `middleware.py:15`) pop in below. Citations are the hero.
4. Tab Breadth — 2s — Tab bar with Chat/Architecture/Trace/Health Report highlights sweeping left to right. Faint glimpse of architecture graph and health score "87/100".
5. Outro/Tagline — 3s — "Understand any codebase in 15 minutes." in gradient text. DevLens AI logo mark fades up.

## Audio
- Audio role: sparse professional accents
- Audio arc: Quiet opening → building momentum during pipeline → confident hold during chat → quick energy for tabs → gentle fade on outro
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: volume 0.30, gentle fade-in over first 0.5s, subtle fade-out over last 1.5s. Let it sit comfortably under the visuals.
- Music cue guidance: Bundled preset at `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json` (109.96 BPM). Strong cue targets: ~8.74s for citation reveal, ~17.47s for outro tagline landing. Beat-grid window for indexing stages: 4.91s, 5.34s, 6.00s, 6.56s.
- Audio-reactive treatment: subtle; use music RMS/bass to make the glassmorphism card border glow and citation chip presence breathe gently. No waveform/equalizer visuals.
- Audio-coupled moments:
  - Scene 2 / pipeline stages — interface/drop sounds for each stage completion, beat-grid snapped
  - Scene 3 / citation reveal — soft bell/announcement when citation chips appear, beat-locked to ~8.74s
  - Scene 5 / tagline landing — single clean impactBell_heavy, beat-locked to ~17.47s
- SFX selection guidance: Use polished, low high-frequency-risk sounds. interface/drop for subtle stage completions. impactBell_heavy_000 for the final landing. Keep it sparse — 2-3 cues maximum aside from the pipeline beats.
- SFX analysis guidance: `assets/sfx/sfx-analysis.md` — prefer low HF risk for polished moments
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copy the music into `brag-output/composition/assets/music/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project.
- Keep all text readable in the final render.
- Keep the video within 15-25 seconds.
- Include the planned music/SFX layer unless audio was explicitly disabled or documented as intentionally silent.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints. Hyperframes decides exact animation timing and should ignore cues that hurt readability, scene pacing, or the product story.
- Major reveals may move toward nearby strong cues within about 0.15s. Smaller entrances may align to nearby beat points within about 0.10s. Use only 1-3 strong cue locks in a 15-25s video unless the edit clearly benefits from more.
- Use SFX to support motion and interaction: card sounds for card-like reveals, short announcement cues for major payoffs, key/click sounds for text or user actions, and restraint when the edit is already busy.
- Honor planned music treatment such as fade-outs, ducking, beat-aligned reveals, or letting a final SFX ring over the music, using the best Hyperframes-supported implementation.
- When music is present and the treatment is not `none`, consider Hyperframes audio-reactive workflow: extract audio data and use RMS/frequency bands for subtle, brand-specific motion. Good targets are glow, depth, background warmth, card presence, title emphasis, or other existing visual elements. Avoid waveform/equalizer visuals, musical-note graphics, generic particle systems, strobing, or heavy pulsing.
- Use local assets for audio and any required runtime/media dependencies when possible.
- Run `hyperframes check` before render — it is brag's single gate.

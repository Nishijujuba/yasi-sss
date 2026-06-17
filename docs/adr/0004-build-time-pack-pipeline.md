# Use A Build-Time Practice Pack Pipeline

Cambridge source PDFs, WMA audio, answer keys, and audioscripts will be processed before the React application runs. The build pipeline will emit verified question-page images, overlay coordinates, accepted answers with provenance, transcript data, and browser-ready MP3 assets; the static React application will consume only these released artifacts.

## Considered Options

- Browser runtime PDF processing: reduces preprocessing, increases browser variability and coordinate-detection risk.
- Single embedded HTML file: easy to carry, difficult to maintain as transcripts and intensive listening features grow.
- Build-time practice pack pipeline: keeps extraction and verification outside the user-facing practice session and makes marking reproducible.

## Consequences

Source processing and release validation become explicit project commands. A practice pack cannot enter the application until its release gate passes.

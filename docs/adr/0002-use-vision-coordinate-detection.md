# Use Vision Coordinate Detection For Overlays

The practice pack will use deterministic image analysis to propose blank and choice coordinates, followed by a separate vision subagent that validates each proposal against the rendered page and question order. The user explicitly rejected manual coordinate annotation as the primary path, so coordinates enter the exam simulation only when both stages agree and the combined confidence reaches the release threshold.

## Considered Options

- Manual coordinate annotation: precise when carefully checked, too labor-intensive for scaling across Cambridge books.
- Pure PDF text extraction: unreliable for this source because extracted text is visibly corrupted.
- Vision coordinate detection: better fit for preserving PDF layout while automating answer-field placement.

## Consequences

The coordinate pipeline must produce machine-readable overlay data, confidence values, and review images. Detections below `0.85` confidence, or disagreements between image analysis and vision validation, should fail closed and stay out of the exam simulation until the detection logic is repaired, because a misplaced overlay breaks answer entry even when the question content is correct.

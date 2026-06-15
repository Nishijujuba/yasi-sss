# Use Hybrid Question Rendering

The practice pack will render original PDF listening question pages as a question facsimile layer and place an interaction overlay on top for blanks, choices, focus order, and feedback. This preserves the book layout even when PDF text extraction is unreliable, while keeping answer keys, audioscripts, and scoring rules in structured data for later exam practice, shadowing, and intensive listening generation.

## Considered Options

- Full PDF-to-HTML conversion: attractive for semantic markup, weak for this source because text extraction is visibly corrupted.
- Manual HTML retyping: accurate when carefully edited, too slow and fragile for a whole Cambridge book.
- Image-only pages: visually faithful, insufficient for keyboard input, choice selection, and scoring.

## Consequences

The first implementation needs coordinate mapping for answer fields and choice regions. Later features can reuse the structured data without depending on PDF extraction at runtime.

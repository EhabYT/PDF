# OmniFix Engine

One processing mode: **OMNIFIX**. Independent deterministic computer vision; no proprietary CamScanner code, no generative AI, no alternate user-selectable filters.

## Pipeline
1. **Read & orient:** Pillow decodes the source, applies EXIF orientation for the working reference, converts to RGB. Original bytes are never changed.
2. **Analyze:** brightness, contrast, shadow fraction and border/background uniformity are measured on a downscaled copy.
3. **Detect:** Gaussian blur → adaptive Canny → morphological close → contours → convex quadrilateral / high-rectangularity fallback. Candidates are scored by rectangularity, edge gradient support and area. Confidence < 0.62 preserves the full frame.
4. **Correct perspective:** ordered corners, small outward safe margin clipped to image bounds, target size from edge lengths, uniform downscale only if the configured output pixel cap would be exceeded. Manual corners are honored after validation.
5. **Normalize illumination:** LAB L-channel background estimated by downscaled Gaussian blur; bounded gain normalizes shadows without forcing white. Color channels are preserved.
6. **Enhance:** mild CLAHE blend, gentle global contrast, highlight roll-off (not pure-white clipping), tightly bounded neutral-paper white balance, conditional mild bilateral denoising, mild unsharp masking.
7. **Output:** high-quality JPEG (quality 95 default, 4:4:4, 300 DPI metadata), thumbnail, processing metadata and checksums.

## Preservation safeguards
- Uploaded source stored read-only with SHA-256.
- Source checksum verified before and after processing.
- Processed output written to a new path; originals never overwritten.
- No thresholding-to-binary, object removal, inpainting, text replacement or generative reconstruction.
- Faint marks, colored stamps and signatures are protected by conservative intensity and color-preserving operations.
- Pixel-level output preservation is not guaranteed after enhancement/geometry; source preservation is.

## Settings
Intensity (0–1), automatic detection, automatic perspective, shadow correction, output pixel cap and PDF import DPI scale the same pipeline. Disabling detection preserves full frames; disabling perspective skips automatic warp. Manual correction remains available.

## Determinism & tests
Identical input/settings produce identical output bytes in the pinned environment. Tests cover synthetic normal/tilted/shadow/uneven/faint/stamp/signature/table cases, original integrity, dimensions, determinism and visual baselines.

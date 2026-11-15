# Foam comparison viewer

From the project's `scripts` directory:

```powershell
python viewer.py export
python viewer.py serve
```

Open http://localhost:8000 in a browser. Keep the terminal open; Ctrl+C stops the server.

Export uses the existing frozen `data/processed/displacement/marked_foam_train/parameters.json` and test annotations/observations for `marked_foam_test`. It does not fit or change the model. It recomputes predictions and metrics, including an instantaneous-recovery baseline on identical input/observation masks. The default explicitly permits book-input reconstruction across gaps of up to eight frames, matching the evaluation already used. Override with `--max-book-gap` if needed.

The exporter copies the original test video to `viewer/dist/video.mp4` and writes portable JSON. Outputs stay outside `scripts`. No video rendering or tracking is required. Existing simulation MP4s are not used by the viewer.

Select a test press, play or scrub, toggle measured/predicted marker overlays, and drag the 3D proxy to rotate. Double-click resets the orientation. The plot shows vertical marker RMSE per frame, with gaps for missing observations. The downloads expose the frozen parameters, per-press metrics and predictions/provenance.

The displayed proxy is precomputed with the Python model, not a second JavaScript physics implementation. Browser controls replay a frozen test; they do not refit or alter the material. Default playback matches the exported 30 fps slow-motion video; capture time uses 120 fps. Browser support for the original MP4 codec is required.

`viewer/dist` is a standalone static website after export. Host that directory with a static hosting provider to produce the submission link. Localhost is only accessible on your computer. The video may be large; check the provider's per-file limit before uploading. No external scripts, fonts or runtime packages are required.

## Model and interpretation

The book underside is a prescribed unilateral displacement boundary. The state relaxes to 35 mm at an exponential rate when unconstrained, while respecting the book ceiling. Uniform vertical strain maps the state to material-marker predictions. Only the effective time constant is fitted; force, stiffness and damping are not separately identified.

The instantaneous baseline uses `h=min(35,book_height)` with the same calibration, repaired input and valid marker samples. Always-resting baseline results are retained in the JSON for reference, but are weaker comparisons. Recovery-only scores retain the existing observation-based selection rule, documented in the exported data. No metric window is changed in response to test scores.

The page exposes weak parameter identification and input repairs. Deep compression, nonuniform deformation, dot tracking errors, unknown timing and fixed-width assumptions remain limitations. A dimensioned box is used rather than reconstructed geometry.

Gaussian Splatting informs the conceptual observation/projection fitting loop; Gaussian rendering is not implemented. Hybrid Particle–Voxel informs action-conditioned state evolution; its learned architecture is not implemented. The implementation uses Python, NumPy, SciPy, OpenCV, and browser Canvas/HTML/CSS/JavaScript, with coding assistance from OpenAI Codex.

The main [project README](../README.md) provides the full interpretation and results. The direct motion graph lets you select any initialized dot and compares measured and predicted displacement from its resting reference. New exports supply the pixel scale so this graph uses millimetres; older exports fall back to explicitly labeled pixels. Re-export to update the graph units.

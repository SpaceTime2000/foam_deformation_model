# Learning a foam block's response from video

This project models a foam block being compressed by a book and recovering after the book lifts. The block measures 190 × 75 × 35 mm at rest. A simple 3D box represents its shape; a single fitted recovery time controls how quickly its height returns to normal when it is no longer constrained by the book.

The input is the book's measured motion. The output is the predicted foam height and the corresponding movement of material points. Ink dots on the foam provide observations against which those predictions can be fitted and checked. This is a small, displacement-controlled deformation model, not a reconstruction or a general material simulator.

The fitted recovery time is **61.6 ms**. On three presses in a separate recording, vertical marker errors are approximately **2.01, 2.12 and 1.97 mm**. A baseline that follows the book and recovers instantly achieves almost the same errors over the complete interactions. The fitted model does better on the short recovery portions, but the evidence for a precise recovery parameter is weak. These qualifications are central to interpreting the result.

## View the result

**Interactive viewer:** [Open the real-video and model comparison](https://spacetime2000.github.io/foam_deformation_model/).

**Source code and saved model:** [GitHub repository](https://github.com/SpaceTime2000/foam_deformation_model).

**Input footage:** [Download the original recordings from Google Drive](https://drive.google.com/drive/folders/1eDp1PoQyIxnEdt35SP5SI9YXnNkyjfJ6?usp=sharing). For rerunning the pipeline, place `marked_foam_train.mp4` in `data/train/` and `marked_foam_test.mp4` in `data/test/`. The viewer retains its own test-video playback copy at `viewer/dist/video.mp4`; the Drive folder is the download source, not the webpage's streaming URL.

The interactive page shows the real test recording beside a rotatable 3D proxy. Green circles mark tracked dots and orange crosses show predicted positions. Playback, the 3D response and the graphs share the same timeline. A separate graph compares measured and predicted displacement for any initialized dot; another shows prediction error throughout the press. Parameters, metrics and the exported predictions can be downloaded from the page.

An additional **Exploratory mean displacement** chart lets the viewer select a fixed group of dots. Both means use exactly those dots, each measured from its own resting reference. The observed mean is omitted whenever any selected dot is unavailable under the existing scoring mask; the predicted mean remains visible. Dot availability, selected IDs and complete-group frame coverage are displayed. No dots are selected by default, and the selection resets between presses. This is an inspection aid, not a new evaluation score: choosing favorable dots after seeing the test cannot establish improved accuracy. The original metrics are unchanged.

To view the existing exported result locally, open a terminal at the project root and run:

```powershell
python -m pip install -r scripts/requirements.txt
cd scripts
python viewer.py serve
```

Open **http://localhost:8000** and leave the terminal running. Select a press, click Play, or drag the timeline to inspect individual frames. Drag the 3D box to rotate it; double-click to reset its orientation. Ctrl+C stops the server. The existing export is needed at `viewer/dist/results.json`, with its video and page assets alongside it.

If the export is missing or needs rebuilding from the saved observations, run this before serving:

```powershell
python viewer.py export --max-book-gap 8
```

Export reads the frozen training parameters and test observations. It computes predictions and baseline scores, copies the original test video into `viewer/dist`, and does **not** fit or change the model. The browser displays these precomputed Python predictions; it does not run a separate physics implementation or learn from playback.

The local address works only on the computer serving it. Use the hosted viewer and repository links above in the submission email, after checking that the deployed page and footage downloads work while signed out.

## Why use the book's movement as the input?

The video shows displacement, but it does not measure the force applied by the hand. Treating that unknown force as if it were measured would introduce an unsupported assumption. Instead, the book's underside acts as a moving boundary: the foam cannot extend above it while they are in contact.

This separates the problem into two parts. During compression, the prescribed boundary strongly determines the height. After separation, the model's own recovery rule determines the motion. Contact is decided during simulation, rather than by manually switching to a different equation at a selected release frame.

There is a tradeoff. Prescribing displacement avoids inventing a loading force and makes new presses easy to evaluate from their book trajectories. It also means good agreement during pressing is limited evidence about the learned material behavior: even an instantaneous-recovery baseline can follow the same boundary. That is why the baseline comparison matters.

The geometry is deliberately simple. The assignment permits a rough proxy, and a single camera view does not constrain a detailed 3D reconstruction. Keeping the representation small makes its parameters and failure modes easier to understand. A box, however, cannot represent localized deformation or lateral bulging just because it can be rotated on screen.

## From the recording to observations

The reported capture setting is 1080p at 120 fps. Exported playback is approximately 30 fps, producing slow motion. All physical times assume that each exported frame corresponds to one uniformly spaced captured frame. The file's playback rate alone does not verify that assumption; dropped or duplicated frames would change the estimated recovery time.

Setup selects a resting reference, the projected foam top and table, material dots, the book underside, and complete press intervals. The known 35 mm resting height sets the approximate image scale. Dots span different positions and vertical rows on the visible face, including the interior of that face; they do not have to lie on the top and bottom edges.

Material dots were used because a changing foam silhouette can be confused with the book's edge or a shadow. Dot tracking combines optical flow with nearby dark-blob support and consistency checks. A resting dot constellation is initialized separately for each press to accommodate small changes in pose between presses. If enough of the resting constellation becomes recognizable again, lost tracks may be reacquired. This remains a heuristic tracker: an accepted track can still have the wrong identity.

The book detector uses the maroon cover as a search cue, then refines the underside edge. Manually marked underside points calibrate the offset between that cue and the actual boundary. This detector is specific to the recording's book and lighting. It is not intended as a general book tracker.

Missing dot observations remain missing. Scoring requires at least four initialized, visible dots in a frame, and only those valid observations enter the loss. A dot missing at a press's initial reference is excluded from that press's fitting objective even if it is found later. Reported coverage describes availability under these rules, not an independent accuracy check.

Unknown book input is rejected unless a maximum reconstruction gap is explicitly permitted. The reported fit and test use an eight-frame limit. Bounded finite observations are interpolated. A lifting book that exits the image can be extrapolated using its preceding upward motion, subject to consistency checks; absent-book observations on both sides can indicate an unconstrained interval. Foam measurements are not used to fill book motion. These are offline input estimates, sometimes using later input observations, not guaranteed online predictions.

The test export reconstructs five missing book-input frames in press 1 (634–638) and five in press 2 (1304–1308); press 3 needs none. Their locations are recorded and flagged in the viewer. Eight capture samples correspond to about 67 ms, comparable to the fitted 61.6 ms recovery time. Uncertainty near release therefore matters substantially.

## The model, in plain terms

Let `H` be the resting height, `h` the current height and `p` the prescribed book height above the table. The simulation starts each selected interval at rest. Without the book, the remaining compression decays exponentially:

```text
compression = H - h
d(compression)/dt = -compression / tau
```

Over a small time step this gives an exact free-recovery update. The book then limits how tall the block can become:

```text
h_free = H - (H - h) * exp(-dt / tau)
h_next = min(h_free, p)
```

The book position is interpolated over eight substeps per captured-frame interval. A slowly lifting book can stay in contact; a rapidly lifting book can leave the foam behind. There is no inertia or explicit force calculation. This is a quasistatic approximation with one memory variable, height.

To compare that height with the video, each reference dot is scaled vertically about the table:

```text
y_predicted = table_y + (y_reference - table_y) * h/H
x_predicted = x_reference
```

This assumes uniform vertical strain and fixed length and width. It is a strong simplification, especially under deep compression. A separate marker-derived height diagnostic estimates a common scale from the observed dots, but it is a model-dependent proxy, not a direct measurement of the foam's top surface. The primary comparison uses dot coordinates themselves.

## What is fitted, and can it tell us stiffness and damping?

Only `tau`, the effective recovery time, is fitted. Known dimensions, capture rate, geometric calibration and the measured book trajectory are supplied rather than learned. SciPy searches for the value of `tau` that minimizes the average vertical marker mean-squared error, with each training press receiving equal weight. The search is bounded between one capture-frame interval and two seconds.

The exponential can be motivated by a simple parallel spring–damper interpretation. If compression is `q`, an effective stiffness is `k`, and a viscous damping coefficient is `b`, unloaded quasistatic force balance gives:

```text
k*q + b*dq/dt = 0
tau = b/k
```

This explains the recovery equation; it does not establish that the foam is a linear spring–damper over the full compression range. Here `k` would have units N/m and `b` N·s/m. Multiplying both by the same positive factor leaves the recovery motion unchanged. The prescribed book displacement supplies no missing force scale. Consequently **the current data and model do not identify separate stiffness and damping**, and the saved model does not report them.

An independently known load could help establish an effective stiffness: under an appropriate settled, approximately linear compression test, `k ≈ force / compression`. A measured recovery time could then give `b ≈ k*tau` under the same approximation. Hand pressure in the present video is not a known load, and knowing the book's mass would not recover that unknown extra force. Multiple known loads and rates would be needed to assess nonlinear foam behavior. This experiment does not provide that characterization.

The assignment names stiffness and damping as examples of fitted behavior. This project instead fits an effective recovery time and states its limitations. It meets that interpretation of behavior fitting, but does not claim a full constitutive material model.

## Training and the fresh interaction

Presses 1–4 of `marked_foam_train.mp4` fit one shared recovery time. Press 5 is a within-recording validation press and is excluded from fitting. A separate recording, `marked_foam_test.mp4`, contains three test presses. Their book trajectories are supplied to the already fitted model; no test recovery parameter is optimized.

Each test interval still needs geometric calibration and a resting marker reference. Those are observations of the initial setup, not fitted recovery dynamics. Subsequent foam dots are used to evaluate predictions, never to reset the simulated height. Supplying the test book trajectory is intentional: the task demonstrated is response to a measured interaction, not prediction of the hand's future actions.

The test is held out from parameter optimization, but it is not a blind benchmark. Tracking previews and software handling were inspected during development. Its three presses use the same object and broadly similar interaction. The results do not establish transfer to a different object, loading direction or capture setup.

## What the results show

All numbers below are vertical material-marker RMSE in millimetres. RMSE is the square root of the mean squared prediction error: lower is better. The model and baseline are scored on identical observations. These are image-derived, geometrically scaled errors, not independently measured 3D surface errors.

The baseline uses `h = min(H, p)`. It compresses with the book and returns instantly when unconstrained. This is a more informative comparison than an object that stays at rest throughout the press.

| Separate test press | Model, full interval | Instant baseline, full interval | Model, recovery only | Instant baseline, recovery only | Recovery frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2.010 | 2.016 | 0.836 | 1.245 | 10 |
| 2 | 2.124 | 2.134 | 0.711 | 0.942 | 25 |
| 3 | 1.968 | 1.971 | 0.579 | 0.655 | 28 |

The fitted model reduces full-interval error by less than 0.5% in every press. Most of each interaction is governed by the shared book boundary, so the similar overall numbers are unsurprising. The recovery differences favor a finite recovery time, but their small windows, estimated input and tracking uncertainty prevent a strong accuracy claim.

Recovery-only frames are selected by the existing observation-based rule: the book is more than 1 mm above the marker-height proxy, and that proxy remains at least 0.3 mm below rest. This rule does not use the model's predicted contact state, but it still depends on the uniform-strain proxy. It is not an independent contact sensor. Full-interval errors remain the primary metric.

All three test presses have 100% frame coverage under the four-dot rule. Training coverage is less complete: approximately 100%, 100%, 79% and 38%, with 36% on the validation press. Validation error is 2.199 mm on its available observations. Missing observations during strong compression can bias what gets evaluated. Coverage is not the percentage of correctly tracked dots.

Parameter stability is another limitation. Leaving out one training press gives fitted recovery times of about 55.5, 59.9, 56.8 and 717.3 ms. Halving or doubling the selected recovery time changes training loss by less than 5%. These diagnostics indicate weak identification; they are not confidence intervals. The model's numerical integration is much more stable: increasing substeps from eight to sixteen changes predicted height by at most about 0.000087 mm. Numerical consistency does not resolve the measurement or modeling errors.

The model does provide a consistent, input-driven compression/recovery response and a reproducible comparison against observed material motion. Its main shortcomings are systematic pressing errors, a restrictive deformation shape and uncertain recovery timing. Apparent base motion and marker-height disagreement also suggest that tracking, pose and uniform-strain assumptions do not all hold exactly. Their contributions cannot be separated from these recordings alone.

## Reproduce the pipeline

The final implementation is `scripts/displacement.py`, supported by `displacement_model.py`, `displacement_tracking.py`, `displacement_setup.py` and `viewer.py`. Older `run.py` and edge-tracking files are exploratory work and are not the source of the results above.

Python with NumPy, SciPy, OpenCV, Matplotlib and Pillow is required. Interactive setup additionally uses Tkinter and needs a desktop display. The browser viewer uses HTML, CSS and Canvas without external JavaScript packages. The original MP4 codec must be supported by the browser. Dependency versions are not currently pinned, so identical numerical output across library versions is not guaranteed.

The intended layout is:

```text
data/train/marked_foam_train.mp4
data/test/marked_foam_test.mp4
data/annotations/marked_foam_train.json
data/annotations/marked_foam_test.json
data/processed/displacement/marked_foam_train/
data/processed/displacement/marked_foam_test/
scripts/                     # Python code and requirements
visualizations/displacement/ # Generated plots and demo videos
viewer/dist/                 # Webpage, exported results and test video
```

For a complete rerun, use the commands below from `scripts`. Setup is manual: choose the resting reference and scale, dots, actual book underside, and non-overlapping complete intervals that begin before loading and end after recovery. Assign training and validation roles for the training recording, and test roles for the separate recording. Inspect tracking across compression and release before accepting a fit.

```powershell
python displacement.py setup --video "../data/train/marked_foam_train.mp4" --fps 120
python displacement.py track
python displacement.py preview --tracking-only --trial 1
python displacement.py fit --max-book-gap 8
python displacement.py preview --trial 1

python displacement.py setup --video "../data/test/marked_foam_test.mp4" --fps 120
python displacement.py track --config "../data/annotations/marked_foam_test.json"
python displacement.py preview --config "../data/annotations/marked_foam_test.json" --tracking-only --trial 1
python displacement.py evaluate --config "../data/annotations/marked_foam_test.json" --model "../data/processed/displacement/marked_foam_train/parameters.json" --max-book-gap 8
python displacement.py preview --config "../data/annotations/marked_foam_test.json" --model "../data/processed/displacement/marked_foam_train/parameters.json" --trial 1
python viewer.py export --max-book-gap 8
python viewer.py serve
```

Repeat tracking review and optional demo rendering with the other trial numbers. Full reruns can change saved outputs; viewing the existing export does not. Manually choosing different annotations can change the fit.

There is a portability limitation in the saved annotations: they record an absolute video path, file size and modification time. Tracking caches and the fitted model also record hashes. Moving the project or changing an annotation can therefore invalidate the saved processing. On another computer, the exported viewer is the simplest way to inspect the exact reported predictions. To rerun processing, point setup at the local footage, review and save its configuration, then track and fit again. If an existing configuration prevents setup from opening because its video path belongs to another machine, preserve that JSON as a backup outside its expected filename before making a new setup. Do not bypass the consistency checks or represent a new run as the unchanged saved fit.

`parameters.json` under the training processed directory contains the fitted value and diagnostics. `observations.npz` contains tracking measurements; metadata records their setup. The viewer's `metrics.json` includes the stronger instantaneous baseline, which older saved metric files may not contain. `results.json` includes the model, test observations, predictions, missing-input flags and provenance hashes. The original footage is needed for retracking; the exported test video supports viewing only.

## Relationship to the supplied papers and credits

Neither paper is reproduced, and neither is the source of the spring–damper equation. Kerbl et al., *3D Gaussian Splatting for Real-Time Radiance Field Rendering* (2023), fits a scene representation through image observations and emphasizes efficient rendering. The connection here is only the broad idea of comparing projected predictions with observations. There are no 3D Gaussians, spherical harmonics or Gaussian rasterizer in this project.

Wang et al., *Hybrid Particle-Voxel Dynamics for Multimodal 3D World Simulation* (2026), separates a 3D representation from action-conditioned state evolution. That is conceptually related to separating the foam state from book input. This project does not use its particle–voxel representation, learned latent dynamics, multimodal predictions or training code. A small state model was chosen because one object and a few single-view presses do not support claims comparable to that work.

The spring–damper interpretation is standard viscoelastic modeling; see the [COMSOL linear viscoelasticity reference](https://doc.comsol.com/6.3/doc/com.comsol.help.sme/sme_ug_theory.06.029.html), particularly its Kelvin–Voigt description. The unilateral boundary rule and marker observation model are choices of this implementation, not a validated constitutive law for this foam.

The applicant supplied the object, measurements, videos and manual annotations, and reviewed tracking visually. Code and explanatory material were developed with substantial assistance from OpenAI Codex. Numerical optimization uses SciPy, array processing uses NumPy, video and tracking operations use OpenCV, plots use Matplotlib, and the setup interface uses Tkinter and Pillow. The viewer uses browser Canvas and a Python HTTP server. The implementation does not import a supplied paper's simulator or pretrained dynamics model.

## Submission status

The public repository contains the final code, fitted model, annotations, processed observations and exported viewer. GitHub Pages is configured to serve the result at the viewer address above. Before submitting, check the hosted video playback and controls, and verify that both original recordings in the linked Drive folder are downloadable while signed out. This README does not establish that those access checks have passed or that the submission email has been sent.

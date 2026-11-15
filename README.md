# Learning a foam block's response from video

[Interactive result](https://spacetime2000.github.io/foam_deformation_model/) · [Code and saved model](https://github.com/SpaceTime2000/foam_deformation_model) · [Download the original videos](https://drive.google.com/drive/folders/1eDp1PoQyIxnEdt35SP5SI9YXnNkyjfJ6?usp=sharing)

I used a foam block, a book and a side-view recording to build a simple model of compression and recovery. The block measures **190 × 75 × 35 mm** at rest. In the simulation, its height changes while its length and width stay fixed. Ink dots on the visible face give me points whose movement I can compare with the model.

The main choice was to use the book's movement as the input. I can measure where the book is in the image, but I do not know how hard the hand is pushing. The model therefore follows a moving boundary during compression and recovers toward its original height when that boundary lifts away. I fit one parameter from the dot trajectories: the time scale of that recovery.

The saved fit is **61.6 ms**. On three presses in a separate recording, the model's vertical dot-position errors are approximately **2.01, 2.12 and 1.97 mm**. Those numbers need a comparison: a simpler model that follows the book and recovers instantly gets almost the same full-clip errors. Adding a recovery time helps on the short recovery portions, but the recordings do not pin down that time very well. The results below include that comparison and the tracking gaps that affect it.

## Seeing the result

The [viewer](https://spacetime2000.github.io/foam_deformation_model/) puts the real recording beside a rotatable 3D box. Green circles show tracked dots; orange crosses show where the model predicts those dots should be. The video, box and plots follow the same timeline. You can choose a test press, play or drag the timeline, and rotate the box by dragging it. Double-click resets the viewing angle.

There are three ways to inspect the comparison:

- The error plot shows vertical marker RMSE throughout the interaction, for both the fitted model and the instant-recovery baseline.
- The individual-dot plot shows measured and predicted displacement from that dot's resting position. This makes it easier to see where a particular track disappears or where the uniform-compression assumption fails.
- The **Exploratory mean displacement** plot lets you choose a fixed group of dots. Both curves use exactly that group, with each dot measured from its own resting reference. If any selected observation is missing, the observed mean is left blank. The predicted mean remains visible through the gap.

The mean plot starts with no selection and resets when you change press. It shows the selected IDs, each dot's availability and the number of frames containing the whole group. Choosing dots here does not change the model or the reported metrics. It is useful for inspection, but selecting dots because they agree with the model cannot demonstrate better accuracy. Averaging can also hide differences between dots, so the individual plots and video remain useful.

The viewer provides downloads of the parameters, test metrics and exported observations/predictions. It plays predictions computed by the Python model; it does not refit anything in the browser. Its playback video is included at `viewer/dist/video.mp4`. The Drive folder provides the original recordings for download rather than supplying the webpage's streaming URL.

## What I marked, and why

This part of the work is manual. The selections establish the geometry, the points to follow and the portions of video to process. They do not specify the desired recovery curve.

### A resting frame and a height scale

I first choose a sharp frame showing the foam at rest. This supplies the reference positions of the dots and the resting geometry. The saved setups use **frame 0** in both recordings.

On that frame, I mark the foam's upper edge and the place where its bottom meets the table, at roughly the same central horizontal position. Their pixel separation represents the measured **35 mm** resting height. For example, if the resting block spans 280 pixels vertically, the scale is about 8 pixels per millimetre. The actual saved calibration is used in the code; this is just an illustration of what the two clicks establish.

Those lines are calibration marks on a particular frame. They are not fixed pixel positions that the foam must keep later, and they are not a manually traced outline for every frame. The final pipeline follows material dots during deformation. The resting reference is matched again at each press start, allowing a small image translation and scale adjustment between presses. That adjustment also updates the projected table position and pixel scale for that press.

This depends on a genuinely resting start and a reasonably consistent view. A bad reference, camera movement, perspective effects or matching the wrong dots can all give a misleading scale. I have not independently calibrated a full 3D camera model.

### Dots on the foam

I select distinct ink dots spread horizontally and across several vertical rows on the visible face. Their different heights matter: uniform compression predicts different displacements for dots at different distances from the table. A group all on one horizontal line would give much less information about that deformation pattern.

Dots can be anywhere on the visible face; they do not have to mark the upper and lower boundaries. What matters is that each selected dot can be recognized as the same material point later. On saving setup, clicks snap to nearby detected ink blobs. The saved training setup has **9 dots** and the separate test setup has **18**. The test does not need the same painted-dot IDs as training, since each recording supplies its own resting reference and both use the same fitted height-response rule.

I moved to material dots because foam borders were difficult to separate reliably from the book edge, changing shadows and the compressed shape. Dots give local observations within the face, although they introduce their own problems when they blur, become covered or get too close together.

Tracking uses optical flow between adjacent frames, nearby dark-blob support and forward/backward consistency checks. A resting-pattern match can recover tracks once enough of the dot arrangement becomes recognizable again. Lost observations remain missing rather than being filled with simulated dot positions. These checks help, but they cannot guarantee that an accepted track has kept the correct identity.

### The book's underside

I choose a sharp frame with the book visible and mark two points along its **actual underside**, spanning the central foam region. The saved book-reference frames are **323** in training and **190** in testing. These can be different from the resting-reference frame.

The underside matters because it is the physical boundary touching the foam. A convenient line on the book cover might move similarly, but it would have the wrong height unless its offset were calibrated. The detector first uses the maroon cover to locate a search region, then refines the underside brightness edge. The manually selected points calibrate its offset. Their horizontal span also sets the region used to estimate the book input.

The detector measures a line and its tilt, but the reduced simulation uses one representative book height and assumes a horizontal plate. Tilt is therefore a diagnostic of an approximation, not an extra deformation mode. This color-and-edge detector is specific to the book and lighting in these recordings.

### Complete press intervals

For each press, I select a start frame **before loading, with the foam at rest**, and an end after the foam appears settled. Starting at first contact or at maximum compression would remove the known resting initial condition. Including the approach, compression, lift and recovery lets the model run continuously through the interaction.

The saved intervals are listed below. Frame numbers are zero-based, and both endpoints are included.

| Recording | Press | Start | End | Use |
| --- | ---: | ---: | ---: | --- |
| Training | 1 | 157 | 635 | Fit |
| Training | 2 | 835 | 1345 | Fit |
| Training | 3 | 1576 | 2146 | Fit |
| Training | 4 | 2347 | 2595 | Fit |
| Training | 5 | 2808 | 3018 | Validation only |
| Separate test | 1 | 170 | 641 | Test only |
| Separate test | 2 | 946 | 1326 | Test only |
| Separate test | 3 | 1963 | 2415 | Test only |

There is no manually marked release frame in this final pipeline. The model decides contact from the prescribed book boundary and its own evolving height. An earlier edge-based experiment used manually reviewed release selections; those are not the annotations driving this model.

## Timing and missing observations

The reported recording setting is **1080p at 120 fps**. The exported videos play at about 30 fps, giving slow motion. I assume every exported frame is one uniformly spaced capture sample, so the physical step between samples is `1/120` second. The exported playback rate alone does not establish that. Dropped or duplicated frames would affect the fitted recovery time.

For a dot observation to enter the objective, that dot must have a finite resting reference and a tracked position in a frame with at least four usable dots. A dot missing at initialization stays excluded from that press's objective even if it is later reacquired. A trial also needs at least ten frames with four usable dots and forty individual dot observations. The code checks that the initial marker-height estimate is close to rest.

These rules concern available data. In particular, **100% frame coverage does not mean every dot was tracked throughout**. In the test recordings, dots 1–9 are available in roughly 98–100% of frames, whereas dots 10–18 are available in only about 27–56%, depending on the press and dot. Their lower measured errors can partly reflect missing difficult portions. Disappearance can come from occlusion, blur or tracker failure; the coordinates alone do not tell me which.

Missing book input needs separate handling because the simulator requires a boundary at every step. By default the pipeline rejects unknown input. For the reported fit and evaluation I explicitly allowed gaps of at most **eight missing frames**:

- A gap between finite book observations is filled by linear interpolation.
- When a lifting book leaves the image, preceding upward motion can be extrapolated across a short gap, subject to checks that it clears the resting foam.
- A gap between absent-book observations can be treated as unconstrained. Long, unbounded or inconsistent gaps are rejected.

Foam dots are not used to reconstruct book input. Raw observations are retained, and estimated input is recorded separately. Some reconstructions use later book observations, so this is offline processing rather than a strictly online measurement system.

Test press 1 reconstructs frames **634–638**, and press 2 reconstructs **1304–1308**, five frames each. Press 3 needs none. The viewer flags these estimates. The eight-frame allowance represents about 67 ms of missing capture samples, comparable to the fitted 61.6 ms recovery time. Input uncertainty around separation is therefore an important limitation, even when the reconstructed trajectory looks plausible.

## How the deformation model works

The state is the current height `h`. The resting height is `H = 35 mm`, and `p` is the book underside's height above the table. Each selected press begins with the foam at rest.

For free recovery, I assume that the rate of recovery is proportional to the compression still remaining. With `q = H - h`:

```text
dq/dt = -q / tau
```

A larger `tau` gives slower recovery. Over a small time step, the free update and the contact restriction are:

```text
h_free = H - (H - h) * exp(-dt / tau)
h_next = min(h_free, p)
```

This keeps the block below the book. If the book rises slowly enough, contact can continue while the foam recovers. If it rises faster, the foam separates and recovers at its own rate. The code interpolates the book position over eight substeps per captured-frame interval. There is no inertial state or force calculation.

To compare the height with the image, I scale each resting dot vertically about the table:

```text
y_predicted = table_y + (y_reference - table_y) * h/H
x_predicted = x_reference
```

The same height drives the 3D box. The representation is simple enough to inspect and fit from a small recording, and a rough geometric proxy is permitted by the assignment. Its cost is a strong assumption: every point shares the same vertical strain, with no change in length or width. It cannot reproduce local indentation, lateral bulging, shear, friction, permanent set or a spatially varying recovery. Deep compression makes those omissions especially relevant.

There is also a marker-derived height diagnostic, obtained by estimating a common vertical scale from the observed dots. It is useful for checking assumptions, but it depends on the same uniform-strain idea. It is not an independent measurement of the top surface. The main objective and reported errors use the dot coordinates directly.

## What is learned from the video

I fit **one shared recovery time**, using presses 1–4 of the training recording. The dimensions, capture rate, reference geometry and book motion are supplied. SciPy searches over `tau` between one capture-frame interval and two seconds. For each candidate, the simulator runs from rest using only book input. The loss is the average vertical dot-position mean-squared error in millimetres, with equal weight for each training press.

This is parameter fitting rather than neural-network training. The observations inform the response through the fitted parameter; their recorded height curve is not fed back into the simulator. The model can be run with a different book trajectory, which is how the separate recording is evaluated.

A useful motivation for the exponential rule is a spring and viscous damper acting in parallel. If their effective stiffness and damping are `k` and `b`, unloaded quasistatic force balance gives:

```text
k*q + b*dq/dt = 0
tau = b/k
```

Here `k` would be in N/m and `b` in N·s/m. This interpretation explains the equation, but **the experiment does not identify `k` and `b` separately**. Multiplying both by the same positive factor gives the same recovery curve. Measured displacement does not supply the missing force scale, and the hand's load is unknown. Even if the book's mass were known, it would not establish that extra hand force.

A controlled known-load experiment could help: at a settled, approximately linear operating point, stiffness could be estimated from force divided by compression, followed by `b ≈ k*tau`. Multiple loads and rates would be needed to check whether those quantities remain meaningful for this foam. The current result is an effective recovery model, not that material characterization. The assignment gives stiffness and damping as examples; the behavior fitted here is the recovery time.

## Testing on another recording

Training press 5 is evaluated as a within-recording validation press. The three test presses come from a separate recording of the same object. Their book trajectories drive the frozen **61.6 ms** model; no dynamics parameter is optimized on them.

A test press still needs a resting reference and geometric calibration. These describe the initial setup. Later foam observations are used for comparison and diagnostics, not to reset the predicted state. The input is the measured interaction, so the demonstration concerns the foam's response to that input rather than prediction of the hand's next action.

The test recording was excluded from parameter fitting, but it was inspected while reviewing tracking and fixing software handling. It is not a blind benchmark. All presses are from one object and a similar interaction; they do not establish performance on other objects, viewing conditions or loading directions.

## Results and how much to read into them

The table compares vertical material-dot RMSE in millimetres. RMSE is the square root of the mean squared position error, so lower is better. These measurements come from image tracking and approximate geometric scaling; they are not independently measured 3D surface errors.

The instant-recovery baseline uses `h = min(H, p)`. It compresses with the same book input but returns immediately to rest when unconstrained. Both methods use the same reconstructed input and exactly the same valid observations. This gives a more useful test of the recovery parameter than comparison with a block that never deforms.

| Separate test press | Model, full interval | Instant baseline, full interval | Model, recovery only | Instant baseline, recovery only | Recovery frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2.010 | 2.016 | 0.836 | 1.245 | 10 |
| 2 | 2.124 | 2.134 | 0.711 | 0.942 | 25 |
| 3 | 1.968 | 1.971 | 0.579 | 0.655 | 28 |

Over each full interval, the improvement is **less than 0.5%**. Both methods share the book boundary for much of the press, so they make similar predictions there. A finite recovery time improves the short recovery portions, but that does not outweigh the larger, systematic errors during pressing. The dot plots show that the uniform-compression box does not explain all of the visible motion.

Recovery-only frames use an observation-based rule: the book must be more than 1 mm above the marker-height proxy, with that proxy still at least 0.3 mm below rest. This avoids selecting recovery from the fitted model's own contact flag. However, the proxy is imperfect and the windows are small, so I would not treat these scores as a precise measurement of free recovery. The full-interval scores remain the main comparison.

Each test frame has at least four usable dots. Training frame coverage is approximately **100%, 100%, 79% and 38%**, and validation coverage is **36%**. Validation RMSE is **2.199 mm** on the available observations. Missing points during strong compression can bias the evaluated sample toward easier frames. Neither coverage nor a low error on surviving tracks establishes correct identities throughout the recording.

The recovery time is also unstable across training subsets. Leaving out one training press gives fits of approximately **55.5, 59.9, 56.8 and 717.3 ms**. Halving or doubling the selected time changes training loss by less than 5%. That is evidence that the data and objective only weakly distinguish recovery times. These checks are sensitivity diagnostics, not statistical confidence intervals.

Numerical integration is a much smaller source of variation: increasing from eight to sixteen substeps changes the predicted height by at most about **0.000087 mm**. That checks the solver's resolution, not the physical validity of its assumptions. Apparent base motion and disagreement in the marker-height proxy also point to a mixture of tracking, pose and deformation-model errors that this recording cannot separate cleanly.

What the model does provide is a continuous compression-and-recovery response driven by the book, a fitted parameter from observed material motion, and a comparison on separate interactions with visible residuals. A stronger experiment would improve tracking through deep compression, verify capture timing, obtain a clearer unconstrained release, and add known-load measurements before trying to claim stiffness or damping values.

## Running the project

### View the saved comparison locally

Install the Python dependencies from the project root, then serve the exported page:

```powershell
python -m pip install -r scripts/requirements.txt
cd scripts
python viewer.py serve
```

Open **http://localhost:8000** and keep the terminal open. Ctrl+C stops the server. This uses the existing `viewer/dist` files, including the playback video, and does not need the raw training recording.

To rebuild the viewer data from the saved test observations and frozen training model, run this from `scripts` before serving:

```powershell
python viewer.py export --max-book-gap 8
```

Export recomputes predictions and baseline scores and copies the test video into the viewer folder. It does not fit or change the model. On another machine, export is subject to the saved-path checks described below; the already exported page is the easiest way to inspect the exact reported result.

### Run setup, tracking and fitting

Download the two original recordings from the [Drive folder](https://drive.google.com/drive/folders/1eDp1PoQyIxnEdt35SP5SI9YXnNkyjfJ6?usp=sharing) and place them at:

```text
data/train/marked_foam_train.mp4
data/test/marked_foam_test.mp4
```

The Python requirements are NumPy, SciPy, OpenCV, Matplotlib and Pillow. Setup also uses Tkinter and needs a desktop display. Dependency versions are not pinned, so identical numerical results across versions are not guaranteed. The browser page uses HTML, CSS and Canvas without external JavaScript dependencies; it needs support for the original MP4 codec.

Run the following from `scripts`, using the selection procedure described earlier. Inspect tracking for every press before accepting the fit, especially around compression and release.

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

Repeat the preview commands with other trial numbers to inspect them. In setup, label the first four training intervals `train`, the fifth `validation`, and all separate-recording intervals `test`. Those roles determine which data enter parameter fitting. A full rerun can replace saved outputs; changing manual annotations can change the fit.

### Saved paths and reproducibility

The saved setup files contain absolute video paths, file sizes and modification times. Tracking metadata and the fitted model also store hashes for consistency checks. The JSON files are preserved byte-for-byte in Git because line-ending normalization would change those hashes.

These checks catch accidental reuse of stale processing, but the current path handling makes relocation awkward. On a different computer, use setup with the local footage path, review and save the configuration, then retrack and refit. If an existing configuration prevents setup from opening because it belongs to the original machine's video path, preserve it as a backup outside its expected filename before creating the new setup. A new run with revised annotations should be identified as such. Raw-video processing is not currently a one-command, machine-independent reproduction; the saved export provides the exact predictions reported here.

### Code and output files

The final pipeline consists of:

| File | Purpose |
| --- | --- |
| `scripts/displacement_setup.py` | Manual references, geometry, dots and press intervals |
| `scripts/displacement_tracking.py` | Book detection and material-dot tracking |
| `scripts/displacement_model.py` | Height evolution, unilateral contact and marker projection |
| `scripts/displacement.py` | Tracking, parameter fitting, evaluation and video previews |
| `scripts/viewer.py` | Frozen-result export and local HTTP server |

Annotations are in `data/annotations/`. Measurements, parameters and numeric results are in `data/processed/displacement/`, separated by recording name. Generated plots and demo videos go to `visualizations/displacement/`; exported web files go to `viewer/dist/`. Source videos stay in `data/train/` and `data/test/` locally and are downloaded from Drive.

The training directory's `parameters.json` contains the fitted time, assumptions, sensitivity checks and input-repair record. `observations.npz` stores the tracked measurements, with setup provenance in `tracking_metadata.json`. The viewer's `metrics.json` includes the instant-recovery baseline, which older processed metric files may not contain. `results.json` includes test observations, predictions, missing-input flags and provenance hashes.

Earlier edge-tracking scripts and their outputs remain in the local working directory but are excluded from the submitted repository. Their fitted values are not the results described here.

## The supplied papers and tools used

I used the papers as context for the problem rather than attempting either system in this small experiment. In Kerbl et al., *3D Gaussian Splatting for Real-Time Radiance Field Rendering* (2023), a scene representation is fitted through rendered image comparisons. The connection here is broad: a representation produces projected observations that can be compared with images. This code uses ordinary material-point projection; it does not implement Gaussians, spherical harmonics or the paper's renderer.

Wang et al., *Hybrid Particle-Voxel Dynamics for Multimodal 3D World Simulation* (2026), models how a 3D state changes in response to actions. Separating the book input from the foam state follows that general problem formulation. The implementation here uses an explicit height state and a hand-chosen update rule, with none of the paper's particle–voxel representation, learned latent dynamics or multimodal prediction. A few single-view presses of one object would not support training or evaluating a comparable system.

The spring–damper motivation comes from standard viscoelastic modeling, rather than either paper. The [COMSOL linear viscoelasticity reference](https://doc.comsol.com/6.3/doc/com.comsol.help.sme/sme_ug_theory.06.029.html) describes the Kelvin–Voigt interpretation. The reduced contact rule and uniform-strain observation model are choices made for this implementation, with the limitations discussed above.

I supplied the object, dimensions, recordings and manual annotations, and inspected tracking visually. **The code and explanatory material were developed with substantial OpenAI Codex assistance.** The implementation uses SciPy for optimization, NumPy for array calculations, OpenCV for video and tracking, Matplotlib for plots, and Tkinter/Pillow for setup. The viewer uses browser Canvas and a Python HTTP server. No simulator or pretrained dynamics model from the supplied papers is imported.

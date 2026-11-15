# Final foam model

Read the [project README](../README.md) for the current approach, results, assumptions, limitations, credits and full run instructions.

The final pipeline is `displacement.py` with `displacement_model.py`, `displacement_tracking.py`, `displacement_setup.py` and `viewer.py`. Earlier `run.py` and edge-tracking outputs are exploratory work; their fitted values and metric files are not the final result. The old documentation is preserved in `README_LEGACY_EDGE_MODEL.md`.

To view the existing exported test result from this directory:

```powershell
python -m pip install -r requirements.txt
python viewer.py serve
```

Open http://localhost:8000. If you need to regenerate the web data from saved observations, run `python viewer.py export --max-book-gap 8` first. Export does not fit the model.

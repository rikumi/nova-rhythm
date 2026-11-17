# SHARP Gaussian scenes

Static outfit artwork is inferred locally with [Apple SHARP](https://github.com/apple/ml-sharp). The website displays the resulting 3D Gaussian scene with WebGL2 and [Spark](https://sparkjs.dev/), using extended float32-center encoding without LoD reduction. This does not use transparent image layers or an original-image plane.

## Local runtime

The existing ignored runtime is `.build/sharp-layering`, with the official source checkout in `ml-sharp`, the Apple `sharp_2572gikvuh.pt` checkpoint, and per-outfit prediction folders. The tested interpreter is `.build/layering-trial/venv/Scripts/python.exe` with CUDA PyTorch and SHARP requirements. Model weights and environments must not be committed or uploaded with scene assets.

```powershell
.build/layering-trial/venv/Scripts/python.exe scripts/sharp/run_batch.py
```

The script selects every outfit whose original catalog card contains at most one layer. It reads existing original artwork from `.build/layering-trial/<code>/original.png`, downloading missing copies from the existing artwork release. Game installation directories are never modified. `references/sharp-scenes-plan.json` records the inputs and hashes. Per-item caches bind source hashes, checkpoint hash, precision, camera assumptions and exporter version. Existing inspected trial predictions are adopted once and pinned to the current source hashes.

Inference uses SHARP's native 1536x1536 input, BF16 autocast, and the original 30mm focal-length assumption. All predicted Gaussians are retained. Metric unprojection transforms both centers and oriented covariance; camera calibration remains consistent with the original image aspect ratio. PLY exports retain float32 attributes. Gaussian colors are exported as sRGB SH0 for interoperability; the local viewer decodes to linear for blending before its display conversion.

Progress and failures are saved in `.build/sharp-layering/batch`. Interrupted or changed inputs can be resumed with the same command. A failed scene withholds publication. Source images, raw Gaussian arrays and local PLYs remain separate from the release artifacts.

## Local viewer

Open `http://127.0.0.1:5174/?disc=214016#/outfit` for Spring Chronicle. A line-art cube button sits immediately before the download button and reads, for example, `3D (59.7MB)`. The size comes from `compressed_bytes`, displayed in decimal MB with one fractional digit. Each outfit starts in its regular view and only an explicit button click loads its model. Selecting another outfit, leaving the outfit page, refreshing, or choosing the regular artwork/phonograph view clears the temporary 3D selection. Neither URL parameters nor stored 3D preferences enable it. Completed model file caching remains available after a manual click. The manifest alone determines support, with no per-model HEAD probes. Catalog and manifest are resolved together before displaying the first outfit. The model payload and large WebGL chunk are only requested when 3D is displayed. A missing manifest entry hides the option; payload failures keep the option and current manual selection stable, showing original static artwork instead. Static artwork is displayed underneath centered status messages throughout module download, model download, worker decompression and parsing, and remains until the first 3D render. Mouse movement, captured touch dragging and the existing device-tilt input move the camera; it recenters after input ends. Rendering stops when the view is stationary. Fullscreen uses the same actual 3D scene.

During development, scene files are exposed through the restricted Vite route `/__sharp-3d/<code>/scene.json` and `.ply`. Binary predictions, checkpoints and arbitrary filesystem paths are not served. No browser inference or model downloads are included: the browser loads a precomputed scene.

## Legacy Release publication

```powershell
.build/layering-trial/venv/Scripts/python.exe scripts/sharp/run_batch.py --publish
```

After all static outfits pass numeric, size and hash validation, a separate `sharp-scenes-YYYYMMDD` release is created as a draft. Each PLY is gzip-compressed losslessly and its decompressed SHA256 is checked against the original float32 PLY. Scene metadata, `sharp-scenes.json`, the processing plan and model attribution are uploaded. The authenticated GitHub CLI verifies every remote asset's SHA256 and byte count before publishing the release. Reruns skip matching remote assets.

The uploaded metadata uses `scene_format: "ply+gzip"`. WebGL clients can decompress the response with `DecompressionStream('gzip')`, then pass PLY bytes to their splat loader. Each entry includes original-image dimensions, focal length, vertical field of view, focus distance, hashes and URLs. The local viewer supports this format as well as uncompressed PLY.

The resource publisher performs no Git commits, pushes or Pages deployments. It does not change the suspended Qwen layering workflow. Scene quality remains subject to the monocular model's inferred depth and disocclusion behavior.

## Depth calibration and manual corrections

`references/sharp-scenes-depth.json` limits the effective inverse-depth span to 0.35–1.25. Scenes already in range retain their original depth. Compressing inverse depth and expanding log depth both preserve camera rays and transform full Gaussian covariance; original predictions remain unchanged. The camera pivot is placed in front of the scene, with the pointed side receding, and the artwork frame follows the same smoothed input.

`references/sharp-scenes-semantic.json` contains explicit, reproducible spatial corrections. For 4038 (波光漫游), soft polygons select the character and swim ring. Their depth is brought close to the surrounding water surface, retaining modestly nearer dolphins and underwater scenery, reflecting a view upward from underwater. The initial strong recession was reduced from a subject depth factor of 1.25 to 0.90 after visual feedback; the surrounding depth mapping remains unchanged. The warp preserves each center's original screen projection and transforms covariance with the full spatial Jacobian, including the feathered mask gradient. It does not repaint the artwork or rerun inference. As with other monocular scenes, newly exposed surfaces may retain reconstruction artifacts when rotated.

Re-export selected scenes after changing these rules:

```powershell
.venv/Scripts/python.exe scripts/sharp/export_scene.py --codes 4038
```

The batch runner also checks these rules when deciding whether an export cache remains valid. Run the batch runner before publishing if exporting manually, so that its result index is synchronized with the scene files.


## Website integration

Production loads the small `public/data/sharp-scenes.json` manifest on demand. Model payloads and all 106 original PNGs are committed to this repository on the isolated `site-assets` branch. They remain outside the Pages artifact. URLs reference the `site-assets` branch on `raw.githubusercontent.com`, which was verified to load the full 57 MiB scene with CORS in a production browser. Original Releases remain archival backups. There is no third-party proxy or browser inference dependency.

The one-time migration from verified legacy releases is `scripts/sharp/store_repository_assets.py`. It uses an isolated `.build/repository-assets` worktree and commits/pushes models in batches of eight, respecting the per-push size limit without changing the main worktree. All original PNGs are verified against their recorded SHA256 before committing. `references/runtime-assets.json` records the resulting branch revision. To prepare website metadata after migration:

```powershell
.venv/Scripts/python.exe scripts/sharp/prepare_web.py
npm run build
```

`prepare_web.py` reads the verified geometry metadata in `references/sharp-scenes-results.json` and the verified asset revision and branch URL in `references/runtime-assets.json`. It updates `public/data/outfits.json` original-image URLs and generates `public/data/sharp-scenes.json`. The editable story-melodies mapping is not touched. It copies camera calibration, immutable model hashes and download URLs into the runtime manifest; no binary data is copied. Keep the original asset filenames unchanged. The server should return gzip files as `application/octet-stream` without `Content-Encoding: gzip`, because the viewer explicitly decompresses their payload with `DecompressionStream`.

Original multi-layer outfits retain their own renderer. Their layer separation is limited to approximately the generated batch's peak visible parallax: 5.2% horizontally and 3.6% vertically at full pointer displacement. This limit accounts for each outfit's rotation angles, scales all depths together around zero, and preserves relative spacing, direction and the resting composition. Native cards already within the limit and generated canvas layers are unchanged.


To check out the large resources locally without putting them in the Pages tree:

```powershell
git fetch origin site-assets
git worktree add --detach .build/repository-assets origin/site-assets
```

Ordinary website builds do not need to check out that branch. Keep model filenames content-addressed and refresh the runtime manifest after changing resources. Record the verified revision for auditing while continuing to use branch URLs, so new model versions get new cache keys.


## Reliable scene loading

Download, decompression and parsing have separate status messages. Interrupted downloads retry up to three times with HTTP Range resume. A 45-second inactivity watchdog detects stalled connections; an actively progressing slow download has no total time limit. The Raw endpoint was checked to honor byte ranges.

Gzip decompression runs in a short-lived Web Worker and transfers its result back without copying. Simultaneous normal/fullscreen loads share one job. The most recent decoded scene is retained in memory; at most two complete compressed scenes are stored in the optional `nova-sharp-models-v1` Cache Storage cache. A corrupt disk cache is discarded and downloaded again. Storage failure does not prevent network loading. GPU allocation starts after download and decompression complete.

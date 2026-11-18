# SHARP Gaussian scenes

Static outfit artwork is inferred locally with [Apple SHARP](https://github.com/apple/ml-sharp). The website displays the resulting 3D Gaussian scene with WebGL2 and [Spark](https://sparkjs.dev/), using extended float32-center encoding without LoD reduction. This does not use transparent image layers or an original-image plane.

Native prefab layers always take precedence, including when an older SHARP archive contains the same outfit. Generation, runtime-manifest preparation and the frontend all exclude native cards. An earlier extraction silently skipped stripped MonoBehaviour type trees and consequently misclassified native outfits, including 4046. `scripts/native_typetrees.py` reads matching schemas from version and install game bundles only when both the script identifier and serialized layout hash match, retaining full payload validation. `scripts/recover_native_layers.py` audits all layouts, restores missing ImageWarp backgrounds and unprefixed Sprite references, and exports full-resolution lossless textures; `references/native-layer-recovery.json` records recovered geometry, source hashes and exported texture hashes. Then run `python scripts/sharp/prepare_web.py` to refresh the filtered SHARP manifest. Game files remain read-only. Original model archives remain available for research, but only 43 genuinely static cards are now exposed as SHARP scenes.

## Local runtime

The existing ignored runtime is `.build/sharp-layering`, with the official source checkout in `ml-sharp`, the Apple `sharp_2572gikvuh.pt` checkpoint, and per-outfit prediction folders. The tested interpreter is `.build/layering-trial/venv/Scripts/python.exe` with CUDA PyTorch and SHARP requirements. Model weights and environments must not be committed or uploaded with scene assets.

```powershell
.build/layering-trial/venv/Scripts/python.exe scripts/sharp/run_batch.py
```

The script selects every outfit whose original catalog card contains at most one layer. It reads existing original artwork from `.build/layering-trial/<code>/original.png`, downloading missing copies from the existing artwork release. Game installation directories are never modified. `references/sharp-scenes-plan.json` records the inputs and hashes. Per-item caches bind source hashes, checkpoint hash, precision, camera assumptions and exporter version. Existing inspected trial predictions are adopted once and pinned to the current source hashes.

Inference uses SHARP's native 1536x1536 input, BF16 autocast, and the original 30mm focal-length assumption. All predicted Gaussians are retained. Metric unprojection transforms both centers and oriented covariance; camera calibration remains consistent with the original image aspect ratio. PLY exports retain float32 attributes. Gaussian colors are exported as sRGB SH0 for interoperability; the local viewer decodes to linear for blending before its display conversion.

Progress and failures are saved in `.build/sharp-layering/batch`. Interrupted or changed inputs can be resumed with the same command. A failed scene withholds publication. Source images, raw Gaussian arrays and local PLYs remain separate from the release artifacts.

## Local viewer

Open `http://127.0.0.1:5174/?disc=214016#/outfit` for Spring Chronicle. The cube button before the download button reads `3D`. Its explicit on/off selection is remembered in `nova-sharp-enabled`; the interface has no download-size label or cache checkbox. Both desktop and touch devices load the original continuous SHARP Gaussian model. Manifest entries determine availability. Static artwork remains beneath centered loading status until the first successful render. Pointer, captured touch dragging and device tilt move the camera; it recenters after input ends. Camera coordinates are rounded to four decimal places before comparison, avoiding camera, DOM attribute and render updates when the rounded position is unchanged. Fullscreen suspends and disposes the underlying preview to avoid duplicate GPU allocations.

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

Native and SHARP views share `useArtworkPointer`: gesture geometry is read once and invalidated by resize/scroll, while light-position writes are batched per animation frame. Input bounds follow the resting layout instead of the animated surface. This optimization does not reduce splat density or render resolution. Pointer and sensor motion use a shared 1.2 gain; the custom sensor dropdown reverses sensor motion independently of dragging.

## Archived depth-slice experiment

The image-slice experiment is disabled. Desktop and mobile both render the original Gaussian models, ignoring `layer_scene` metadata. The scripts and earlier assets below are retained for reproducibility; baking or publishing them does not activate image slices in the website.

`scripts/sharp/export_depth_layers.py` reads the corrected metric PLY, including the existing depth/semantic adjustments. Twenty plane depths span the visible scene range. Each Gaussian is assigned to its nearest plane, with outliers clamped to the end planes. The offline renderer preserves the Gaussian covariance and linear color blending before exporting straight-alpha, lossless WebP images at the original image resolution. Transparent outer margins are cropped with original pixel coordinates retained. Empty planes remain present as transparent one-pixel images. There is no new inference or semantic segmentation. Small parallax differences from continuous Gaussian depth are expected because depth is quantized.

The mobile renderer filters premultiplied samples, recovers linear color before blending, and normalizes accumulated coverage before display. This avoids dark seams when many small transparency masks are minified. Original image files are not downscaled. The package stores a validated `SDL1` header and twenty WebP payloads, so the existing resumable download and opt-in CacheStorage controls work with one file.

To reproduce locally, install NumPy and Pillow in the analysis Python environment, install Playwright (`npm install --no-save --package-lock=false playwright`) and make Chrome available. First export the metric scenes, then run:

```powershell
node scripts/sharp/bake_depth_layers.mjs 4016
node scripts/sharp/bake_depth_layers.mjs
```

`NOVA_PYTHON` and `NOVA_PLAYWRIGHT_MODULE` can select existing installations. Results go to `.build/sharp-depth-layers/<code>/`: twenty individual images, the packed `scene.layers`, reference/composite PNGs and `layers.json`. Source hashes and settings allow completed models to be reused. Full-scene versus layer-composite color error is recorded and checked before publication. Vite retains local package routes for analysis; the active viewer does not select these packages. `publish_depth_layers.py` uploads packages on the isolated resource branch, verifies remote Git objects, records `references/sharp-depth-layers-results.json`, and updates the runtime manifest. Subsequent `prepare_web.py` calls retain matching layer entries.

Download, decompression and parsing have separate status messages. Interrupted downloads retry up to three times with HTTP Range resume. A 45-second inactivity watchdog detects stalled connections; an actively progressing slow download has no total time limit. The Raw endpoint was checked to honor byte ranges.

Gzip decompression runs in a short-lived Web Worker and transfers its result back without copying. Simultaneous normal/fullscreen loads share one job. The most recent decoded scene and its downloaded payload are retained in memory. Once downloaded, a Cache checkbox appears immediately after the 3D button. Persistent storage in `nova-sharp-models-v1` is opt-in: checking it stores the payload, and unchecking immediately deletes only the persistent entry. The current preview and in-memory payload remain available, so checking again needs no download. Explicitly stored models are not automatically evicted by an application count limit. Network requests bypass the implicit HTTP cache; persistent model storage is controlled by this checkbox. Development PLY URLs include the exported scene hash to prevent stale local geometry. A corrupt disk cache is discarded and downloaded again. Storage failure does not prevent network loading. GPU allocation starts after download and decompression complete.

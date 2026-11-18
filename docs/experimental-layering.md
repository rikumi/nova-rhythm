# Experimental semantic artwork layers

Normal artwork is unchanged. Add `experimental_layering=1` to opt into generated layers; the option is retained when navigating between tracks. Only static outfits are eligible. Native game layers, covers, downloads and Open Graph images retain their original sources.

The optional manifest is `public/data/experimental-layering.json`. If it is unavailable, or an outfit has no complete 2–10-layer entry, the original artwork is used. All generated layers share a full image canvas, including transparent margins. The renderer keeps their registration in normal and fullscreen views.

## Model and local runtime

The selected model is [Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered), using [Unsloth Q4_K_M weights](https://huggingface.co/unsloth/Qwen-Image-Layered-GGUF). [ComfyUI](https://github.com/Comfy-Org/ComfyUI) and [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) run inside `.build/layering-trial`, which is excluded from Git. Model weights and complete runtime environments are not uploaded to the repository.

The tested Windows runtime uses an RTX 4060 Laptop GPU with 8GB VRAM, Python 3.14, PyTorch 2.14.1 CUDA 13.0, ComfyUI commit `e9afbccc2669677076feb08e52658f129cd8c12b`, and ComfyUI-GGUF commit `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`.

Prepare these files under `.build/layering-trial/ComfyUI/models`:

- `unet/qwen-image-layered-Q4_K_M.gguf`: [weights](https://huggingface.co/unsloth/Qwen-Image-Layered-GGUF/resolve/main/qwen-image-layered-Q4_K_M.gguf), SHA256 `6eedc0c9a08f91f1f39959b9ac991d643d351baf45d1248267c4fdd61645dfd0`.
- `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`: [weights](https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors), SHA256 `cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4`.
- `vae/qwen_image_layered_vae.safetensors`: [weights](https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/vae/qwen_image_layered_vae.safetensors), SHA256 `c5320595fc61859ccdd0282184208f7b781c983b8ce4c6bc3e7723a807d3d28d`.

The runtime interpreter is `.build/layering-trial/venv/Scripts/python.exe`. Install ComfyUI requirements and GGUF dependencies in that environment. Text encoding and image inference run in separate processes to release the encoder before loading the larger diffusion model. On the tested Windows setup, disabling async offloading and CUDA async allocation avoids a native access violation during GGUF loading.

## Plan and execution

`references/experimental-layering-plan.json` lists the static outfits, original artwork URLs, captions and requested layer counts. Captions are manual or AI annotations and can be edited. Most images request four layers to favor intact semantic objects; crowded scenes request five or six. The default range is four to ten. Reviewed corrections can set `minimum_layers: 2` to prioritize intact objects over layer count.

An item can specify `seed` to override the shared random seed and a numeric `priority` (larger values run first) to place a pending regeneration ahead of other work. Changing its caption, seed or requested layer count invalidates only that item's cached result at the next image checkpoint, without interrupting the current image.

Generate a fresh plan only when intentionally replacing its annotations:

```powershell
.venv/Scripts/python.exe scripts/layering/prepare_plan.py
```

Start or resume inference:

```powershell
.venv/Scripts/python.exe scripts/layering/run_batch.py
```

Progress, model logs and result fingerprints are saved under `.build/layering-trial/batch`. Each completed outfit has its own original PNG, inference input, workflow, generated PNG layers, reconstructed image and result JSON. Completed inputs are skipped after checking their source and output hashes. Failed cases retain error records. The worker retries with another seed or one additional layer when it cannot obtain the required nonempty outputs.

The worker temporarily prevents automatic system sleep while it runs; the setting ends with the process. A stopped process can be restarted with the same command. An interrupted image restarts from its first diffusion step.

Vite serves completed local results through an ignored `local-overrides.json` manifest. For example:

```text
http://127.0.0.1:5174/?disc=214016&experimental_layering=1#/outfit
```

Refresh the page after another image completes. The AI layering toggle appears only for single-image outfits, between phonograph mode and the gravity control. It defaults to off and persists its state locally. `experimental_layering=1` also enables it; `experimental_layering=0` disables it explicitly. Disabling the toggle restores the original artwork. Native multilayer outfits are never replaced.

Each card retains its own original depth values and projection; no cross-card depth normalization is applied. The arrival stagger is anchored to the first animation start, with the last layer scheduled 200ms later when assets are ready. Slow-loading layers still wait for the preceding layers in Z order.

Review decisions are recorded in `references/experimental-layering-reviews.json`, pinned to layer hashes. A regenerated image needs a new review. An optional `layer_order` in the plan changes only drawing order; `layer_order_hashes` prevents applying a reviewed reorder to different generated images.

## Publication

Publication is currently disabled pending user review. The plan's `publication.enabled: false` and the local batch `publication-hold.json` each independently prevent release upload, Git push and Pages deployment, even with `--publish`. Both holds must be explicitly removed only after the user requests resumption. Local generation continues.

When publication is enabled, the optional `--publish` flag uploads only after every planned outfit has a valid result:

```powershell
.venv/Scripts/python.exe scripts/layering/run_batch.py --publish
```

It creates a separate `experimental-layering-qwen-YYYYMMDD` GitHub Release using the authenticated GitHub CLI, converts PNG layers to lossless WebP, verifies the decoded pixels and uploaded SHA256 digests, then publishes the new manifest and generation records. Only the two generated manifest files are committed by the publisher; unrelated staged or working changes are preserved. Pushing the commit triggers the existing Pages workflow, whose completion is recorded locally.

The publisher expects the frontend support and these scripts to have already been committed on `main`. It never force-pushes. A failed image, upload or deployment produces a failed status with details, retaining completed assets for retry.

## Reviewed publication and corrections

`references/experimental-layering-corrections.json` records requested grouping and occlusion corrections. `apply_corrections.py` transfers existing RGBA pixels without inference, retains backups, and checks that the composite changes by at most rounding error. Unreviewed corrected results stay local.

An explicit reviewed-only publication can bypass the general publication hold: `python scripts/layering/publish_layers.py --approved-only`. It filters accepted entries against their exact saved layer hashes and uses a separate reviewed release tag. General automatic publication remains disabled.

The runtime setup installs a streaming CPU safetensors reader when `--disable-mmap` is active. Ordinary tensor reads avoid the native mapped-reader fault observed on repeated Windows encoder loads. FP8 and BF16 tensor bytes are preserved and model weights are not modified.

## Native-resolution backfill trial (suspended)

`backfill_hd.py` was tested on 4016, 4027 and 4043. It refines model alpha boundaries with original-image guidance and restores visible RGB detail from the 2400x1700 original. Generated hidden-region paint is preserved separately. Run with the optional local Pillow/NumPy/SciPy analysis dependencies: `python scripts/layering/backfill_hd.py --codes 4016 4027 4043`. The ignored `.build/layering-hd` outputs can be previewed through Vite; original model outputs remain untouched.

The neutral composites match the originals to at most one channel level, but this is insufficient: low-resolution model masks leave some character outlines on the background. Those errors become visible during parallax. The trial was rejected for edge ownership; this method must not be treated as a validated replacement for native game layers. Measurements and the rejection are recorded in `references/experimental-layering-hd-samples.json`.

AI layer generation is disabled by the plan, automatic publication remains held, and the public manifest is disabled so existing links use the original artwork. The UI only offers the AI checkbox when an enabled manifest supplies a generated card. Publishing additionally rejects textures whose dimensions differ from the original artwork; matching dimensions alone do not establish acceptable boundaries. No further batch work should resume without a new explicit request.

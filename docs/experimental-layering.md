# Experimental semantic artwork layers

Normal artwork is unchanged. Add `experimental_layering=1` to opt into generated layers; the option is retained when navigating between tracks. Only static outfits are eligible. Native game layers, covers, downloads and Open Graph images retain their original sources.

The optional manifest is `public/data/experimental-layering.json`. If it is unavailable, or an outfit has no complete 4–10-layer entry, the original artwork is used. All generated layers share a full image canvas, including transparent margins. The renderer keeps their registration in normal and fullscreen views.

## Model and local runtime

The selected model is [Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered), using [Unsloth Q4_K_M weights](https://huggingface.co/unsloth/Qwen-Image-Layered-GGUF). [ComfyUI](https://github.com/Comfy-Org/ComfyUI) and [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) run inside `.build/layering-trial`, which is excluded from Git. Model weights and complete runtime environments are not uploaded to the repository.

The tested Windows runtime uses an RTX 4060 Laptop GPU with 8GB VRAM, Python 3.14, PyTorch 2.14.1 CUDA 13.0, ComfyUI commit `e9afbccc2669677076feb08e52658f129cd8c12b`, and ComfyUI-GGUF commit `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`.

Prepare these files under `.build/layering-trial/ComfyUI/models`:

- `unet/qwen-image-layered-Q4_K_M.gguf`: [weights](https://huggingface.co/unsloth/Qwen-Image-Layered-GGUF/resolve/main/qwen-image-layered-Q4_K_M.gguf), SHA256 `6eedc0c9a08f91f1f39959b9ac991d643d351baf45d1248267c4fdd61645dfd0`.
- `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`: [weights](https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors), SHA256 `cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4`.
- `vae/qwen_image_layered_vae.safetensors`: [weights](https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/vae/qwen_image_layered_vae.safetensors), SHA256 `c5320595fc61859ccdd0282184208f7b781c983b8ce4c6bc3e7723a807d3d28d`.

The runtime interpreter is `.build/layering-trial/venv/Scripts/python.exe`. Install ComfyUI requirements and GGUF dependencies in that environment. Text encoding and image inference run in separate processes to release the encoder before loading the larger diffusion model. On the tested Windows setup, disabling async offloading and CUDA async allocation avoids a native access violation during GGUF loading.

## Plan and execution

`references/experimental-layering-plan.json` lists the static outfits, original artwork URLs, captions and requested layer counts. Captions are manual or AI annotations and can be edited. Most images request four layers to favor intact semantic objects; crowded scenes request five or six. The supported range is four to ten. The approved first sample is retained.

An item can specify `seed` to override the shared random seed and `priority: true` to place a pending regeneration ahead of other work. Changing its caption, seed or requested layer count invalidates only that item's cached result on the next run.

Generate a fresh plan only when intentionally replacing its annotations:

```powershell
.venv/Scripts/python.exe scripts/layering/prepare_plan.py
```

Start or resume inference:

```powershell
.venv/Scripts/python.exe scripts/layering/run_batch.py
```

Progress, model logs and result fingerprints are saved under `.build/layering-trial/batch`. Each completed outfit has its own original PNG, inference input, workflow, generated PNG layers, reconstructed image and result JSON. Completed inputs are skipped after checking their source and output hashes. Failed cases retain error records. The worker retries with another seed or one additional layer when it cannot obtain four nonempty outputs.

The worker temporarily prevents automatic system sleep while it runs; the setting ends with the process. A stopped process can be restarted with the same command. An interrupted image restarts from its first diffusion step.

Vite serves completed local results through an ignored `local-overrides.json` manifest. For example:

```text
http://127.0.0.1:5174/?disc=214016&experimental_layering=1#/outfit
```

Refresh the page after another image completes. Removing the parameter restores the original artwork.

## Publication

The optional `--publish` flag uploads only after every planned outfit has a valid result:

```powershell
.venv/Scripts/python.exe scripts/layering/run_batch.py --publish
```

It creates a separate `experimental-layering-qwen-YYYYMMDD` GitHub Release using the authenticated GitHub CLI, converts PNG layers to lossless WebP, verifies the decoded pixels and uploaded SHA256 digests, then publishes the new manifest and generation records. Only the two generated manifest files are committed by the publisher; unrelated staged or working changes are preserved. Pushing the commit triggers the existing Pages workflow, whose completion is recorded locally.

The publisher expects the frontend support and these scripts to have already been committed on `main`. It never force-pushes. A failed image, upload or deployment produces a failed status with details, retaining completed assets for retry.

## Rejected depth-slice trial

Apple SHARP was tested locally on three samples. Inference took about 1.7–2.0 seconds per image and projected Gaussian depth bands took about 6–11 seconds to export. The static reconstruction was close, but depth bands split continuous people, clothing and props. It was rejected for this feature. Its local outputs are preserved separately under `.build/sharp-layering`; no SHARP layers are published by this pipeline.

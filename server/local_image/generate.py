import json
import os
import sys
from pathlib import Path

import torch
from diffusers import EulerDiscreteScheduler, StableDiffusionXLPipeline, UNet2DConditionModel
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file


BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
LIGHTNING_REPO = "ByteDance/SDXL-Lightning"
LIGHTNING_CHECKPOINT = "sdxl_lightning_4step_unet.safetensors"
SIZES = {
    "square": (1024, 1024),
    "portrait": (768, 1024),
    "landscape": (1024, 768),
}


def _read_request():
    request = json.load(sys.stdin)
    prompt = str(request.get("prompt", "")).strip()
    aspect_ratio = str(request.get("aspect_ratio", "square")).strip().casefold()
    output_name = Path(str(request.get("output", "image.png"))).name
    if not prompt or len(prompt) > 1800:
        raise ValueError("invalid prompt")
    if aspect_ratio not in SIZES:
        aspect_ratio = "square"
    if output_name != request.get("output") or not output_name.endswith(".png"):
        raise ValueError("invalid output path")
    return prompt, aspect_ratio, output_name


def main():
    prompt, aspect_ratio, output_name = _read_request()
    width, height = SIZES[aspect_ratio]

    unet = UNet2DConditionModel.from_config(BASE_MODEL, subfolder="unet").to(
        "cuda",
        torch.float16,
    )
    checkpoint = hf_hub_download(LIGHTNING_REPO, LIGHTNING_CHECKPOINT)
    state_dict = load_file(checkpoint, device="cuda")
    unet.load_state_dict(state_dict)
    del state_dict
    torch.cuda.empty_cache()

    pipe = StableDiffusionXLPipeline.from_pretrained(
        BASE_MODEL,
        unet=unet,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
        low_cpu_mem_usage=True,
    ).to("cuda")
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config,
        timestep_spacing="trailing",
    )
    pipe.set_progress_bar_config(disable=True)
    pipe.enable_vae_slicing()
    pipe.enable_vae_tiling()

    enhanced_prompt = (
        f"{prompt}. High quality, coherent composition, clean details, "
        "professional lighting, no watermark, no logo, no illegible text."
    )
    with torch.inference_mode():
        image = pipe(
            enhanced_prompt,
            width=width,
            height=height,
            num_inference_steps=4,
            guidance_scale=0,
        ).images[0]

    output_path = Path("/output") / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    print(json.dumps({"success": True, "output": output_name, "width": width, "height": height}))


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()

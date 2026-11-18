"""User-authorized pixel-preserving black-background removal."""
from pathlib import Path

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[2]
source = root / 'frontend/public/brand/dapeter-logo.png'
rgb = np.asarray(Image.open(source).convert('RGB'))
brightness = rgb.max(axis=2).astype(np.float32)
# Remove near-black background noise, with a narrow soft alpha transition.
# Original RGB values, including the navy rim and gray bars, are unchanged.
alpha = np.rint(np.clip((brightness - 12) / 16, 0, 1) * 255).astype(np.uint8)
rgba = np.dstack((rgb, alpha))
full = Image.fromarray(rgba)
destination = Path(__file__).parent / 'dapeter-logo-transparent-v1.png'
full.save(destination)
assert np.array_equal(np.asarray(Image.open(destination))[:, :, :3], rgb)
assert np.all(alpha[:100] == 0)
box = full.getbbox()
assert box
left, top, right, bottom = box
padding = 16
crop = full.crop((max(0, left-padding), max(0, top-padding), min(full.width, right+padding), min(full.height, bottom+padding)))
cropped = destination.with_name('dapeter-logo-transparent-cropped-v1.png')
crop.save(cropped)
preview = Image.new('RGBA', crop.size, '#e8edf3')
preview.alpha_composite(crop)
preview.convert('RGB').save(destination.with_name('dapeter-logo-alpha-preview.jpg'))
print(f'Saved {destination.name}: {full.size}; original RGB preserved; alpha {alpha.min()}..{alpha.max()}')
print(f'Saved {cropped.name}: {crop.size}')

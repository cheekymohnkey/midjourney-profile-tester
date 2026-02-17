from io import BytesIO
from PIL import Image
import base64
from typing import Optional
import random


def image_to_jpeg_bytes(img: Image.Image, quality: int = 85, max_size: Optional[int] = None) -> bytes:
    """Return JPEG bytes for the given PIL Image, optionally resizing to max_size on the longest side."""
    if max_size is not None:
        ratio = max_size / max(img.size)
        if ratio < 1:
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def embed_image_data(img: Image.Image, src: Optional[str] = None, *, max_size: int = 1024, quality: int = 85) -> str:
    """Return a base64-encoded JPEG representation of `img` (string, no header).

    This always returns inline base64 (no presigned URL). The caller is
    responsible for adding the `data:image/jpeg;base64,` header if needed.
    """
    img_bytes = image_to_jpeg_bytes(img, quality=quality, max_size=max_size)
    return base64.b64encode(img_bytes).decode('ascii')


def _rgb_to_hex(rgb_tuple) -> str:
    r, g, b = rgb_tuple
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _luminance(r, g, b):
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def adjust_palette_temperature_and_saturation(hexs, temperature_bias: float = 0.0, saturation_level: float = 1.0):
    """Adjust a list of hex colors by shifting hue (temperature_bias) and scaling saturation.

    - `temperature_bias` is a small float where positive => warmer (shift toward red/yellow),
      negative => cooler (shift toward blue/cyan). Typical range [-1.0, 1.0].
    - `saturation_level` multiplies the existing saturation (1.0 = unchanged).

    Returns a new list of hex strings.
    """
    try:
        import colorsys

        # Map temperature bias to degrees of hue shift; clamp modestly to avoid extreme shifts
        max_shift_deg = 30.0
        shift_deg = max(-max_shift_deg, min(max_shift_deg, float(temperature_bias) * max_shift_deg))
        shift_frac = shift_deg / 360.0

        # Clamp saturation multiplier to reasonable range
        sat_mul = max(0.0, min(2.0, float(saturation_level)))

        out = []
        for h in hexs:
            try:
                h = h.lstrip('#')
                if len(h) == 3:
                    r = int(h[0]*2, 16)
                    g = int(h[1]*2, 16)
                    b = int(h[2]*2, 16)
                else:
                    r = int(h[0:2], 16)
                    g = int(h[2:4], 16)
                    b = int(h[4:6], 16)
                # colorsys uses 0..1 floats
                rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
                # Convert to HLS for easy hue/saturation adjustments
                h0, l0, s0 = colorsys.rgb_to_hls(rf, gf, bf)
                # apply hue shift
                h1 = (h0 + shift_frac) % 1.0
                # apply saturation scaling
                s1 = max(0.0, min(1.0, s0 * sat_mul))
                # convert back
                rf2, gf2, bf2 = colorsys.hls_to_rgb(h1, l0, s1)
                r2 = int(max(0, min(255, round(rf2 * 255))))
                g2 = int(max(0, min(255, round(gf2 * 255))))
                b2 = int(max(0, min(255, round(bf2 * 255))))
                out.append(f"#{r2:02x}{g2:02x}{b2:02x}")
            except Exception:
                out.append(h if h.startswith('#') else f"#{h}")

        return out
    except Exception:
        return hexs


def _kmeans_palette_from_pixels(pixels, k=4, max_samples=2000, iterations=8):
    """Simple k-means clustering on a list of (r,g,b) pixels.

    This is a lightweight, dependency-free k-means suited for small images /
    sampled pixels. `pixels` may be a list of integer 3-tuples.
    Returns list of (centroid_rgb, count) tuples ordered by count desc.
    """
    if not pixels:
        return []

    pts = pixels
    if len(pts) > max_samples:
        pts = random.sample(pts, max_samples)

    # initialize centroids by choosing k random points
    k = min(k, len(pts))
    centroids = [tuple(map(float, pts[i])) for i in random.sample(range(len(pts)), k)]

    for _ in range(iterations):
        clusters = [[] for _ in range(k)]
        for p in pts:
            # assign to nearest centroid
            best_i = 0
            best_d = None
            for i, c in enumerate(centroids):
                d = (p[0]-c[0])**2 + (p[1]-c[1])**2 + (p[2]-c[2])**2
                if best_d is None or d < best_d:
                    best_d = d
                    best_i = i
            clusters[best_i].append(p)

        moved = False
        for i, cluster in enumerate(clusters):
            if not cluster:
                # reinitialize empty centroid
                centroids[i] = tuple(map(float, pts[random.randrange(len(pts))]))
                moved = True
                continue
            nr = sum(p[0] for p in cluster) / len(cluster)
            ng = sum(p[1] for p in cluster) / len(cluster)
            nb = sum(p[2] for p in cluster) / len(cluster)
            newc = (nr, ng, nb)
            if newc != centroids[i]:
                centroids[i] = newc
                moved = True
        if not moved:
            break

    # compute final counts
    counts = [0] * k
    for p in pts:
        best_i = 0
        best_d = None
        for i, c in enumerate(centroids):
            d = (p[0]-c[0])**2 + (p[1]-c[1])**2 + (p[2]-c[2])**2
            if best_d is None or d < best_d:
                best_d = d
                best_i = i
        counts[best_i] += 1

    centroids_with_counts = list(zip(centroids, counts))
    # filter out centroids that are near-white/near-black
    filtered = []
    for c, cnt in centroids_with_counts:
        lum = _luminance(c[0], c[1], c[2])
        if lum >= 0.96 or lum <= 0.03:
            continue
        filtered.append((c, cnt))

    # sort by count desc
    filtered.sort(key=lambda x: x[1], reverse=True)
    return filtered


def sample_image_palette(image_path: str, n_colors: int = 4, resize: int = 256, method: str = 'median_cut') -> list:
    """Sample the most common colors from an image file and return hex strings.

    method: 'median_cut' (PIL adaptive palette) or 'kmeans' (lightweight k-means).
    Returns a list of hex strings ordered by importance.
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img.thumbnail((resize, resize), Image.Resampling.LANCZOS)

        if method == 'kmeans':
            pixels = list(img.getdata())
            # filter near-white/near-black
            pixels = [p for p in pixels if 0.03 < _luminance(*p) < 0.96]
            clusters = _kmeans_palette_from_pixels(pixels, k=n_colors)
            hexs = [_rgb_to_hex(c) for c, _ in clusters]
            return hexs

        # default: median_cut / adaptive palette
        pal = img.convert('P', palette=Image.ADAPTIVE, colors=n_colors)
        palette = pal.getpalette()  # list of r,g,b triples
        color_counts = pal.getcolors()
        if not color_counts:
            return []

        # Sort by count descending
        color_counts.sort(reverse=True, key=lambda x: x[0])
        hexs = []
        for count, idx in color_counts[:n_colors]:
            base = idx * 3
            if base + 2 < len(palette):
                r, g, b = palette[base:base+3]
                hexs.append(f"#{r:02x}{g:02x}{b:02x}")
        return hexs
    except Exception:
        return []


def sample_palette_from_images(image_paths: list, n_colors: int = 5, per_image_colors: int = 6, resize: int = 256, method: str = 'median_cut') -> list:
    """Aggregate color samples from multiple image files and return ordered hex list.

    If `method` is 'kmeans', per-image sampling will use k-means and then counts
    are aggregated across images. Otherwise uses adaptive palette per image.
    """
    try:
        from collections import Counter

        counter = Counter()

        for p in image_paths:
            try:
                if method == 'kmeans':
                    # get kmeans clusters from this image
                    clusters = sample_image_palette(p, n_colors=per_image_colors, resize=resize, method='kmeans')
                    # each returned hex counts once per cluster (kmeans is less frequency-aware)
                    for h in clusters:
                        counter[h] += 1
                else:
                    img = Image.open(p).convert('RGB')
                    img.thumbnail((resize, resize), Image.Resampling.LANCZOS)
                    pal = img.convert('P', palette=Image.ADAPTIVE, colors=per_image_colors)
                    palette = pal.getpalette() or []
                    counts = pal.getcolors() or []
                    # collect colors, but skip near-white/near-black
                    for cnt, idx in counts:
                        base = idx * 3
                        if base + 2 < len(palette):
                            r, g, b = palette[base:base+3]
                            lum = _luminance(r, g, b)
                            if lum >= 0.96 or lum <= 0.03:
                                continue
                            hexs = f"#{r:02x}{g:02x}{b:02x}"
                            counter[hexs] += cnt
            except Exception:
                continue

        if not counter:
            return []

        # Return top n_colors by accumulated count
        result = [h for h, _ in counter.most_common(n_colors)]
        return result
    except Exception:
        return []

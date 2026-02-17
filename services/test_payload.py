import json
from services.image_utils import embed_image_data
from typing import List
from PIL import Image
from storage_helpers import Path as StoragePath, load_image
import logging

logger = logging.getLogger(__name__)


def build_rubric_text(rubric: dict, row: dict | None = None) -> str:
    """Render a rubric dict into a human-readable text block for LLM prompts.

    Ensures MUST/AVOID/PREFER sections are emitted and labels are copied verbatim.
    """
    if not isinstance(rubric, dict):
        return "\n\nRubric: (no rubric provided for this test)\nPlease ensure the test record includes a `rubric` field with `must`, `avoid`, and `prefer` lists.\n"

    weights = rubric.get('weights') or {}
    musts = rubric.get('must') or []
    avoids = rubric.get('avoid') or []
    prefers = rubric.get('prefer') or []

    out = []
    out.append("\n\nRubric Weights:\n" + json.dumps(weights))
    out.append("\n\nMUST (copy labels verbatim):\n")
    for item in musts:
        out.append(f"- {item}\n")

    out.append("\nAVOID (copy labels verbatim):\n")
    for item in avoids:
        out.append(f"- {item}\n")

    out.append("\nPREFER (copy labels verbatim):\n")
    for item in prefers:
        out.append(f"- {item}\n")

    notes = rubric.get('notes') or ''
    out.append("\nRubric Notes:\n" + notes)

    return "".join(out)


def prepare_test_message(test_name: str, filepaths, row: dict | None, test_obj: dict | None) -> List[dict]:
    """Prepare a sequence of message parts (text/image blocks) for a single test.

    `filepaths` may be a Path, list of Paths, or None. Returns a list of dicts
    matching the structure expected by `batch_ai_rate_images`'s message_content.
    """
    parts = []

    # Determine canonical id
    canonical_id = None
    if isinstance(test_obj, dict):
        canonical_id = test_obj.get('guid') or test_obj.get('id')
    if not canonical_id:
        canonical_id = test_name.replace(' ', '_').replace('/', '_')

    prompt_text = (row.get('Prompt') if isinstance(row, dict) else '')
    section = (row.get('Section') if isinstance(row, dict) else '')

    parts.append({
        "type": "text",
        "text": f"\n\n**Test: {test_name}**\nID: {canonical_id}\nTest Name: {test_name}\nSection: {section}\nPrompt: {prompt_text}"
    })

    # Add rubric if available on test_obj or row
    rubric = None
    try:
        if isinstance(test_obj, dict):
            rubric = test_obj.get('rubric')
    except Exception:
        rubric = None
    if not rubric and isinstance(row, dict):
        rubric = row.get('rubric')

    parts.append({"type": "text", "text": build_rubric_text(rubric, row)})

    # Attach images - accept PIL Images, pathlib.Path, or filenames
    if isinstance(filepaths, list):
        total = len(filepaths)
        for idx, fp in enumerate(filepaths, 1):
            try:
                if isinstance(fp, Image.Image):
                    img_obj = fp
                    img_b64 = embed_image_data(img_obj)
                else:
                    # Assume path-like
                    p = StoragePath(str(fp))
                    if not p.exists():
                        logger.error("Image file does not exist, skipping: %s", fp)
                        continue
                    img_obj = load_image(str(p))
                    img_b64 = embed_image_data(img_obj)
                parts.append({"type": "text", "text": f"Image {idx}/{total}:"})
                parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}})
            except Exception as e:
                logger.exception("Failed to embed image for %s: %s", fp, e)
                continue
    elif filepaths:
        try:
            if isinstance(filepaths, Image.Image):
                img_obj = filepaths
                img_b64 = embed_image_data(img_obj)
                parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}})
            else:
                p = StoragePath(str(filepaths))
                if not p.exists():
                    logger.error("Image file does not exist, skipping: %s", filepaths)
                else:
                    img_obj = load_image(str(p))
                    img_b64 = embed_image_data(img_obj)
                    parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}})
        except Exception as e:
            logger.exception("Failed to embed single image %s: %s", filepaths, e)

    return parts

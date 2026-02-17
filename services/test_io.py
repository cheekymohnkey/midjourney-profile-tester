from pathlib import Path
from typing import Optional, Union, List


def collect_test_image_paths(output_dir: Union[str, Path], profile_id: str, test_name: str, find_image_file) -> Optional[Union[Path, List[Path]]]:
    """Collect image path(s) for a given profile/test.

    - For known multi-image 'void' tests, returns a list of Path objects (may be empty).
    - For normal tests, returns a single Path or None.

    The function delegates actual file existence lookup to `find_image_file` which
    matches storage-specific logic.
    """
    # Recognize void tests by convention (legacy names present in the app)
    void_test_names = {"Null Prompt (Photo)", "Null Prompt (Art)"}

    out_dir = Path(output_dir)
    profile_dir = profile_id if profile_id else 'baseline'

    if test_name in void_test_names:
        images = []
        for img_num in range(1, 9):
            fp = find_image_file(out_dir, profile_dir, test_name, image_num=img_num)
            if fp:
                images.append(fp)
        return images

    # Single image test
    fp = find_image_file(out_dir, profile_dir, test_name)
    return fp

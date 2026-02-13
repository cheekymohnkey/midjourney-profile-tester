#!/usr/bin/env python3
import os
from pathlib import Path
# Load .env manually
env_path = Path(__file__).resolve().parents[1] / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    import sys
    # Ensure project root is on sys.path so local modules can be imported
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from storage import init_storage, get_storage
s = get_storage()
profile = 'qye9ofd'
files = s.list_files(f'profile_results/{profile}', '*')
print('USE_S3=', os.getenv('USE_S3'))
print('S3_BUCKET_NAME=', os.getenv('S3_BUCKET_NAME'))
print('S3_PREFIX=', os.getenv('S3_PREFIX'))
print('Found files count:', len(files))
for f in files:
    print(f)


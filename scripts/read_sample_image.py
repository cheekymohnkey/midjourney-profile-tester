#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import get_storage
from PIL import Image
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

key = 'profile_results/qye9ofd/qye9ofd_9b69211e0824445ab61a46fc719e7bed.jpg'
logger.info('Reading %s', key)
s = get_storage()
try:
    data = s.read_bytes(key)
    logger.info('Read bytes: %d', len(data))
    img = Image.open(BytesIO(data))
    logger.info('Image format=%s size=%s mode=%s', img.format, img.size, img.mode)
except Exception as e:
    logger.exception('Error reading image: %s', e)

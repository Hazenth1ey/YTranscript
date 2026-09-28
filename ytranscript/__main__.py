"""Lets you run the tool as ``python -m ytranscript <link>`` without installing."""

import sys

from .cli import main

sys.exit(main())

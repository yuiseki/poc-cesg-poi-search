#!/usr/bin/env python3
"""Export STAC item from manifest."""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poc_cesg_poi_search.stac import manifest_to_stac_item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    item = manifest_to_stac_item(manifest, base_url=args.base_url)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
    print(f"Written: {args.out}")


if __name__ == "__main__":
    main()

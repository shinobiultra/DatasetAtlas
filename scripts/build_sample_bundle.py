#!/usr/bin/env python3
"""Build a compact sample browser from checked-in, approved inputs only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_release import ROOT, build_frontend


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/dataset-atlas-samples.zip')
    parser.add_argument('--max-bytes', type=int, default=50_000_000,
                        help='Maximum expanded bundle size; default 50 MB')
    parser.add_argument('--serve', action='store_true', help='Open the freshly built sample browser instead of making a ZIP')
    parser.add_argument('--workbench', action='store_true', help='Start the local workbench after building its interface')
    parser.add_argument('--no-open', action='store_true', help='Print the sample URL without opening a browser')
    parser.add_argument('--port', type=int, default=8767, help='Sample server port; stable 8767 by default, 0 for an ephemeral port')
    parser.add_argument('--skip-npm-install', action='store_true', help='Reuse dependencies already installed with npm ci (CI only)')
    args = parser.parse_args()
    if args.serve and args.workbench:
        parser.error('--serve and --workbench are mutually exclusive')
    if args.max_bytes <= 0:
        parser.error('--max-bytes must be positive')
    build_frontend(install_dependencies=not args.skip_npm_install)
    if args.workbench:
        from dataset_atlas.cli import main as atlas
        return atlas(['--root', str(ROOT), 'serve'])
    if args.serve:
        from dataset_atlas.sample_launcher import serve
        serve(ROOT / 'apps/web/dist', port=args.port, open_browser=not args.no_open)
        return 0
    from dataset_atlas.exports.sample_bundle import build_sample_bundle
    receipt = build_sample_bundle(ROOT / 'apps/web/dist', args.output,
                                  notices_dir=ROOT / 'licenses', license_path=ROOT / 'LICENSE',
                                  max_bytes=args.max_bytes)
    checksum = args.output.with_name(args.output.name + '.sha256')
    with checksum.open('x') as destination:
        destination.write(f"{receipt['sha256']}  {args.output.name}\n")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

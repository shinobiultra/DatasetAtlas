#!/usr/bin/env python3
"""Move catalogue entries that are not separate real datasets out of registry/datasets and record why.

The researcher's instruction of 2026-10-09: aliases and views of another dataset are not catalogue datasets, and the catalogue holds
only real datasets. An entry is moved only when its own registry record says it is another name for, or a subset, filtered selection,
protocol or recipe built from, another catalogued dataset with no separately released data of its own, or that it is a platform or a
generic descriptor that names no dataset. Entries with their own prepared data are never moved. The YAML is kept under
registry/excluded/ (not loaded by the registry) and each exclusion is recorded in registry/candidate_dispositions.yaml, which the
coverage and corpus code already treat as an account of the mention. Nothing here changes identity, release or any other field of a
dataset that stays in the catalogue.

    python scripts/exclude_catalogue_entries.py [--apply]
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DECIDED = 'Researcher instruction 2026-10-09: aliases and views are not catalogue datasets; only real datasets are listed.'

ALIAS = 'alias_not_separate_dataset'
VIEW = 'view_not_separate_dataset'
PLATFORM = 'platform_not_dataset'
NONE = 'no_identifiable_dataset'

# id -> (disposition, catalogue entries it refers to, why)
EXCLUDE: dict[str, tuple[str, list[str], str]] = {
    'cub': (ALIAS, ['cub-200-2011'], 'Survey name for the CUB birds family; the identifiable release is CUB-200-2011.'),
    'cub200': (ALIAS, ['cub-200-2011'], 'Survey spelling of CUB-200-2011.'),
    'flowers': (ALIAS, ['flowers102'], 'Chart label for the Oxford Flowers family; the catalogued release is Flowers-102.'),
    'fgvc': (ALIAS, ['fgvc-aircraft'], 'Chart label for FGVC-Aircraft.'),
    'conceptual-captions': (ALIAS, ['cc3m'], 'Name of the Conceptual Captions family; the catalogued release is CC3M.'),
    'ms-coco': (ALIAS, ['coco'], 'Spelling of MS COCO; mentions name no release, split or selection.'),
    'mscoco': (ALIAS, ['coco'], 'Spelling of MS COCO used for retrieval evaluation; no release or split is named.'),
    'ms-coco-7f846b38': (ALIAS, ['coco'], 'Spelling of MS COCO; the paper selects ten images without naming them.'),
    'ms-coco-captions': (ALIAS, ['coco'], 'MS COCO captions; caption IDs and split are not named.'),
    'visualqa': (ALIAS, ['vqa-v2'], 'Survey name of the official VQA benchmark; the catalogued release is VQA v2.'),
    'sb-syn': (ALIAS, ['sbbench-syn'], 'Chart label for the SBBench synthetic releases.'),
    'sb-syn-crop': (ALIAS, ['sbbench-syn-crop'], 'Chart label for the SBBench synthetic crop releases.'),
    'illusory-vqa': (ALIAS, ['illusionvqa'], 'Spelling or family name of IllusionVQA; the catalogued release is IllusionVQA.'),
    'facial-expression-recognition-2013': (ALIAS, ['fer-2013'], 'The same Kaggle Challenges-in-Representation-Learning data as FER-2013.'),
    'imagenet': (ALIAS, ['imagenet-ilsvrc-2012', 'imagenet-1k'], 'Umbrella name that many papers use for training, validation and sampled subsets; no single release.'),
    'imagenet-ilsvrc': (ALIAS, ['imagenet-ilsvrc-2012'], 'The ILSVRC challenge release, cited only as model-training lineage.'),
    'coco-gender': (ALIAS, ['coco-demographic-annotations', 'cocogender'], 'Gender-label overlay on COCO attributed to Zhao et al.; not a new image archive.'),
    'coco-train': (VIEW, ['coco'], 'The train split of COCO; the paper names no release year or image IDs.'),
    'coco-caption': (VIEW, ['coco'], 'The caption annotations of the COCO releases.'),
    'coco-detection-dataset': (VIEW, ['coco'], 'A survey descriptor of the COCO detection source; no separate archive or subset.'),
    'coco-spatial': (VIEW, ['coco-one', 'coco-two'], "The What's Up COCO-spatial overlay on COCO images, catalogued as coco-one and coco-two."),
    'cocogendertxt': (VIEW, ['cocogender'], 'The caption/text configuration derived from COCO-GB.'),
    'mscoco-100-target-subset': (VIEW, ['coco'], 'A 100-image selection from COCO with no published ID list.'),
    'imagenet100': (VIEW, ['imagenet-ilsvrc-2012'], 'One of several non-identical 100-class selections of ILSVRC; no class list or seed.'),
    'imagenetval': (VIEW, ['imagenet-ilsvrc-2012'], 'The validation split of ILSVRC; exact year and selection unpinned.'),
    'imagenet-sampled-1-000-images': (VIEW, ['imagenet-ilsvrc-2012'], 'A paper-sampled 1,000-image subset of ImageNet; selection unreleased.'),
    'cifar-2': (VIEW, ['cifar-10'], 'A two-class protocol generated from CIFAR-10 with the authors\' seed and index files.'),
    'scrambled-mnist': (VIEW, ['mnist'], 'Pixel- and Fourier-phase scrambling of MNIST; a transformation, not a release.'),
    'shiftmnist': (VIEW, ['mnist'], 'Binary and texture shifts constructed from MNIST digits; a protocol, not a release.'),
    'artbench-2': (VIEW, ['artbench'], 'A paper-specific two-style subset of ArtBench-10.'),
    'laion-aesthetics': (VIEW, ['laion'], 'The aesthetic-score subset of LAION-5B.'),
    'vl-gender': (VIEW, ['fairface', 'miap', 'phase'], 'A gender-balanced 1,000-image-per-source evaluation drawn from other datasets.'),
    'vlagenderbias': (VIEW, ['fairface', 'miap', 'phase'], "A benchmark the authors' scripts build by sampling other datasets."),
    'gpt-4v-filtered-vl-gender-subset': (VIEW, ['fairface', 'miap', 'phase'], 'A GPT-4V-filtered sample of VL-Gender.'),
    'perturbed-gender-benchmark-image-variants': (VIEW, ['cocogender', 'fairface', 'miap', 'phase'], 'Colour, lighting, object and background perturbations of other benchmarks.'),
    'visual-counterfact-filtered-467': (VIEW, [], 'A 467-case analysis subset of Visual-CounterFact.'),
    'gda-adversarial-image-variants': (VIEW, [], 'Adversarial variants generated from samples of three existing datasets.'),
    'gaussian-rubbish-examples': (VIEW, [], 'Generated noise inputs used as a probe, not a dataset.'),
    'custom-speech-segment-collection': (VIEW, ['wall-street-journal'], 'Training segments derived from a read-speech corpus; not released as a dataset.'),
    'dall-e-generated-target-images': (VIEW, [], 'Target images an attack method generates; no separate archive.'),
    'paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection': (VIEW, ['hc-bench'], 'The 53-image wild part of HC-Bench.'),
    'paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set': (VIEW, ['hc-bench'], 'The 53-image wild part of HC-Bench.'),
    'brain-score': (PLATFORM, [], 'A benchmark platform hosting many datasets, not a dataset.'),
    'robustbench': (PLATFORM, [], 'A robustness leaderboard, model zoo and library, not a source-image dataset.'),
    'custom-dataset': (NONE, [], 'A generic survey label that names no dataset.'),
    'custom-image-editing-dataset': (NONE, [], 'A generic survey descriptor of editing examples; no fixed release.'),
    'concept-editing-dataset': (NONE, [], 'A survey descriptor; no independently named data archive.'),
    'contrastive-prompts': (NONE, [], 'Method inputs, not a standalone dataset.'),
    'ostris-dataset': (NONE, [], 'A survey shorthand whose dataset was not resolved.'),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    datasets = ROOT / 'registry/datasets'
    present = {p.stem for p in datasets.glob('*.yaml')} | {p.stem for p in (ROOT / 'registry/excluded').glob('*.yaml')}
    entries = {i: yaml.safe_load(((datasets if (datasets / f'{i}.yaml').exists() else ROOT / 'registry/excluded') / f'{i}.yaml').read_text()) for i in EXCLUDE}
    problems = []
    for i, (_, targets, _) in EXCLUDE.items():
        if i not in present:
            problems.append(f'{i}: no such entry')
        for target in targets:
            if target not in present or target in EXCLUDE:
                problems.append(f'{i}: refers to {target}, which is not a kept catalogue entry')
    if problems:
        print('\n'.join(problems))
        return 1
    dispositions_path = ROOT / 'registry/candidate_dispositions.yaml'
    document = yaml.safe_load(dispositions_path.read_text())
    recorded = {item['id'] for item in document['excluded_from_dataset_catalogue']}
    for i, (kind, targets, why) in EXCLUDE.items():
        if i in recorded:
            continue
        entry = entries[i]
        record = {'id': i, 'name': entry['name'], 'disposition': kind, 'reason': why}
        if targets:
            record['refers_to'] = targets
        record.update(paper_ids=entry['paper_ids'], decided_by=DECIDED, entry_file=f'registry/excluded/{i}.yaml')
        if entry.get('source_url'):
            record['source_url'] = entry['source_url']
        document['excluded_from_dataset_catalogue'].append(record)
    redirects = {item['alias_id'] for item in document['alias_redirects']}
    if 'facial-expression-recognition-2013' not in redirects:
        document['alias_redirects'].append({'alias_id': 'facial-expression-recognition-2013', 'canonical_id': 'fer-2013', 'disposition': 'same_challenge_data_alias',
            'reason': 'Both entries name the Kaggle Challenges in Representation Learning FER data (Goodfellow et al. 2013).',
            'paper_ids': entries['facial-expression-recognition-2013']['paper_ids'], 'source_url': entries['facial-expression-recognition-2013']['source_url']})
    print(f'{len(EXCLUDE)} entries; kept catalogue would hold {len(present) - len(EXCLUDE)}')
    if args.apply:
        (ROOT / 'registry/excluded').mkdir(exist_ok=True)
        for i in EXCLUDE:
            if (datasets / f'{i}.yaml').exists():
                shutil.move(datasets / f'{i}.yaml', ROOT / 'registry/excluded' / f'{i}.yaml')
        dispositions_path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

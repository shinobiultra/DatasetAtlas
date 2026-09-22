# Source audit: 40 additional canonical groups

Original-source research only. A public project page does not establish the paper-selected release, adapter coverage, or media publication rights. All 40 adapters/previews remain unimplemented.

Audit receipts: `work/sources/source-audit-jobs-batch2.json`.

| ID | Identity | Access | Primary source | Finding |
|---|---|---|---|---|
| `artbench` | resolved | public | [official](https://github.com/liaopeiyuan/artbench) | Author release has 60,000 artworks, 10 styles and explicit downloads; paper variant not pinned. |
| `cc3m` | resolved | public | [official](https://github.com/google-research-datasets/conceptual-captions) | Google publishes TSV URL-caption pairs; images remain third-party URLs and may disappear. Same source family as conceptual-captions candidate. |
| `cub-200-2011` | resolved | public | [official](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Original Caltech bird dataset has 11,788 images, 200 categories, boxes, parts and attributes; same source family as cub candidate. |
| `deepfashion` | family_only | unverified | [official](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html) | CUHK lists several distinct benchmarks; Attribute/Category release differs from other task archives that require agreement and institutional email. |
| `docci` | resolved | public | [official](https://google.github.io/docci/) | Google offers descriptions, images, metadata as separate files, with images 7.1 GB. |
| `emoset` | family_only | public | [official](https://github.com/JingyuanYY/EmoSet) | Original authors distinguish 118,102 richly labeled images from 3.3M broad pool; paper mention does not pin which. |
| `exams-v` | resolved | public | [official](https://github.com/mbzuai-nlp/EXAMS-V) | Author repository links the dataset; multimodal and text-only questions coexist. |
| `fer-2013` | resolved | gated | [official](https://www.kaggle.com/c/challenges-in-representation-learning-facial-expression-recognition-challenge/data) | Original challenge is on Kaggle; registration and challenge rules govern access. Third-party Kaggle reuploads are not original rights evidence. |
| `finevision` | family_only | public | [official](https://huggingface.co/datasets/HuggingFaceM4/FineVision) | HuggingFaceM4 publishes many source-specific configurations; a generic FineVision reference does not identify the selected mixture or snapshot. |
| `hellaswag-pro` | unresolved | unverified | [paper](https://arxiv.org/html/2502.11393v2) | Author paper defines the benchmark and says it would be publicly released upon acceptance; no author-hosted data release verified in this audit. |
| `iconqa` | resolved | public | [official](https://github.com/lupantech/IconQA) | Authors provide diagrams/questions and distinguish Icon645 pretraining dataset from IconQA. |
| `idenprof` | resolved | public | [official](https://github.com/OlafenwaMoses/IdenProf) | Author repo release offers train/test archives; first release has 900 train and 200 test per profession. |
| `imagenet-ilsvrc-2012` | resolved | gated | [official](https://www.image-net.org/challenges/LSVRC/) | Official ImageNet challenge page sends common classification release to Kaggle and requires login/request for other data. |
| `imagenet100` | family_only | gated | [official](https://www.image-net.org/challenges/LSVRC/) | ImageNet100 denotes multiple nonidentical 100-class selections derived from ILSVRC; paper mention does not specify class list or seed. |
| `lingoqa` | resolved | public | [official](https://github.com/wayveai/lingoqa) | Wayve author repository publishes benchmark and download instructions; evaluation has 500 answers. |
| `llava-instruct-150k` | resolved | public | [official](https://huggingface.co/datasets/liuhaotian/LLaVA-Instruct-150K) | Original LLaVA docs link instruction JSON files; visual examples reference source images separately. |
| `mm-safetybench` | resolved | public | [official](https://github.com/isXinLiu/MM-SafetyBench) | Author release provides multimodal safety evaluation data; distinguish it from SafeBench. |
| `mmbench-en-dev` | resolved | public | [official](https://github.com/open-compass/MMBench) | OpenCompass author repo identifies the English development split; test split relies on separate submission path. |
| `mme-perception` | resolved | public | [official](https://mme-benchmark.github.io/home_page.html) | Official MME site defines perception as sum of existence/count/position/color/poster/celebrity/scene/landmark/artwork/OCR subtasks; reasoning is separate. |
| `ms-cxr` | resolved | gated | [official](https://physionet.org/content/ms-cxr/1.1.0/) | MS-CXR annotations are a subset of MIMIC-CXR; credentialed PhysioNet access and underlying images needed. |
| `places` | family_only | unverified | [official](https://places2.csail.mit.edu/) | MIT Places family includes multiple versions and split sizes; original site may be intermittently unavailable. |
| `pmc-vqa` | resolved | public | [official](https://github.com/xiaoman-zhang/PMC-VQA) | Original author repository describes 227k VQA pairs over 149k biomedical images from PMC. |
| `puzzlevqa` | resolved | public | [official](https://github.com/declare-lab/LLM-PuzzleTest) | Author-maintained repository includes puzzle data and evaluation; distinct from VisualPuzzles. |
| `raise1k` | family_only | unverified | [official](https://loki.disi.unitn.it/RAISE/) | Original RAISE RAW image archive is identifiable; exact RAISE1k image IDs/processing in cited experiment are not pinned. |
| `roco` | resolved | public | [official](https://github.com/razorx89/roco-dataset) | Original ROCO repository documents radiology image-caption pairs; ROCOv2 later excludes many original images for rights. |
| `rs-vqa` | family_only | public | [official](https://rsvqa.sylvainlobry.com/) | Author page lists multiple remote-sensing VQA releases; paper mention does not identify variant. |
| `rsicd` | resolved | public | [official](https://github.com/201528014227051/RSICD_optimal) | Original paper points to author repository for the RSICD corpus. |
| `safebench` | resolved | public | [official](https://safebench-mm.github.io/) | Paper-cited SafeBench is the MLLM safety benchmark, not autonomous-driving SafeBench; official site links author data. |
| `seedbench` | family_only | public | [official](https://github.com/AILab-CVC/SEED-Bench) | Original authors now host several distinct SEED-Bench versions; generic citation does not select one. |
| `shapeworld` | resolved | public | [official](https://github.com/AlexKuhnle/ShapeWorld) | Original code generates synthetic shape-language datasets; it is a generator, not one immutable image archive. |
| `sun397` | resolved | unverified | [official](https://sun.cs.princeton.edu/) | Original SUN site currently forwards to a sparse MIT page; exact archive availability could not be verified. |
| `the-pile` | resolved | unverified | [official](https://github.com/EleutherAI/The-Pile) | Original author repo documents a large mixed text corpus; current original distribution path and component availability need verification. |
| `vibeeval` | resolved | public | [official](https://huggingface.co/datasets/RekaAI/VibeEval) | RekaAI official HF dataset has 269 examples and normal/hard categories. |
| `visualpuzzle` | resolved | public | [official](https://github.com/neulab/VisualPuzzles) | NeuLab author repo links a public HF dataset; distinct from PuzzleVQA. |
| `waterbirds` | resolved | public | [official](https://github.com/kohpangwei/group_DRO) | Original author repo provides a generated tarball and script; regeneration differs because of random seeds. |
| `whoops` | resolved | public | [official](https://whoops-benchmark.github.io/) | Authors link public benchmark dataset with four visual-commonsense tasks. |
| `wilds` | family_only | public | [official](https://wilds.stanford.edu/) | WILDS is a collection of ten distribution-shift datasets across modalities; no single WILDS media release. |
| `wmdp` | resolved | public | [official](https://huggingface.co/datasets/cais/wmdp) | CAIS publishes original multiple-choice hazardous-knowledge proxy benchmark. |
| `zerobench` | resolved | public | [official](https://zerobench.github.io/) | Original project links author data with a later v2 revision; paper reference alone does not select v1/v2. |
| `recap-datacomp-1b` | resolved | public | [official](https://github.com/UCSC-VLAA/Recap-DataComp-1B) | Authors publish Parquet metadata and URL-based img2dataset instructions; linked images are not one self-contained licensed archive. |

## Acquisition leads

- `artbench`: Small 32x32 variant is an accessible preview lead.
- `cc3m`: Annotation-only bounded preview; never treat URLs as redistributed image assets.
- `cub-200-2011`: CaltechDATA archive has a published checksum; bounded preview feasible.
- `deepfashion`: Choose benchmark first; do not promise one generic DeepFashion download.
- `docci`: 10.5 MB descriptions are a bounded metadata preview lead; image preview needs 7.1 GB or source-specific range access.
- `emoset`: Choose 118K versus 3.3M before implementing.
- `exams-v`: Public author dataset lead; image inclusion requires rights review.
- `fer-2013`: Registration-dependent original CSV, no anonymous downloader.
- `finevision`: Configuration-specific bounded streaming only after pinning revision.
- `hellaswag-pro`: Request author release or locate official version; do not substitute original HellaSwag.
- `iconqa`: Direct author archive is an accessible adapter lead.
- `idenprof`: Release archives are an accessible bounded acquisition lead.
- `imagenet-ilsvrc-2012`: Large, credentialed acquisition; no auto-download.
- `imagenet100`: Require exact class list/split before identity resolution.
- `lingoqa`: Use author download instructions; video bytes need bounded transport.
- `llava-instruct-150k`: 229 MB instruction JSON is an annotation-only lead.
- `mm-safetybench`: Use original paired data rather than derived tiny split.
- `mmbench-en-dev`: VLMEvalKit loader names the exact dev split.
- `mme-perception`: Use perception subtask only; avoid conflating MME aggregate.
- `ms-cxr`: Requires PhysioNet credentials and DUA; genuine external gate.
- `places`: Choose exact Places release, e.g. Places365 Standard, before adapter.
- `pmc-vqa`: Public author annotation lead; media rights are per article.
- `puzzlevqa`: Small authored benchmark suitable for bounded preview.
- `raise1k`: Need exact 1k selection manifest; original site timed out during audit.
- `roco`: Pin original vs v2, then inspect image-level licenses.
- `rs-vqa`: Select LR/HR release before source adapter.
- `rsicd`: Author repository is acquisition lead; rights review required for public images.
- `safebench`: Use official HF release, preserve harmful-content provenance.
- `seedbench`: Resolve cited version before adapter; image/video handling differs.
- `shapeworld`: Reproducible generation needs configuration and random seed pinned.
- `sun397`: Download link requires live verification; do not call implementation gap an external gate.
- `the-pile`: No bulk download; identify specific component and original release first.
- `vibeeval`: Small public 269-item benchmark is a direct preview lead.
- `visualpuzzle`: 1,168-item author benchmark is a small adapter lead.
- `waterbirds`: Use published tarball for exact benchmark, not regenerated variant.
- `whoops`: Small 500-image source is an accessible lead after dataset rights check.
- `wilds`: Select named WILDS component before adapting.
- `wmdp`: Text-only metadata source; avoid exposing sensitive prompts in preview.
- `zerobench`: Small benchmark lead; pin version and scoring rules.
- `recap-datacomp-1b`: Metadata streaming only; no unbounded billion-image acquisition.

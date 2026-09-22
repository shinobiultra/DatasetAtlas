# Source audit: 29 remaining disjoint groups

Primary-source research only. The registry retains paper-specific candidate IDs, corpus mention roles, and unimplemented adapter/preview states. A source-family page does not prove the exact paper sample or media publication rights.

Audit receipt: `work/sources/source-audit-jobs-batch3.json`.

| ID | Identity | Access | Primary source | Finding |
|---|---|---|---|---|
| `cifar10` | resolved | public | [official](https://www.cs.toronto.edu/~kriz/cifar.html) | Original CIFAR-10 family is identifiable; this spelling is a separate catalogue candidate with multiple paper roles, not an independent release. |
| `cifar100` | resolved | public | [official](https://www.cs.toronto.edu/~kriz/cifar.html) | Original CIFAR-100 family is identifiable; this spelling does not represent a second source release. |
| `coco-2014` | resolved | public | [official](https://cocodataset.org/#download) | Original COCO 2014 release exists, but the survey table does not specify train, val, captions, or detection subset. |
| `coco-train` | family_only | public | [official](https://cocodataset.org/#download) | Attack paper says clean images from COCO train without pinning release year or selected image IDs. |
| `cub200` | family_only | public | [official](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Survey table says CUB200; official CUB-200-2011 is an identifiable candidate but table does not pin version. |
| `facial-expression-recognition-2013` | resolved | gated | [official](https://www.kaggle.com/c/challenges-in-representation-learning-facial-expression-recognition-challenge/data) | The cited paper names Goodfellow et al. 2013 FER-2013, 35,887 grayscale faces, then selects 500 model-correct samples and constructs emotion-pair prompts. |
| `fgvc` | family_only | unverified | [official](https://www.robots.ox.ac.uk/~vgg/data/fgvc-aircraft/) | Evaluation chart labels FGVC alongside Cars/DTD/EuroSAT/Flowers/Pets; it does not spell out aircraft or split. |
| `flowers` | family_only | unverified | [official](https://www.robots.ox.ac.uk/~vgg/data/flowers/102/) | The chart labels Flowers but gives no class count or split; Oxford releases Flowers 17 and Flowers 102. |
| `imagenet` | family_only | gated | [official](https://www.image-net.org/) | Many paper roles cite ImageNet, including training, validation, model lineage, and sampled subsets; one release cannot cover all mentions. |
| `imagenet-ilsvrc` | family_only | gated | [official](https://www.image-net.org/challenges/LSVRC/) | Deep Image Prior paper says AlexNet trained on ImageNet ILSVRC, which establishes model-training lineage, not a new Atlas image evaluation release. |
| `imagenet-segmentation` | resolved | unverified | [official](https://github.com/yossigandelsman/clip_text_span) | Survey table cites Gandelsman et al.; author code explicitly uses gtsegs_ijcv.mat from calvin-vision.net. This should not be silently replaced with Gao ImageNet-S. |
| `imagenetval` | family_only | gated | [official](https://www.image-net.org/challenges/LSVRC/) | Survey table says ImageNetVal; likely ILSVRC validation but exact study source, year and selection are not pinned. |
| `jiechieu-tsopze-resume-corpus` | resolved | public | [official](https://github.com/florex/resume_corpus) | Author repository supplies resumes_corpus.zip and resume_samples.zip with occupation labels; later paper mines skill n-grams from these resumes. |
| `llava-instruct-150k-3a74a703` | family_only | public | [official](https://huggingface.co/datasets/HuggingFaceM4/FineVision/tree/main/LLaVA_Instruct_150K) | Paper explicitly draws from FineVision rather than the standalone original LLaVA JSON; exact sampled 10,000 IDs and revision are not pinned. |
| `ms-coco-7f846b38` | family_only | public | [official](https://cocodataset.org/#download) | Paper randomly selects ten MS COCO images for a sentiment experiment; original source family is known but selected images are not. |
| `ms-coco` | family_only | public | [official](https://cocodataset.org/#download) | Mentions include caption-guided image retrieval, 36 selected images, and a survey-table citation; none proves a common exact release. |
| `ms-coco-captions` | family_only | public | [official](https://cocodataset.org/#download) | Adversarial evaluation randomly selects an MS-COCO caption; the task family is identifiable but caption IDs and split are not. |
| `mscoco` | family_only | public | [official](https://cocodataset.org/#download) | AnyAttack tables use MSCOCO text-to-image/image-to-text retrieval; exact retrieval split and preparation are not stated by this candidate. |
| `ok-vqa` | resolved | public | [official](https://okvqa.allenai.org/download.html) | Original author site publishes questions and annotations separately from COCO images; A-OKVQA is a different dataset. |
| `oxfordpet` | resolved | public | [official](https://www.robots.ox.ac.uk/~vgg/data/pets/) | Oxford publishes images and trimap annotations separately; same source family as pets candidate, not a new release. |
| `restricted-imagenet` | resolved | gated | [official](https://github.com/MadryLab/robustness/blob/master/robustness/datasets.py) | Author code specifies nine superclass label ranges and requires a local full ImageNet tree; no independent restricted-image archive is required. |
| `sb-syn` | family_only | public | [official](https://huggingface.co/vlmbias) | DeBiasLens authors link public synthetic releases; SB-Syn chart label may refer to these, but it is not automatically an alias of SBBench-Syn. |
| `sb-syn-crop` | family_only | public | [official](https://huggingface.co/vlmbias) | DeBiasLens author organization exposes crop-specific synthetic releases matching supplement counts. |
| `sbbench-syn` | family_only | public | [official](https://huggingface.co/vlmbias) | Paper supplement counts match two public HF noncrop datasets; a generic SBBench-Syn candidate spans age and gender configs. |
| `sbbench-syn-crop` | family_only | public | [official](https://huggingface.co/vlmbias) | Paper supplement counts match two public HF crop datasets; generic candidate is not one immutable collection. |
| `smolim2-135m-10b` | resolved | public | [official](https://huggingface.co/datasets/EleutherAI/SmolLM2-135M-10B) | The candidate spelling SmoLIM2 is a transcription error; author text corpus is a sampled 10B-token SmolLM2-135M pretraining mixture, used for transcoders. |
| `visu` | resolved | gated | [official](https://huggingface.co/datasets/aimagelab/ViSU-Text) | Author publishes a ViSU-Text repository listing but file access requires a manual institutional application; unsafe vision images are deliberately withheld. |
| `vqa-2-0` | resolved | public | [official](https://visualqa.org/download.html) | VQA 2.0 is original VQA v2 family; candidate paper does not specify exact split or image IDs. |
| `vqav2` | family_only | public | [official](https://visualqa.org/download.html) | This candidate accumulates multiple roles: evaluation, training, and survey mention; one paper uses 500 random images. |

## Acquisition and protocol leads

- `cifar10`: Reuse approved CIFAR-10 adapter after paper-specific split is chosen.
- `cifar100`: Reuse approved CIFAR-100 adapter after role-specific selection is chosen.
- `coco-2014`: Use existing COCO source only after task and split are pinned.
- `coco-train`: Ask for paper image IDs/year; existing COCO adapter can supply the verified base release.
- `cub200`: Do not alias CUB200 to the 2011 release without paper version evidence.
- `facial-expression-recognition-2013`: Source is verified; derived 500-example prompt selection needs authors' IDs/prompts.
- `fgvc`: Verify chart method/data appendix before mapping to FGVC-Aircraft.
- `flowers`: Choose Oxford Flowers variant before adapter reuse.
- `imagenet`: Resolve each paper role against ILSVRC year, split, and sample IDs.
- `imagenet-ilsvrc`: Keep training lineage separate from downloadable paper-specific records.
- `imagenet-segmentation`: Verify the author-linked MAT availability and original rights before adaptation.
- `imagenetval`: Obtain cited-study split definition before reusing an ImageNet adapter.
- `jiechieu-tsopze-resume-corpus`: Metadata-only text lead; privacy/rights assessment needed before any records or excerpts.
- `llava-instruct-150k-3a74a703`: Pin FineVision revision and paper sample manifest before adapting; 76.6 GB family is not a bounded preview.
- `ms-coco-7f846b38`: Require the ten paper image IDs for exact reproducibility.
- `ms-coco`: Resolve each paper role separately; preserve all mention receipts.
- `ms-coco-captions`: Annotation-only preview may be possible once split and caption selection are pinned.
- `mscoco`: Determine Karpathy/official retrieval split from AnyAttack implementation before adaptation.
- `ok-vqa`: Small annotation-only adapter lead; media depends on COCO release.
- `oxfordpet`: Public ~800 MB images plus annotations; bounded preview after source checksum and rights review.
- `restricted-imagenet`: Implement reproducible label mapping only on user-provided licensed ImageNet images.
- `sb-syn`: Use author noncrop datasets as leads; preserve age/gender distinction and candidate ID.
- `sb-syn-crop`: Use author crop datasets as leads, not unlicensed public preview media.
- `sbbench-syn`: Pin gender or age config and revision before an adapter.
- `sbbench-syn-crop`: Pin gender or age config and revision before an adapter.
- `smolim2-135m-10b`: Text-only source is public but too large for automatic full acquisition.
- `visu`: ViSU-Text needs author gate acceptance; no local preview is claimed. Unsafe vision remains withheld.
- `vqa-2-0`: Reuse active VQA v2 adapter only after paper split identified.
- `vqav2`: Do not collapse all paper selections into one preview; retain paper-role receipts.

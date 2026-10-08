# Dataset authorization links

Publisher/access routes refreshed 2026-10-07; local Hugging Face native-file checks are recorded separately from authorization claims.
Your local Hugging Face authorization has since enabled ImageNet-1K, Winoground,
SORRY-Bench and ZeroBench preparations. ViSU-Text’s original text release is prepared locally. Flickr30K's linked mirror is also prepared. Native BBQ-V Parquet and MMA-Diffusion image CSV requests still return HTTP 403 for the local account; their exact source populations remain separate identity questions.
The links below remain useful for a fresh installation and the remaining restricted
releases. Access approval and an implemented Atlas adapter are separate requirements. The coverage report
continues to list implementation gaps even for gated sources.

| Dataset | Where to request access | What to do |
| --- | --- | --- |
| Winoground | [facebook/winoground](https://huggingface.co/datasets/facebook/winoground) | Sign in to Hugging Face and accept the research-use conditions and contact-information sharing. The publisher reports automatic gating. |
| ViSU-Text | [aimagelab/ViSU-Text](https://huggingface.co/datasets/aimagelab/ViSU-Text) | Submit the access form with a verified institutional address. The publisher reviews requests manually. The broader ViSU corpus is a distinct identity; approval for this text release does not establish access to every image release. |
| SORRY-Bench | [sorry-bench/sorry-bench-202503](https://huggingface.co/datasets/sorry-bench/sorry-bench-202503) | Sign in and review the repository conditions. Its public metadata reports automatic gating. |
| ZeroBench | [jonathan-roberts1/zerobench](https://huggingface.co/datasets/jonathan-roberts1/zerobench) | Sign in and review the access conditions. This is the author-linked repository; its public metadata reports automatic gating. |
| ImageNet / ILSVRC 2012 | [ImageNet download and terms](https://www.image-net.org/download.php), [ILSVRC/imagenet-1k](https://huggingface.co/datasets/ILSVRC/imagenet-1k) | Create an account or sign in and request access for the needed release. The page also links the ILSVRC subset on Kaggle. |
| Flickr30K | [Author download instructions and request form](https://shannon.cs.illinois.edu/DenotationGraph/), [nlphuji/flickr30k mirror](https://huggingface.co/datasets/nlphuji/flickr30k) | Follow the form under Downloads for research/educational use. Image rights remain with the source owners. |
| FACET | [Meta FACET download/license page](https://ai.meta.com/datasets/facet-downloads/) | Review the dataset agreement and follow the publisher's access process. The live page did not expose the form in this check; no working form or Hugging Face mirror is asserted. |
| TIMIT | [LDC93S1 catalog and licensing](https://catalog.ldc.upenn.edu/LDC93S1) | Use your institution's LDC entitlement, or register and follow the licensing instructions. This can involve a fee; Atlas has not purchased it. |
| Google Web 1T | [LDC2006T13 catalog and agreement](https://catalog.ldc.upenn.edu/LDC2006T13) | Use your institution's LDC entitlement or follow the publisher's licensing instructions. The applicable fee is shown after login. |
| COCO demographic overlay | [Princeton author page and Annotations request form](https://princetonvisualai.github.io/imagecaptioning-bias/) | Follow the Annotations link to request this overlay. Approval for the overlay is distinct from the underlying COCO image release. |
| MS-CXR | [PhysioNet MS-CXR 1.1.0](https://physionet.org/content/ms-cxr/1.1.0/) | Obtain individual PhysioNet credentialing, complete the required training, and sign the data-use agreement. The underlying MIMIC-CXR images have their own access requirements. [Credentialing FAQ](https://physionet.org/about/faqs/) explains the process. |
| CelebA identity annotations | [Official author page and contact instructions](https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html) | The author releases face identities upon request. Public images, attributes and split files have separate non-commercial research terms and prohibit redistribution; an image-only mirror does not establish a complete native annotation join. |
| Chicago Face Database | [Official download request](https://www.chicagofaces.org/download/) | Complete the request form for the named release and review its use terms. |
| GYAFC | [Author repository](https://github.com/raosudha89/GYAFC-corpus) | Follow the current README access instructions for the underlying Yahoo Answers material. This check did not verify a working request form. |
| FER-2013 | [Official Kaggle competition data](https://www.kaggle.com/c/challenges-in-representation-learning-facial-expression-recognition-challenge/data) | Sign in and review the competition's data terms. Availability for your account was not checked. |
| Ring-A-Bell nudity InvPrompts | [Chia15/RingABell-Nudity](https://huggingface.co/datasets/Chia15/RingABell-Nudity); the authors' [repository](https://github.com/chiayi-hsu/Ring-A-Bell) names it as the release | Sign in to Hugging Face and accept the dataset conditions (automatic gating). Atlas prepares it with your local token; it never accepts terms for you. Content is adversarial text about explicit imagery and stays local. |
| MultiTrust benchmark suite | [thu-ml/MultiTrust](https://huggingface.co/datasets/thu-ml/MultiTrust) (CC BY-SA 4.0) | Sign in and accept the conditions (automatic gating). Atlas can list its 10,549 files with your account but has no per-task adapters yet, so this is an implementation gap, not an access block. |
| SBBench / current BBQ-V photographic release | [ucf-crcv/BBQ-V](https://huggingface.co/datasets/ucf-crcv/BBQ-V) and [author instructions](https://github.com/UCF-CRCV/BBQ-Vision) | Request access to the author-linked current release. Its membership differs from historical SBBench; approval does not resolve that difference. The separately prepared synthetic variants do not grant access to this photographic population. |
| MMA-Diffusion benchmark candidate | [Text benchmark](https://huggingface.co/datasets/YijunYang280/MMA-Diffusion-NSFW-adv-prompts-benchmark) and [image benchmark](https://huggingface.co/datasets/YijunYang280/MMA_Diffusion_adv_images_benchmark) | Follow the two author-linked Hugging Face access processes. The exact corpus-mentioned population remains a candidate identity; do not assume that approval for one release covers the other. |
| RAISE-1K | [Publisher request form](https://loki.disi.unitn.it/RAISE/confirm.php?package=1k) | Supply your name, affiliation and email, describe the project, and review/accept the research and education terms. Native RAW/TIFF/CSV integration remains separate implementation work. |
| ROSMAP candidate | [RADC Research Resource Sharing Hub](https://www.radc.rush.edu/) | Create an account and use Request Data/Specimens for the needed clinical or omics population. Data-use agreements and the exact citing-paper cohort still need reconciliation. |
| Unnamed synthetic spatial training population | [Author data requirements](https://github.com/Raphoo/linear-mech-vlms/blob/main/spatial_finetuning/README.md) | The README asks researchers to contact the author for the large synthetic Objaverse training archive. This is distinct from the publicly linked COCO-Spatial validation release. |

After approval, use a local Hugging Face login or a local read token for the
approved account; do not put tokens in registry YAML, receipts, or chat. Atlas's
Hugging Face credential profile can read the existing local token. For locally
downloaded licensed files, keep them in one directory and register their paths
with `atlas datasets add`; format-specific mappings may still be required.

No request, agreement acceptance, purchase, or message to a publisher was made
on your behalf. Publication remains restricted to the already approved packs.

The catalogue's ImageNet, ILSVRC, ImageNet100, validation and Restricted ImageNet
entries share a base access route, but have distinct membership questions. The
unnamed CFD/MORPH candidate should start with the CFD publisher above; its exact
derived population and any additional source entitlement remain unresolved.

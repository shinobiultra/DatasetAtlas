# Corpus coverage

Generated from the local read-only corpus on 2026-09-22T03:50:44.831124+00:00.
Full extracted paper text and candidate queues remain in ignored `work/corpus/`.

## Observed inventory

- Files inventoried: **83** (67 PDFs, 15 HTML snapshots, 1 RIS export).
- RIS records: **64**; distinct linked paper IDs: **64**. The RIS is a cross-check, not a required count.
- PDF pages reported by `pdfinfo`: **1533**; sparse-text pages: **7**; separately, **206** numeric/table-heavy pages retain extracted text.
- Files with extraction failure: **0**; HTML snapshots with no usable visible text: **15**.
- Byte-identical duplicate hash groups: **0**. Different PDF versions retain separate hashes and page counts.
- Automated candidate occurrences: **4028**; candidate name groups: **1149**. These are noisy search leads, **not a dataset count or accepted records**.
- Candidate occurrences uniquely matching a registry alias whose identity is resolved: **706**. Alias matching alone does not accept the mention or verify its role.
- Pending review items: **0**; agent-complete full-text mention inventories: **64**; human-approved papers: **0**.

## Paper outcomes

- `extraction_failed`: 0
- `no_dataset_mentions_found_after_review`: 0
- `processed`: 64
- `processed_with_review_items`: 0
- `unavailable`: 0

`processed_with_review_items` means extraction finished but one or more specific queue items remain. A paper with zero detected candidates is **not** marked `no_dataset_mentions_found_after_review` until its full-text mention inventory is checked.

## Candidate role labels

- `bibliography-only reference`: 875 automated occurrences
- `derived collection`: 106 automated occurrences
- `evaluation`: 829 automated occurrences
- `introduction`: 156 automated occurrences
- `related-work mention`: 17 automated occurrences
- `training`: 276 automated occurrences
- `unclassified`: 1769 automated occurrences

Role labels above are automated context heuristics, particularly unreliable for two-column PDFs. Curated roles below come from page review.

## Page-located reviewed evidence

- Page-checked assertions: **602** across **63** papers, covering **342** candidate names or explicitly unnamed collections.
- Conservatively grouped candidate identities: **332**; no corpus audit assertion alone verifies a release.
- Confirmed identity alias redirects: **6**. All original page receipts remain attached to canonical proposals; paper-specific splits and roles are retained.
- Receipts are in ignored `work/corpus/curated_dataset_evidence.jsonl`; grouped identity proposals are in `work/corpus/curated_dataset_candidates.json`.
- Page-checked assertions establish only their cited claims. A complete mention inventory requires `mention_inventory_review_complete`; original dataset source and release verification are separate.

## Paper-by-paper audit

| Paper ID | Title | PDFs | Candidate mentions | Outcome | Mention inventory |
| --- | --- | ---: | ---: | --- | --- |
| `paper-08e415961919a492` | Deep Image Prior | 1 | 19 | `processed` | agent inventory checked |
| `paper-09b2d7393fc75cf7` | Architectural Backdoors in Vision-Language Model Supply Chains via Representation Steering | 1 | 94 | `processed` | agent inventory checked |
| `paper-12e8bd34b4a2f2a8` | Visual Adversarial Examples Jailbreak Aligned Large Language Models | 1 | 53 | `processed` | agent inventory checked |
| `paper-164d7c221452ffec` | Biases Propagate in Encoder-based Vision-Language Models: A Systematic Analysis From Intrinsic Measures to Zero-shot Retrieval Outcomes | 1 | 114 | `processed` | agent inventory checked |
| `paper-1e2474b15fec2d7d` | Controversial stimuli: pitting neural networks against each other as models of human recognition | 1 | 246 | `processed` | agent inventory checked |
| `paper-2038cb87115b4fb0` | What Do VLMs NOTICE? A Mechanistic Interpretability Pipeline for Gaussian-Noise-free Text-Image Corruption and Evaluation | 1 | 116 | `processed` | agent inventory checked |
| `paper-208c53a35b62bc52` | Reliable evaluation of adversarial robustness with an ensemble of diverse parameter-free attacks | 1 | 110 | `processed` | agent inventory checked |
| `paper-20de77d4e60fd1bd` | Seeing Is Believing? A Benchmark for Multimodal Large Language Models on Visual Illusions and Anomalies | 1 | 203 | `processed` | agent inventory checked |
| `paper-24b951c4e4ec2d31` | Vision-Default, Prior-Override: Causal Mechanisms of Perception-Knowledge Conflict in Vision-Language Models | 1 | 18 | `processed` | agent inventory checked |
| `paper-25eaa8c74ce76800` | A Survey on Mechanistic Interpretability for Multi-Modal Foundation Models | 1 | 116 | `processed` | agent inventory checked |
| `paper-29349603429218b8` | Self-interpreting Adversarial Images | 1 | 39 | `processed` | agent inventory checked |
| `paper-2aa40aa13ed2a25b` | Linear Mechanisms for Spatiotemporal Reasoning in Vision Language Models | 1 | 37 | `processed` | agent inventory checked |
| `paper-2ae8012d97e5e3da` | Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability | 2 | 18 | `processed` | agent inventory checked |
| `paper-2c07a8c6af8e33c2` | SemVink: Advancing VLMs' Semantic Understanding of Optical Illusions via Visual Global Thinking | 1 | 28 | `processed` | agent inventory checked |
| `paper-2df1203e2d3767bb` | PHANTOM: A Large-Scale Dataset of Multimodal Adversarial Attacks for Vision-Language Models | 1 | 213 | `processed` | agent inventory checked |
| `paper-32cea5e43d940514` | Interpretable Debiasing of Vision-Language Models for Social Fairness | 1 | 135 | `processed` | agent inventory checked |
| `paper-347b77231e69b630` | Illusory size determines the perception of ambiguous apparent motion | 1 | 19 | `processed` | agent inventory checked |
| `paper-392b0c393c06b48e` | Investigating Adversarial Robustness of Multi-modal Large Language Models | 1 | 146 | `processed` | agent inventory checked |
| `paper-3aa07dc1c7bc37d9` | Multilevel Interpretability Of Artificial Neural Networks: Leveraging Framework And Methods From Neuroscience | 1 | 9 | `processed` | agent inventory checked |
| `paper-3e0db9c633ab204c` | Double Visual Defense: Adversarial Pre-training and Instruction Tuning for Improving Vision-Language Model Robustness | 1 | 97 | `processed` | agent inventory checked |
| `paper-4f53de240f8fc1af` | Illusory Motion Reproduced by Deep Neural Networks Trained for Prediction | 1 | 13 | `processed` | agent inventory checked |
| `paper-52015222b27e7099` | Gradients in the biophysical properties of neonatal auditory neurons align with synaptic contact position and the intensity coding map of inner hair cells | 1 | 11 | `processed` | agent inventory checked |
| `paper-63c3bd849356e00f` | Adversarial Examples Are Not Bugs, They Are Features | 1 | 122 | `processed` | agent inventory checked |
| `paper-666de2b7486d80a3` | The Unreasonable Effectiveness of Deep Features as a Perceptual Metric | 1 | 61 | `processed` | agent inventory checked |
| `paper-6a7364738bac9f07` | IllusionBench+: A Large-scale and Comprehensive Benchmark for Visual Illusion Understanding in Vision-Language Models | 1 | 96 | `processed` | agent inventory checked |
| `paper-6c99cf73401b37d4` | Pathways of Visual Information Flow in Vision-Language Models | 1 | 116 | `processed` | agent inventory checked |
| `paper-6d747c88d639c5aa` | Metamers of neural networks reveal divergence from human perceptual systems | 1 | 35 | `processed` | agent inventory checked |
| `paper-6dbb0d4a7b949143` | Robust-LLaVA: On the Effectiveness of Large-Scale Robust Image Encoders for Multi-modal Large Language Models | 1 | 181 | `processed` | agent inventory checked |
| `paper-72040eccb96ead7a` | Excessive Invariance Causes Adversarial Vulnerability | 1 | 30 | `processed` | agent inventory checked |
| `paper-728d8c0964b540ad` | Intriguing properties of neural networks | 1 | 29 | `processed` | agent inventory checked |
| `paper-7531668a4a39f304` | Prisma: An Open Source Toolkit for Mechanistic Interpretability in Vision and Video | 1 | 5 | `processed` | agent inventory checked |
| `paper-765a2362f8735bc4` | Unveiling the "Fairness Seesaw": Discovering and Mitigating Gender and Race Bias in Vision-Language Models | 1 | 91 | `processed` | agent inventory checked |
| `paper-78a318ad1ec346ef` | Towards Evaluating the Robustness of Neural Networks | 1 | 90 | `processed` | agent inventory checked |
| `paper-79f7a50cea22ddab` | Understanding Deep Image Representations by Inverting Them | 1 | 6 | `processed` | agent inventory checked |
| `paper-7a1ff5996ce95273` | AnyAttack: Towards Large-scale Self-supervised Adversarial Attacks on Vision-language Models | 1 | 37 | `processed` | agent inventory checked |
| `paper-7ed1979562251931` | QAVA: Query-Agnostic Visual Attack to Large Vision-Language Models | 1 | 88 | `processed` | agent inventory checked |
| `paper-80b7ba2e277a20c5` | SMSP: A Plug-and-Play Strategy of Multi-Scale Perception for MLLMs to Perceive Visual Illusions | 1 | 85 | `processed` | agent inventory checked |
| `paper-8729802cb62942f0` | Mechanistic? | 1 | 5 | `processed` | agent inventory checked |
| `paper-9036b4eaa048dc21` | Sparse Autoencoders Learn Monosemantic Features in Vision-Language Models | 2 | 107 | `processed` | agent inventory checked |
| `paper-944952997d24ce45` | Attention! Your Vision Language Model Could Be Maliciously Manipulated | 1 | 51 | `processed` | agent inventory checked |
| `paper-959e8fc51787f7e4` | Circuit Tracing in Vision-Language Models: Understanding the Internal Mechanisms of Multimodal Thinking | 1 | 16 | `processed` | agent inventory checked |
| `paper-a291f2908480a2f8` | On Evaluating Adversarial Robustness of Large Vision-Language Models | 1 | 51 | `processed` | agent inventory checked |
| `paper-a2c6dc42af089fd5` | Towards Deep Learning Models Resistant to Adversarial Attacks | 1 | 62 | `processed` | agent inventory checked |
| `paper-a47845c66d4a3f48` | RobustBench: a standardized adversarial robustness benchmark | 1 | 150 | `processed` | agent inventory checked |
| `paper-a4d86f421f531623` | Mechanistic Interpretability Needs Philosophy | 2 | 3 | `processed` | agent inventory checked |
| `paper-ab31cc6a994470fb` | Adversarial Examples that Fool both Computer Vision and Time-Limited Humans | 1 | 14 | `processed` | agent inventory checked |
| `paper-ad50206beabc5a94` | Could a Neuroscientist Understand a Microprocessor? | 1 | 8 | `processed` | agent inventory checked |
| `paper-b039401c04ff9b91` | Grounding Visual Illusions in Language: Do Vision-Language Models Perceive Illusions Like Humans? | 1 | 20 | `processed` | agent inventory checked |
| `paper-b8a3bbfe3c7eefff` | Adversarial Examples Are Not Easily Detected: Bypassing Ten Detection Methods | 1 | 64 | `processed` | agent inventory checked |
| `paper-c12960e5d652fb7f` | EigenShield: Causal Subspace Filtering via Random Matrix Theory for Adversarially Robust Vision-Language Models | 1 | 55 | `processed` | agent inventory checked |
| `paper-c65ee35ca47313c9` | Bias in Gender Bias Benchmarks: How Spurious Features Distort Evaluation | 1 | 127 | `processed` | agent inventory checked |
| `paper-c941465e4095dbe8` | Position: An Inner Interpretability Framework for AI Inspired by Lessons from Cognitive Neuroscience | 1 | 7 | `processed` | agent inventory checked |
| `paper-d0229a9d15fd6b77` | Obfuscated Gradients Give a False Sense of Security: Circumventing Defenses to Adversarial Examples | 1 | 35 | `processed` | agent inventory checked |
| `paper-d098a79f00c8b2b5` | Open Problems in Mechanistic Interpretability | 1 | 37 | `processed` | agent inventory checked |
| `paper-d8a392188b9cf4d6` | Sparse Autoencoders as Plug-and-Play Firewalls for Adversarial Attack Detection in VLMs | 1 | 25 | `processed` | agent inventory checked |
| `paper-ebd63da316af82e5` | Implicit Inversion turns CLIP into a Decoder | 1 | 12 | `processed` | agent inventory checked |
| `paper-ed38cc9d6f4b163c` | Towards a Novel Perspective on Adversarial Examples Driven by Frequency | 1 | 21 | `processed` | agent inventory checked |
| `paper-f03c5ad315e6d835` | Revealing and Reducing Gender Biases in Vision and Language Assistants (VLAs) | 1 | 123 | `processed` | agent inventory checked |
| `paper-f2bfbdff3e79479c` | The Hydra Effect: Emergent Self-repair in Language Model Computations | 1 | 16 | `processed` | agent inventory checked |
| `paper-f5da3ca03780a203` | Grounding-Driven Attack: Improving Encoder-based Adversarial Transferability against Large Vision-Language Models | 1 | 26 | `processed` | agent inventory checked |
| `paper-f6dcb0e50d10ea38` | Laundering AI Authority with Adversarial Examples | 1 | 5 | `processed` | agent inventory checked |
| `paper-f7fa96d778a8d649` | Explaining and Harnessing Adversarial Examples | 1 | 33 | `processed` | agent inventory checked |
| `paper-fdcf898e0b05daff` | Adversarial Attacks on Multimodal Large Language Models: A Comprehensive Survey | 1 | 13 | `processed` | agent inventory checked |
| `paper-fe221c51b8ea09df` | Explorations of Self-Repair in Language Models | 1 | 16 | `processed` | agent inventory checked |

## Outstanding limits

- All linked papers have agent-complete full-text mention inventories. The automated extractor remains a noisy search aid: it can miss a novel name or mistake a model, title, metric, or author for a dataset. Human approval is tracked separately and is not a required signoff.
- The 15 SingleFile HTML captures are arXiv PDF-viewer shells with no standalone visible article text. Their linked PDFs were independently extracted and reviewed; each shell is documented in the quality queue.
- The seven genuinely sparse-text PDF pages were visually checked. The 206 numeric/table-heavy pages retained substantial extracted text and were covered by the full-paper audits; the quality queue records page-specific visual/OCR checks where needed.
- No candidate is marked accepted, no dataset identity or original release is verified by this automated pass, and no source-access or preview claim follows from this report.

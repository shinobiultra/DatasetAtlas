# Model-server runs and chat with a dataset

Two things use a model server on your own machine (vLLM, Ollama, LM Studio, llama.cpp, SGLang): **batch runs** that ask a
model something about every record of a selection, and **retrieval** that finds the records worth asking about. Both
send dataset contents only to a server on this machine; see [Model connections](model-connections.md) for adding one.

## Batch runs

| Analysis | Asks | Stored as |
| --- | --- | --- |
| `vlm.answer` | a question about each record, with its image if you tick it | text column `answer`, token and latency arrays |
| `vlm.tag` | a fixed set of fields (one of a list, text, yes/no, number) | one typed column per field |
| `vlm.judge` | whether a saved answer matches the reference answers | text column `verdict` (`correct`, `incorrect`, `unsure`), int8 `correct` (1, 0, or -1 for unsure) |
| `embed.api` | the server's `/v1/embeddings` for each record's question or text | `vector`, unit length, with an embedding space |
| `score.vqa_accuracy` | nothing (no model is called) | float32 `accuracy`, with a summary |

They appear in **Analyze** under "Ask a model server" and "Score saved results". A run is estimated first: the estimate shows how many requests go to which model and the **exact
prompt for the first record**, and sends nothing. Results are columnar (see [Analysis at scale](analysis-at-scale.md)),
so 200,000 answers are a few files and not 200,000 JSON items, and they join onto records as
`prediction.<artifact>.answer` for the table, filters and colours.

A server that is not on this machine is refused with a message saying so. The check is on the configured address
(`localhost`, `127.0.0.0/8` or `::1`); an external provider with `allow_external` still cannot receive a batch run.

### Servers and prompts

OpenAI-compatible servers are spoken to through `/v1/chat/completions` and `/v1/embeddings`. When the address is an
Ollama server (`/api/version` answers) Atlas uses Ollama's native `/api/chat` instead, because it is the only way to
turn thinking off (`think: false`), bound the reply (`num_predict`) and request structured output (`format`) reliably.

A prompt is a template. Placeholders: `{question}`, `{text}`, `{choices}`, `{candidate}` (the saved answer being
judged), `{reference}`, and `{field:source.name}` for any record field. Only the fields a template names are frozen
into the run, so a 200k-record run does not carry whole records. `thinking` (model default, off, on), the reply token
limit and the number of parallel requests are set per run; requests are retried when the server answers busy or with a transient error (HTTP 408, 425, 429, 5xx).

Model-dependent failure modes remain explicit:

- A *thinking* model (for example `qwen3-vl:8b` under Ollama) can spend its whole reply budget reasoning and return no
  answer. The record fails with "The model spent its whole token budget reasoning and replied with nothing"; turn
  thinking off, raise the limit, or use a non-thinking variant.
- Some models ignore a JSON schema passed as a response format (`qwen3.5` under Ollama). The schema is therefore also
  spelled out in the prompt (`spell_out_schema`, on by default), and every reply is validated against it regardless. A
  reply that does not fit is a failed record with a reason, never a guess.

Every record is accounted for: it has a result, or it is skipped as not applicable (no question, no saved answer) or
failed, with the reason kept. The finished run lists those reasons, token totals and mean latency, and for a judge or
tag run the verdict or value spread.

### Tags and verdicts

Tag fields are named in lower case (`topic`, `contains_text`), each one of: *one of* a list of 2–64 values, free text,
yes/no or a number. Judge runs read the answers from a saved `vlm.answer` run (the form lists runs that have a text
column over the same records) and compare them with a reference field such as the human answers. A verdict is the
model's opinion; the `correct` column is not accuracy against anything, and a judge run is worth checking against
hand-labelled records before it is trusted.

### Embeddings from a server

`embed.api` stores unit-length vectors, so cosine distance is a dot product. Retrieval models often want a prefix:
`document_prefix` (for example `passage: `) is added to every stored text and is **part of the space's identity**,
because it changes the vectors; `query_prefix` (`query: `) is added to a search text only and is not. The space is
named by model, what was embedded and the document prefix, so two runs of the same recipe are the same space.

### VQA accuracy

`score.vqa_accuracy` implements the official VQA rule (as in the `vqaEval.py` of the VQA release, reimplemented here and
checked against hand-computed cases): for each of a question's human answers leave that annotator out, score
`min(1, matching answers among the others / 3)`, and average. Answers are normalised (case, punctuation, number words,
articles, contractions) only when the human answers disagree, as the official script does. The summary gives mean
accuracy and the same by question type and answer type. Scoring needs saved answers (a `vlm.answer` run) and the human
answers in `source.answers`.

## Chat with a dataset

**Ask the dataset** (in the bottom bar when nothing is selected; **Ask model** once something is) opens the chat panel. It does retrieval
first, then the usual reviewed chat:

1. Pick an embedding space, type a question or topic, choose how many records to retrieve (up to 20) and press
   **Retrieve**. Atlas runs an exact nearest-neighbour search over the records the current filters match (the whole
   population, not a sampled page) and lists the hits with their distance and text.
2. Untick any hit you do not want and press **Attach**. The ticked records become the chat's selected records and the
   message box is filled with your question plus an instruction to answer only from the attached records and cite each as
   `[record:<id>]`. Edit it freely.
3. **Review what will be sent** shows the exact outgoing context and its digest; **Send** answers only for that digest.
   Citations of records outside the attached set are rejected, and a model that is not given the answer says so.

Retrieval chooses candidate records before context approval. Everything the model receives remains inside the approved scope. Optional read-only tools can inspect only that approved selection; they cannot expand it to other dataset records.

A text query works against MiniLM and SigLIP 2 spaces (a SigLIP 2 image space is searched with its text encoder) and
against a model-server space: the query is embedded by the same server and model with the space's `query_prefix`, and
is refused if that provider id now serves a different model or its vectors differ in dimension. Imported vectors have no
encoder, so they can be searched only by an example record.

## Moving finished runs between workspaces

`atlas runs import <other workspace or its work/ folder> <run id>` verifies and copies one finished run, array results
and all, into this workspace, for example a run computed on a cluster. Every file is hashed while it is copied against
the checksum in the artifact's manifest; the frozen selection, the item keys, each record's outcome and the artifact's
identity are re-derived from the run's own configuration, and nothing is registered unless all of it checks out. A
symbolic link, a changed array, a mismatched receipt or an unfinished run is refused and leaves no files behind.
Importing the same run again changes nothing. The workbench must not be running (it holds the workspace's coordinator
lock). An imported run keeps the identity of the embedding it was computed from but not that embedding's vectors; to project or
cluster again here, import or compute the embedding too.

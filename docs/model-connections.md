# Model connections in the local workbench

Model connections are optional. Static browsing and local queries do not contact a model server. The workbench mounts `create_provider_router(service)` under `/api/v1`; configuration and conversations are local state. Never put an API key in a request or configuration file. `api_key_env` names an environment variable whose value is read only for a provider request.

```python
from pathlib import Path
from dataset_atlas.providers import ProviderService, create_provider_router

service = ProviderService(
    config_path=Path("local-config/providers.json"),
    record_lookup=lookup_canonical_record,  # (record_id) -> Record | None
    image_roots=[Path("/approved/media/root")],
    tool_backend=None,                       # tools remain unavailable until wired
    external_record_policy=None,             # external dataset sends fail closed
)
app.include_router(create_provider_router(service), prefix="/api/v1")
```

The provider configuration accepts an explicit HTTP(S) base URL with no credentials, query, fragment, or path other than `/v1`. Plain HTTP is limited to loopback addresses. An external endpoint needs HTTPS and `allow_external=true`. The client sends only to the configured `/v1/chat/completions` or `/v1/embeddings` paths, rejects redirects, and does not use environment proxies. The service persists only the environment variable name, never its value. LM Studio and vLLM can use the same compatible interface; each actual server and model combination needs its own capability tests. External dataset transmission also needs an `external_record_policy(record, context)` callback to approve every selected record and representation. Without one, preview reports `external_send_allowed=false` and sending is refused. A publication right alone does not imply permission to send data to an external model.

`POST /providers/{id}/probe` sends only benign synthetic prompts and a tiny synthetic pixel. It independently records `unknown`, `supported`, or `unsupported` for text generation, one image, multiple images, structured output, tool calls, text embeddings, and image embeddings. A transport or authentication failure leaves the capability unknown. It never sends a dataset record. Probes should be run only after a user configures the provider; there is no automatic discovery or startup probe. A changed configuration resets results to unknown. The probes are compatibility checks, not a benchmark or proof of semantic quality.

Batch runs over a whole selection (answers, tags, verdicts, embeddings) and chat with retrieval are described in
[Model-server runs and chat with a dataset](model-server-runs.md). Only loopback servers can receive a batch run.

Conversation flow:

1. The user selects exact record IDs, provider, mode, optional fields, and optional image asset IDs.
2. `POST /conversations/context` returns the exact outgoing message parts, a SHA-256 context digest, image representation details, policy, and notices. This step makes no provider request. A text-only context explicitly says that images are unavailable.
3. `POST /conversations` includes the original context request, digest, `approved_provider_id`, ordered `approved_record_ids`, and prompt. The service rebuilds the context from current canonical records and image bytes. Any changed digest or approval scope rejects the send.
4. The response and its input receipt are saved in a mode-0600 local JSONL file. The receipt includes model, IDs, prompt, settings, exact outgoing context, known client image handling, provider response/error, and usage when the server supplies it. Provider-side preprocessing is marked unknown.

Exploration may include explicitly selected `source.*`, `prediction.*`, or `human.*` scalar fields and annotations. Filenames, labels, and model predictions are absent by default. Evaluation rejects all auxiliary fields and annotations in code; its base inputs are text, question, choices, and explicitly selected image bytes. For more than one evaluation record, `independent_records=true` is mandatory. The preview then has `delivery="independent"` and `per_record_contexts`, each with its own exact outgoing message; the provider receives one request per record. Exploratory tools are disabled in evaluation and for external providers because their future output cannot be shown in the initial exact-context preview. The service never sends a local image path or fetches a remote image URL. Requested images must belong to the selected records, resolve inside an approved local root, use PNG/JPEG/WebP, be at most 5 MB each, and have a supported image capability for the configured model-server combination.

Read-only tools are optional. To enable them, supply a trusted `tool_backend(name, arguments, approved_ids, remaining_rows) -> ToolResult` using the same query and media services as the frontend. It may implement only `describe_dataset`, `describe_fields`, `search_records`, `get_records`, `aggregate`, `inspect_images`, and `get_run_results`. The dispatcher rejects unknown tools, unknown argument keys, out-of-scope record IDs, extra rows, absent coverage/scope, and evaluation fields. A result must declare `population_scope="approved_selection"`, include coverage and stable source references, and return only approved record rows. Tool receipts get deterministic IDs that the model can cite. `inspect_images` can return allowed metadata; image bytes must be selected through the inspected context. The model cannot start jobs, download, export, run code, read arbitrary files, issue SQL, or select network destinations.

For a local exploration request, `use_tools=true` enables automatic model choice. An optional `required_tool` from the seven-name allowlist forces that one tool on the first model iteration; later iterations use automatic choice. The same scope, call, row, and deadline checks apply outside the model.

Limits are 8 model iterations, 16 tool calls, 1,000 total returned rows, 8 selected images or the provider's lower configured limit, 100 KB per tool result, and an explicit conversation deadline of at most 120 seconds. A provider configuration also bounds input characters, output tokens per iteration, and per-request timeout. These are application safeguards, not provider limits. The service cannot guarantee a monetary cap for externally billed APIs because their pricing and server-side accounting are unknown; the UI must display that spending is not bounded by Atlas. In a deployment where a hard spending cap is needed, keep external providers disabled until billing-side limits are available.

Independent evaluation batches accept at most 100 ordered record IDs and eight total transmitted images, including repeated images across records. A batch has one approval digest over the exact separate contexts and the configured endpoint. The request's `max_batch_completion_tokens` (default 8,192) reserves the provider's per-record output limit before each send; the 120-second deadline and token budget apply to each invocation. Results and progress are saved after each record. Repeating the same approved POST resumes pending records and skips successful ones; a changed record, image, provider endpoint, or model invalidates the digest. `GET /conversation-batches/{batch_id}` returns saved progress. `GET /conversations` lists saved interactions, and `GET /conversations/{id}` returns a complete receipt with the exact “Input sent” context. A completed batch means every separate request returned without a transport or citation error; it does not claim predictions are correct.

All mutation routes require `X-Atlas-Request: 1` and reject a mismatched `Origin`. The host workbench still needs its usual loopback binding and origin/host protections. The record resolver and trusted tool backend must enforce access to the selected records; the provider layer additionally checks the exact approved IDs and rejects tool outputs outside that scope.

## Configure and verify a local provider

Install a compatible local server separately and choose its explicit loopback
address/model in Settings. Atlas does not discover or start a model service.
`scripts/setup-local-vlm.sh` and `scripts/start-local-vlm.sh` provide an optional
isolated, pinned server workflow; inspect its resource settings and local model
requirements before running it. A prepared environment or cached weights do not
mean that a server is currently available.

Run the benign capability probe for that exact configured server and model.
Unsupported endpoints remain unavailable, and transport failures remain unknown.
Then preview an exact context before authorizing a dataset interaction. Empty or
output-limited answers retain their provider stop reason and are errors rather
than successful predictions.

The [current release evidence](../reports/release_evidence.md) distinguishes fresh
controlled regression checks from retained historical model demonstrations. A
historical interaction binds its original snapshot, selected records, context
digest, model/settings and saved output. It does not establish current server
availability or model accuracy. Keep exact contexts and credentials in private
workspace storage; public release summaries contain only the necessary aggregate
provenance.

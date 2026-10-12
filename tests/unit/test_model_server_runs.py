"""Model-server runs: the VQA metric, prompts and replies, the loopback client, the processors, and a run through the API."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Asset, Record
from dataset_atlas.processors import run_processor
from dataset_atlas.storage import arrays as store
from dataset_atlas.vlm import client as model_client
from dataset_atlas.vlm import tasks, vqa

HEADERS = {"X-Atlas-Request": "1"}


# --- a fake model server ---------------------------------------------------------

class FakeServer:
    """Answers the OpenAI-compatible and the Ollama-native endpoints, and records what it was sent."""

    def __init__(self, *, ollama: bool = False):
        self.ollama = ollama
        self.requests: list[tuple[str, dict]] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.fail_first = 0
        self.always_status: int | None = None
        self.reply = self.default_reply
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, status, body):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                if self.path == "/api/version" and outer.ollama:
                    return self.send(200, {"version": "0.0-test"})
                self.send(404, {"error": "not found"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with outer.lock:
                    outer.requests.append((self.path, body))
                    outer.in_flight += 1
                    outer.max_in_flight = max(outer.max_in_flight, outer.in_flight)
                    failing = outer.fail_first > 0
                    outer.fail_first = max(0, outer.fail_first - 1)
                try:
                    time.sleep(0.03)
                    if outer.always_status:
                        return self.send(outer.always_status, {"error": {"message": "refused: " + json.dumps(body)[:40]}})
                    if failing:
                        return self.send(503, {"error": {"message": "busy"}})
                    if self.path.endswith("/embeddings"):
                        rows = [{"index": i, "embedding": [float(len(text)), 1.0, 0.0, float(i % 3)]} for i, text in enumerate(body["input"])]
                        return self.send(200, {"data": rows[::-1]})  # out of order on purpose
                    text = outer.reply(body)
                    if self.path == "/api/chat":
                        return self.send(200, {"message": {"role": "assistant", "content": text}, "done_reason": "stop", "prompt_eval_count": 11, "eval_count": 3})
                    return self.send(200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 11, "completion_tokens": 3}})
                finally:
                    with outer.lock:
                        outer.in_flight -= 1

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @staticmethod
    def prompt(body: dict) -> str:
        message = body["messages"][-1]
        content = message["content"]
        return content if isinstance(content, str) else next(part["text"] for part in content if part["type"] == "text")

    @staticmethod
    def default_reply(body: dict) -> str:
        text = FakeServer.prompt(body)
        if "verdict" in json.dumps(body):
            return json.dumps({"verdict": "correct" if "Proposed answer: red" in text else "incorrect"})
        if "category" in json.dumps(body.get("format") or body.get("response_format") or ""):
            return json.dumps({"category": "colour" if "color" in text else "count", "confident": True, "score": 0.5})
        return "Answer: Red." if "color" in text else "two"

    @property
    def provider(self) -> dict:
        return {"id": "fake", "base_url": f"http://127.0.0.1:{self.port}/v1", "model": "fake-model", "timeout_seconds": 10, "max_output_tokens": 64,
                "max_input_characters": 4000, "max_images": 2}

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    fake = FakeServer()
    yield fake
    fake.close()


@pytest.fixture
def ollama():
    fake = FakeServer(ollama=True)
    yield fake
    fake.close()


def pictures(directory: Path, count: int) -> list[Record]:
    rng = np.random.default_rng(0)
    records = []
    for index in range(count):
        path = directory / f"p{index}.jpg"
        Image.fromarray((rng.random((90, 120, 3)) * 255).astype(np.uint8)).save(path)
        records.append(Record(id=f"q{index}", dataset_id="d", release_id="r", snapshot_id="s", question="What color is it?" if index % 2 == 0 else "How many are there?",
                              assets=[Asset(id=f"a{index}", dataset_id="d", release_id="r", modality="image", uri=str(path))],
                              source={"answers": [{"answer": "red", "answer_id": i} for i in range(10)] if index % 2 == 0 else [{"answer": "2", "answer_id": i} for i in range(10)],
                                      "question_type": "what color" if index % 2 == 0 else "how many", "answer_type": "other" if index % 2 == 0 else "number"}))
    return records


# --- VQA accuracy ----------------------------------------------------------------

def test_vqa_accuracy_follows_the_official_formula():
    assert vqa.vqa_accuracy("red", ["red"] * 10) == 1.0
    assert vqa.vqa_accuracy("blue", ["red"] * 10) == 0.0
    # Leaving out any one human, at least three of the others still say red, so every subset gives full credit.
    assert vqa.vqa_accuracy("red", ["red"] * 4 + ["blue"] * 6) == 1.0
    # One other human says blue for the red and the green humans (1/3 each, eight green plus one red) and none for the blue human: 9/3 over 10.
    assert vqa.vqa_accuracy("blue", ["red", "blue"] + ["green"] * 8) == pytest.approx(0.3)
    # Two red humans each see one other red (1/3); the blue and the seven green humans see two (2/3): (2/3 + 2/3 + 14/3) / 10.
    assert vqa.vqa_accuracy("red", ["red", "red", "blue"] + ["green"] * 7) == pytest.approx(0.6)


def test_normalisation_applies_only_when_the_humans_disagree():
    # Unanimous humans: compared as written, so a capital letter does not match.
    assert vqa.vqa_accuracy("yes", ["Yes"] * 10) == 0.0
    # Disagreement switches normalisation on for both sides: case, articles, number words and punctuation stop mattering.
    humans = ["The dog.", "a dog", "dog", "Dog!", "dog", "cat", "dog", "the dog", "dog", "dog"]
    assert vqa.vqa_accuracy("A Dog", humans) > 0.8
    assert vqa.vqa_accuracy("two", ["2", "2", "2", "3"] + ["2"] * 6) == pytest.approx(1.0)
    assert vqa.process_punctuation("it's a nice day.") == "it's a nice day"
    assert vqa.process_digit_article("The two dogs dont bark") == "2 dogs don't bark"
    assert vqa.answer_texts([{"answer": "a"}, "b"]) == ["a", "b"]
    with pytest.raises(ValueError):
        vqa.vqa_accuracy("x", [])


# --- prompts and replies -----------------------------------------------------------

def test_templates_render_known_placeholders_and_leave_other_braces_alone():
    record = Record(id="r", dataset_id="d", release_id="r", snapshot_id="s", question="Why?", text="Because", choices=["a", "b"], source={"kind": "x", "answers": [{"answer": "y"}, {"answer": "z"}]})
    assert tasks.render("{question}|{text}|{choices}|{field:source.kind}|{field:source.answers}|{candidate}|{reference}|{unknown}|{\"k\": 1}", record, candidate="C", reference=["R1", "R2"]) \
        == "Why?|Because|- a\n- b|x|y | z|C|R1 | R2|{unknown}|{\"k\": 1}"
    assert tasks.referenced_fields({"template": "{field:source.kind} {question}", "reference_field": "source.truth"}) == ["source.kind", "source.truth"]
    with pytest.raises(ValueError):
        tasks.record_value(record, "nonsense")


def test_the_prompt_spells_out_the_wanted_object_because_servers_may_not_enforce_a_schema():
    schema = tasks.tag_schema([{"name": "category", "type": "enum", "values": ["colour", "count"], "description": "what it asks"}, {"name": "confident", "type": "boolean"}])
    text = tasks.schema_instruction(schema)
    assert "category: one of: colour, count (what it asks)" in text and "confident: true or false" in text and text.startswith("Reply with only a JSON object")


def test_replies_are_validated_not_trusted():
    schema = tasks.tag_schema([{"name": "category", "type": "enum", "values": ["colour", "count"]}, {"name": "confident", "type": "boolean"}, {"name": "score", "type": "number"}])
    assert tasks.parse_tags('```json\n{"category": "colour", "confident": true, "score": 1}\n```', schema) == {"category": "colour", "confident": True, "score": 1.0}
    assert tasks.parse_tags('Sure! {"category": "count", "confident": false, "score": 2.5} done', schema)["category"] == "count"
    for bad in ('{"category": "other", "confident": true, "score": 1}', '{"category": "colour", "confident": "yes", "score": 1}', '{"category": "colour"}', "no json here", "[1]"):
        with pytest.raises(ValueError):
            tasks.parse_tags(bad, schema)
    assert tasks.parse_verdict('{"verdict": "unsure"}', False) == {"verdict": "unsure"}
    with pytest.raises(ValueError):
        tasks.parse_verdict('{"verdict": "maybe"}', False)
    assert tasks.clean_answer('\n  Answer: "Red."  \nextra') == "Red."
    assert tasks.clean_answer("   ") == ""
    for bad_schema in ([], [{"name": "Bad Name", "type": "string"}], [{"name": "x", "type": "enum", "values": ["only"]}], [{"name": "status", "type": "string"}]):
        with pytest.raises(ValueError):
            tasks.tag_schema(bad_schema)


# --- the client --------------------------------------------------------------------

def test_a_non_loopback_server_is_refused_before_anything_is_sent():
    with pytest.raises(ValueError, match="loopback"):
        model_client.ModelServer({"base_url": "https://models.example.com/v1", "model": "m"})
    assert model_client.is_loopback("http://127.0.0.1:8000/v1") and model_client.is_loopback("http://localhost:11434/v1") and model_client.is_loopback("http://[::1]:1/v1")
    assert not model_client.is_loopback("http://192.168.1.5:8000/v1")


def test_openai_requests_carry_images_schema_and_limits(server, tmp_path):
    client = model_client.ModelServer(server.provider, concurrency=4)
    assert client.api == "openai"
    url, body = client.chat_request([{"role": "system", "text": "be brief"}, {"role": "user", "text": "hi", "images": ["QUJD"]}], max_tokens=7, schema={"type": "object"}, thinking=False,
                                    extra={"top_p": 0.5, "model": "ignored"})
    assert url.endswith("/v1/chat/completions") and body["model"] == "fake-model" and body["max_tokens"] == 7 and body["temperature"] == 0.0
    assert body["messages"][1]["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object"} and body["chat_template_kwargs"] == {"enable_thinking": False} and body["top_p"] == 0.5


def test_ollama_is_detected_and_spoken_to_natively_with_thinking_off(ollama):
    client = model_client.ModelServer(ollama.provider)
    assert client.api == "ollama"
    url, body = client.chat_request([{"role": "user", "text": "hi", "images": ["QUJD"]}], max_tokens=9, schema={"type": "object"}, thinking=False, extra={"options": {"num_ctx": 2048}})
    assert url.endswith("/api/chat") and "/v1" not in url
    assert body["think"] is False and body["format"] == {"type": "object"} and body["messages"][0]["images"] == ["QUJD"]
    assert body["options"] == {"temperature": 0.0, "num_predict": 9, "num_ctx": 2048}


def test_requests_run_concurrently_up_to_the_limit_retry_busy_replies_and_keep_order(server):
    client = model_client.ModelServer(server.provider, concurrency=4, retries=2)
    server.fail_first = 3
    requests = [client.chat_request([{"role": "user", "text": f"item {i} color"}], max_tokens=8) for i in range(12)]
    replies = client.complete_many(requests)
    assert all(isinstance(reply, model_client.Completion) for reply in replies), replies
    assert 1 < server.max_in_flight <= 4
    assert replies[0].prompt_tokens == 11 and replies[0].completion_tokens == 3 and replies[0].finish_reason == "stop"
    prompts = [FakeServer.prompt(body) for _, body in server.requests if body.get("messages")]
    assert len(prompts) == 12 + 3  # three 503s were retried


def test_a_refusal_is_an_error_for_that_request_and_never_echoes_the_prompt(server):
    server.always_status = 400
    client = model_client.ModelServer(server.provider)
    [reply] = client.complete_many([client.chat_request([{"role": "user", "text": "SECRET DATASET TEXT"}], max_tokens=8)])
    assert isinstance(reply, model_client.ModelServerError) and "HTTP 400" in str(reply)
    assert "SECRET" not in str(reply) or "refused" in str(reply)  # the server's own message may appear; the request body does not
    assert len(server.requests) == 1, "a 4xx is not retried"


def test_embeddings_come_back_in_input_order(server):
    client = model_client.ModelServer(server.provider, api="openai", concurrency=2)
    vectors = client.embed_many(["a", "bb", "ccc", "dddd", "eeeee"], batch_size=2)
    assert [float(v[0]) for v in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]


# --- the processors ----------------------------------------------------------------

def config(server_or_provider, tmp_path, **extra):
    provider = server_or_provider.provider if hasattr(server_or_provider, "provider") else server_or_provider
    return {"provider": provider, "asset_roots": [str(tmp_path)], "storage": "arrays", **extra}


def test_answers_are_cleaned_counted_and_every_record_is_accounted_for(server, tmp_path):
    records = pictures(tmp_path, 4) + [Record(id="noq", dataset_id="d", release_id="r", snapshot_id="s", question=None), Record(id="noimg", dataset_id="d", release_id="r", snapshot_id="s", question="Q?")]
    result = run_processor("vlm.answer", records, config(server, tmp_path))
    bulk = result["bulk"]
    assert bulk.ids == ["q0", "q1", "q2", "q3"] and bulk.texts["answer"] == ["Red.", "two", "Red.", "two"]
    assert set(bulk.skipped) == {"noq", "noimg"} and bulk.skipped["noq"]["status"] == "not_applicable" and bulk.skipped["noimg"]["error"] == "The record has no image"
    assert bulk.arrays["completion_tokens"].tolist() == [3] * 4 and bulk.arrays["latency_ms"].dtype == np.float32 and bulk.texts["finish_reason"] == ["stop"] * 4
    # Requests are concurrent, so they arrive in any order: find the one that asked about colour.
    first = next(body["messages"][-1]["content"] for _, body in server.requests if "What color is it?" in FakeServer.prompt(body))
    assert first[1]["image_url"]["url"].startswith("data:image/jpeg;base64,") and "What color is it?" in first[0]["text"]
    assert result["provenance"]["provider"]["model"] == "fake-model" and result["provenance"]["example_prompt"][0]["text"].endswith("What color is it?")
    assert result["coverage"]["statuses"] == {"completed": 4, "not_applicable": 2}


def test_ollama_runs_use_the_native_endpoint_with_thinking_disabled(ollama, tmp_path):
    result = run_processor("vlm.answer", pictures(tmp_path, 2), config(ollama, tmp_path))
    assert result["bulk"].texts["answer"] == ["Red.", "two"]
    path, body = ollama.requests[0]
    assert path == "/api/chat" and body["think"] is False and len(body["messages"][0]["images"]) == 1


def test_server_failures_become_failed_records_not_a_failed_run(server, tmp_path):
    server.reply = lambda body: ""  # the model says nothing
    result = run_processor("vlm.answer", pictures(tmp_path, 2), config(server, tmp_path))
    assert result["bulk"].ids == [] and all(row["status"] == "failed" and "nothing" in row["error"] for row in result["bulk"].skipped.values())
    server.always_status = 400
    failed = run_processor("vlm.answer", pictures(tmp_path, 1), config(server, tmp_path))
    assert failed["bulk"].skipped["q0"]["status"] == "failed" and "HTTP 400" in failed["bulk"].skipped["q0"]["error"]


def test_tags_become_typed_columns(server, tmp_path):
    schema = [{"name": "category", "type": "enum", "values": ["colour", "count"]}, {"name": "confident", "type": "boolean"}, {"name": "score", "type": "number"}]
    result = run_processor("vlm.tag", pictures(tmp_path, 3), config(server, tmp_path, schema=schema, use_images=False))
    bulk = result["bulk"]
    assert bulk.texts["category"] == ["colour", "count", "colour"] and bulk.arrays["confident"].tolist() == [1, 1, 1] and bulk.arrays["score"].dtype == np.float32
    body = server.requests[0][1]
    assert body["response_format"]["json_schema"]["schema"]["properties"]["category"]["enum"] == ["colour", "count"]
    assert "Reply with only a JSON object" in FakeServer.prompt(body) and "category: one of: colour, count" in FakeServer.prompt(body)
    assert not any("image_url" in json.dumps(b) for _, b in server.requests), "tagging did not ask for images"
    server.reply = lambda body: "not json"
    assert run_processor("vlm.tag", pictures(tmp_path, 1), config(server, tmp_path, schema=schema, use_images=False))["bulk"].skipped["q0"]["status"] == "failed"


def test_judging_reads_saved_answers_and_a_reference_field(server, tmp_path):
    records = pictures(tmp_path, 2)
    directory = tmp_path / "saved"
    manifest = store.write_bundle(directory, ["q0", "q1"], {"correct": np.zeros(2, dtype=np.int8)}, texts={"answer": ["red", "blue"]})
    source = {"dir": str(directory), "column": "answer", "manifest": {k: manifest[k] for k in ("count", "ids", "texts")}}
    result = run_processor("vlm.judge", records, config(server, tmp_path, text_source=source, reference_field="source.answers", use_images=False))
    bulk = result["bulk"]
    assert bulk.texts["verdict"] == ["correct", "incorrect"] and bulk.arrays["correct"].tolist() == [1, 0]
    prompts = [FakeServer.prompt(body) for _, body in server.requests]
    red = next(prompt for prompt in prompts if "Proposed answer: red" in prompt)  # requests are concurrent: find it by content
    assert "Reference answers: red | red" in red and "verdict: one of: correct, incorrect, unsure" in red
    with pytest.raises(ValueError, match="saved answers"):
        run_processor("vlm.judge", records, config(server, tmp_path))


def test_embeddings_from_a_model_server_are_unit_length_and_have_an_identity(server, tmp_path):
    records = pictures(tmp_path, 3) + [Record(id="blank", dataset_id="d", release_id="r", snapshot_id="s", question="  ")]
    result = run_processor("embed.api", records, config(server, tmp_path, representation="question", storage_dtype="float32"))
    bulk = result["bulk"]
    assert bulk.ids == ["q0", "q1", "q2"] and bulk.arrays["vector"].shape == (3, 4) and set(bulk.skipped) == {"blank"}
    assert np.allclose(np.linalg.norm(bulk.arrays["vector"], axis=1), 1)
    assert result["provenance"]["embedding_space_id"].startswith("space:") and result["provenance"]["model_id"] == "fake-model"


def test_scoring_saved_answers_gives_per_record_accuracy_and_a_breakdown(tmp_path):
    records = pictures(tmp_path, 4)
    directory = tmp_path / "saved"
    manifest = store.write_bundle(directory, ["q0", "q1", "q2"], {"x": np.zeros(3, dtype=np.int8)}, texts={"answer": ["red", "3", "blue"]})
    source = {"dir": str(directory), "column": "answer", "manifest": {k: manifest[k] for k in ("count", "ids", "texts")}}
    result = run_processor("score.vqa_accuracy", records, {"text_source": source, "storage": "arrays"})
    bulk = result["bulk"]
    assert bulk.ids == ["q0", "q1", "q2"] and bulk.arrays["accuracy"].tolist() == [1.0, 0.0, 0.0] and set(bulk.skipped) == {"q3"}
    summary = bulk.summary
    assert summary["scored"] == 3 and summary["mean_accuracy"] == pytest.approx(1 / 3, abs=1e-5)
    by_type = {row["value"]: row for row in summary["by"]["source.question_type"]}
    assert by_type["what color"]["count"] == 2 and by_type["what color"]["mean_accuracy"] == pytest.approx(0.5) and by_type["how many"]["mean_accuracy"] == 0.0


# --- through the API ---------------------------------------------------------------

def test_a_run_through_the_api_uses_the_configured_loopback_provider_and_joins_its_answers(workspace, server):
    (workspace / "local-config").mkdir(exist_ok=True)
    with TestClient(create_app(workspace)) as client:
        added = client.post("/api/v1/providers", headers=HEADERS, json={"id": "fake", "base_url": server.provider["base_url"], "model": "fake-model", "max_output_tokens": 64})
        assert added.status_code == 200, added.text
        records = client.post("/api/v1/queries/fixture", headers=HEADERS, json={"snapshot_id": "s1", "population_scope": "preview", "unit": "example", "limit": 5}).json()["records"]
        ids = [row["id"] for row in records]
        selection = client.post("/api/v1/selections", headers=HEADERS, json={"id": "", "name": "t", "ids": ids, "unit": "example", "snapshot_ids": ["s1"], "dataset_ids": ["fixture"], "created_at": "2026-01-01T00:00:00Z"}).json()
        run_config = {"provider_id": "fake", "use_images": False, "template": "Is the label of {field:source.label} recorded? Question: {question}", "max_tokens": 8}
        estimate = client.post("/api/v1/runs/estimate", headers=HEADERS, json={"selection_id": selection["id"], "processor_id": "vlm.answer", "config": run_config})
        assert estimate.status_code == 200, estimate.text
        body = estimate.json()
        assert body["storage"] == "arrays" and body["resource_class"] == "network" and body["remote_calls"] == len(ids)
        assert body["processor_estimate"]["loopback_only"] is True and body["processor_estimate"]["provider"]["model"] == "fake-model"
        assert body["processor_estimate"]["example_prompt"][0]["text"].startswith("Is the label of")
        assert not server.requests, "estimating sends nothing to the model"
        run = client.post("/api/v1/runs", headers=HEADERS, json={"selection_id": selection["id"], "processor_id": "vlm.answer", "config": run_config, "estimate_digest": body["estimate_digest"]})
        assert run.status_code == 200, run.text
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = client.get(f"/api/v1/runs/{run.json()['id']}").json()
            if state["status"] not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert state["status"] == "completed", state.get("errors")
        artifact = client.get(f"/api/v1/artifacts/{state['artifact_ids'][0]}").json()
        assert artifact["data"]["bulk"]["texts"]["answer"]["count"] == len(ids) and "provider" not in artifact["provenance"]["config"]
        assert client.get(f"/api/v1/artifacts/{artifact['id']}/texts/answer").json() == ["two"] * len(ids)
        assert len(server.requests) == len(ids)
        # The answers join onto records as an ordinary text field.
        joined = client.post("/api/v1/queries/fixture", headers=HEADERS, json={"snapshot_id": "s1", "population_scope": "preview", "unit": "example", "result_snapshot_ids": [artifact["id"]],
                                                                               "filter": {"field_id": f"prediction.{artifact['id']}.answer", "op": "eq", "value": "two"}})
        assert joined.status_code == 200 and joined.json()["matched_count"] == len(ids)


def test_an_external_provider_cannot_receive_a_batch_run(workspace):
    with TestClient(create_app(workspace)) as client:
        added = client.post("/api/v1/providers", headers=HEADERS, json={"id": "cloud", "base_url": "https://models.example.com/v1", "model": "m", "allow_external": True, "api_key_env": "SOME_KEY"})
        assert added.status_code == 200, added.text
        with pytest.raises(ValueError, match="loopback"):
            client.app.state.run_config("vlm.answer", {"provider_id": "cloud"})
        with pytest.raises(ValueError, match="Choose a model server"):
            client.app.state.run_config("vlm.answer", {})
        assert "provider" not in client.app.state.run_config("project.pca", {"provider": {"base_url": "http://evil"}})


def test_a_reply_that_is_all_reasoning_says_so(ollama, tmp_path):
    """A thinking model can spend its budget before answering; the failure must name that, not just 'nothing'."""
    ollama.reply = lambda body: ""
    original = ollama.httpd.RequestHandlerClass.do_POST

    def thinking_post(handler):
        body = json.loads(handler.rfile.read(int(handler.headers["Content-Length"])))
        payload = json.dumps({"message": {"role": "assistant", "content": "", "thinking": "Let me consider..."}, "done_reason": "length", "prompt_eval_count": 9, "eval_count": 24}).encode()
        handler.send_response(200)
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    ollama.httpd.RequestHandlerClass.do_POST = thinking_post
    try:
        result = run_processor("vlm.answer", pictures(tmp_path, 1), config(ollama, tmp_path))
    finally:
        ollama.httpd.RequestHandlerClass.do_POST = original
    error = result["bulk"].skipped["q0"]["error"]
    assert "reasoning" in error and "max_tokens" in error and "length" in error

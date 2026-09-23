from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.providers import ProviderService, create_provider_router
from dataset_atlas.providers.schemas import ContextRequest, ConversationRequest, ProviderConfig, ToolResult
from dataset_atlas.providers.tools import execute_tool


def record() -> Record:
    return Record(
        id="sample-1", dataset_id="example", release_id="r1", snapshot_id="s1",
        text="a harmless question", question="What is shown?", choices=["cat", "dog"],
        source={"gold_label": "cat", "filename": "cat-answer.png"},
        prediction={"model_answer": "cat"},
        assets=[Asset(id="image-1", dataset_id="example", release_id="r1", modality="image", uri="image.png")],
    )


def service(tmp_path: Path, handler=None) -> ProviderService:
    transport = httpx.MockTransport(handler or (lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})))
    factory = lambda **kwargs: httpx.Client(transport=transport, **kwargs)
    result = ProviderService(tmp_path / "providers.json", lambda id: record() if id == "sample-1" else None, [tmp_path], client_factory=factory)
    result.put_provider(ProviderConfig(id="local", base_url="http://127.0.0.1:1234/v1", model="mock"))
    return result


def test_context_requires_exact_approval_and_never_sends_on_preview(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    svc = service(tmp_path, handler)
    svc.probe("local", ["text_generation"])
    assert len(requests) == 1  # benign probe
    context = ContextRequest(provider_id="local", record_ids=["sample-1"], mode="evaluation")
    preview = svc.preview(context)
    assert len(requests) == 1
    outgoing = json.dumps(preview.outgoing)
    assert "gold_label" not in outgoing and "filename" not in outgoing and "model_answer" not in outgoing
    assert "image-unavailable" not in outgoing  # notice is plain language
    assert "Images are unavailable" in outgoing

    with pytest.raises(ValueError, match="context changed"):
        svc.converse(ConversationRequest(context=context, context_digest="0" * 64, approved_provider_id="local", approved_record_ids=["sample-1"], prompt="Answer"))
    assert len(requests) == 1
    result = svc.converse(ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=["sample-1"], prompt="Answer"))
    assert result.response == "OK" and result.error is None
    assert len(requests) == 2
    assert result.provenance["input_sent"]["context_digest"] == preview.context_digest
    assert svc.list_conversations()[0].id == result.id
    assert svc.get_conversation(result.id).provenance["input_sent"]["context_digest"] == preview.context_digest


def test_evaluation_rejects_hidden_fields_even_if_requested(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(ValueError, match="evaluation excludes"):
        svc.preview(ContextRequest(provider_id="local", record_ids=["sample-1"], mode="evaluation", fields=["source.gold_label"]))
    with pytest.raises(ValueError, match="evaluation excludes"):
        svc.preview(ContextRequest(provider_id="local", record_ids=["sample-1"], mode="evaluation", include_annotations=True))
    preview = svc.preview(ContextRequest(provider_id="local", record_ids=["sample-1"], mode="exploration", fields=["source.gold_label"]))
    assert "gold_label" in json.dumps(preview.outgoing)
    with pytest.raises(ValueError, match="requires independent_records"):
        from dataset_atlas.providers.context import build_context
        build_context(ContextRequest(provider_id="local", record_ids=["sample-1", "sample-2"], mode="evaluation"), svc.get_provider("local"), lambda identity: record().model_copy(update={"id": identity}), [tmp_path])


def test_image_requires_probe_and_allowed_real_bytes(tmp_path):
    svc = service(tmp_path)
    request = ContextRequest(provider_id="local", record_ids=["sample-1"], image_asset_ids=["image-1"])
    with pytest.raises(ValueError, match="not been verified"):
        svc.preview(request)
    svc._providers["local"].capabilities["single_image_input"].status = "supported"
    Image.new("RGB", (2, 2), "red").save(tmp_path / "image.png")
    preview = svc.preview(request)
    assert preview.outgoing[0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert preview.image_representations[0]["sha256"]
    (tmp_path / "image.png").unlink()
    (tmp_path / "image.png").symlink_to("/etc/hosts")
    with pytest.raises(ValueError, match="unsafe under configured roots"):
        svc.preview(request)


def test_config_and_probe_are_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_TEST_KEY", "secret-value")
    seen_auth = []

    def handler(request):
        seen_auth.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    svc = service(tmp_path, handler)
    svc.put_provider(ProviderConfig(id="local", base_url="http://127.0.0.1:1234/v1", model="mock", api_key_env="ATLAS_TEST_KEY"))
    assert all(item.status == "unknown" for item in svc.get_provider("local").capabilities.values())
    probed = svc.probe("local", ["text_generation"])
    assert probed.capabilities["text_generation"].status == "supported"
    assert probed.capabilities["image_embeddings"].status == "unknown"
    assert seen_auth == ["Bearer secret-value"]
    assert "secret-value" not in (tmp_path / "providers.json").read_text()
    context = ContextRequest(provider_id="local", record_ids=["sample-1"])
    preview = svc.preview(context)
    svc.converse(ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=["sample-1"], prompt="Answer"))
    assert "secret-value" not in (tmp_path / "conversations.jsonl").read_text()
    with pytest.raises(ValueError, match="HTTPS"):
        ProviderConfig(id="bad", base_url="http://example.org/v1", model="m", allow_external=True)
    with pytest.raises(ValueError, match="allow_external"):
        ProviderConfig(id="bad", base_url="https://example.org/v1", model="m")


def test_read_only_tool_scope_budget_and_receipt():
    def backend(name, args, scope, remaining):
        assert scope == frozenset({"sample-1"})
        return ToolResult(rows=[{"id": "sample-1", "text": "observed"}], population_scope="approved_selection", coverage={"matched": 1}, source_refs=["sample-1"])

    receipt = execute_tool("get_records", {"record_ids": ["sample-1"], "limit": 1}, backend, frozenset({"sample-1"}), 1, "evaluation")
    assert receipt["citation_id"].startswith("atlas-tool:")
    assert receipt == execute_tool("get_records", {"record_ids": ["sample-1"], "limit": 1}, backend, frozenset({"sample-1"}), 1, "evaluation")
    with pytest.raises(ValueError, match="outside approved scope"):
        execute_tool("get_records", {"record_ids": ["other"]}, backend, frozenset({"sample-1"}), 1, "exploration")
    with pytest.raises(ValueError, match="not allowlisted"):
        execute_tool("shell", {}, backend, frozenset({"sample-1"}), 1, "exploration")
    with pytest.raises(ValueError, match="row limit"):
        execute_tool("get_records", {"limit": 2}, backend, frozenset({"sample-1"}), 1, "exploration")


def test_router_requires_mutation_header(tmp_path):
    app = FastAPI()
    app.include_router(create_provider_router(service(tmp_path)), prefix="/api/v1")
    client = TestClient(app)
    assert client.get("/api/v1/providers").status_code == 200
    assert client.post("/api/v1/conversations/context", json={"provider_id": "local", "record_ids": ["sample-1"]}).status_code == 403
    response = client.post("/api/v1/conversations/context", headers={"X-Atlas-Request": "1"}, json={"provider_id": "local", "record_ids": ["sample-1"]})
    assert response.status_code == 200
    assert response.json()["context_digest"]
    assert client.get("/api/v1/conversations").json() == []
    assert client.get("/api/v1/conversations/conversation:missing").status_code == 404


def test_external_record_transmission_fails_closed_without_rights_policy(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    svc = service(tmp_path, handler)
    svc.put_provider(ProviderConfig(id="remote", base_url="https://models.example.org/v1", model="mock", allow_external=True))
    svc._providers["remote"].capabilities["text_generation"].status = "supported"
    context = ContextRequest(provider_id="remote", record_ids=["sample-1"])
    preview = svc.preview(context)
    assert preview.external_send_allowed is False
    with pytest.raises(ValueError, match="No external dataset transmission policy"):
        svc.converse(ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="remote", approved_record_ids=["sample-1"], prompt="Answer"))
    assert not requests

    svc.external_record_policy = lambda record, context: record.dataset_id == "example" and not context.image_asset_ids
    approved = svc.preview(context)
    assert approved.external_send_allowed is True
    result = svc.converse(ConversationRequest(context=context, context_digest=approved.context_digest, approved_provider_id="remote", approved_record_ids=["sample-1"], prompt="Answer"))
    assert result.response == "OK"
    assert len(requests) == 1


def test_tool_loop_has_grounded_receipt_and_enforces_call_budget(tmp_path):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(body["messages"]) == 3:
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "get_records", "arguments": '{"record_ids":["sample-1"],"limit":1}'}}]}}], "usage": {"total_tokens": 10}})
        receipt = json.loads(body["messages"][-1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": f"Observed one selected record [[record:sample-1]] {receipt['citation_id']}"}}], "usage": {"total_tokens": 5}})

    svc = service(tmp_path, handler)
    svc._providers["local"].capabilities["text_generation"].status = "supported"
    svc._providers["local"].capabilities["tool_calls"].status = "supported"
    svc.tool_backend = lambda name, args, scope, remaining: ToolResult(rows=[{"id": "sample-1", "text": "observed"}], population_scope="approved_selection", coverage={"matched": 1}, source_refs=["sample-1"])
    context = ContextRequest(provider_id="local", record_ids=["sample-1"])
    preview = svc.preview(context)
    args = dict(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=["sample-1"], prompt="Describe the selected record", use_tools=True)
    result = svc.converse(ConversationRequest(**args, required_tool="get_records"))
    assert result.error is None
    assert result.usage["total_tokens"] == 15
    assert result.provenance["cited_records"] == ["sample-1"]
    assert result.provenance["cited_tool_receipts"] == [result.tool_results[0]["citation_id"]]
    assert len(requests) == 2
    assert requests[0]["tool_choice"]["function"]["name"] == "get_records"
    limited = svc.converse(ConversationRequest(**args, max_tool_calls=0))
    assert limited.error == "tool call budget exceeded"
    assert len(requests) == 3


def test_unavailable_record_citation_is_rejected(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "See [[record:unapproved]]"}}]})

    svc = service(tmp_path, handler)
    svc._providers["local"].capabilities["text_generation"].status = "supported"
    context = ContextRequest(provider_id="local", record_ids=["sample-1"])
    preview = svc.preview(context)
    result = svc.converse(ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=["sample-1"], prompt="Answer"))
    assert result.error == "model cited a record outside the approved interaction"
    from dataset_atlas.providers.tools import validate_record_citations
    with pytest.raises(ValueError, match="outside the approved"):
        validate_record_citations("[record:short-id]", frozenset({"sample-1"}))


def test_independent_evaluation_batch_is_isolated_bounded_and_resumable(tmp_path):
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        context = json.loads(body["messages"][1]["content"][0]["text"])
        identity = context["records"][0]["record_id"]
        return httpx.Response(200, json={"choices": [{"message": {"content": f"Answer for [[record:{identity}]]"}}], "usage": {"completion_tokens": 8}})

    records = {identity: record().model_copy(update={"id": identity}) for identity in ("sample-1", "sample-2")}
    transport = httpx.MockTransport(handler)
    svc = ProviderService(tmp_path / "providers.json", records.get, [tmp_path], client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))
    svc.put_provider(ProviderConfig(id="local", base_url="http://127.0.0.1:1234/v1", model="mock"))
    svc._providers["local"].capabilities["text_generation"].status = "supported"
    context = ContextRequest(provider_id="local", record_ids=["sample-1", "sample-2"], mode="evaluation", independent_records=True)
    preview = svc.preview(context)
    assert preview.delivery == "independent" and preview.outgoing == []
    assert [item["record_id"] for item in preview.per_record_contexts] == context.record_ids
    assert all("gold_label" not in json.dumps(item["outgoing"]) for item in preview.per_record_contexts)

    request = ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=context.record_ids, prompt="Answer each separately", max_batch_completion_tokens=512)
    first = svc.converse(request)
    assert first.status == "partial" and first.completed_record_ids == ["sample-1"] and first.pending_record_ids == ["sample-2"]
    assert len(sent) == 1 and len(sent[0]["messages"][1]["content"][0]["text"].split("sample-2")) == 1
    second = svc.converse(request)
    assert second.status == "complete" and second.completed_record_ids == context.record_ids
    assert len(sent) == 2
    assert svc.get_batch(first.batch_id).status == "complete"
    third = svc.converse(request)
    assert third.batch_id == first.batch_id and len(sent) == 2
    assert all(len(item.record_ids) == 1 for item in third.results)
    assert all(item.provenance["input_sent"]["delivery"] == "joint" for item in third.results)


def test_batch_digest_detects_record_change_before_send(tmp_path):
    records = {identity: record().model_copy(update={"id": identity}) for identity in ("sample-1", "sample-2")}
    svc = ProviderService(tmp_path / "providers.json", records.get, [tmp_path])
    svc.put_provider(ProviderConfig(id="local", base_url="http://127.0.0.1:1234/v1", model="mock"))
    svc._providers["local"].capabilities["text_generation"].status = "supported"
    context = ContextRequest(provider_id="local", record_ids=list(records), mode="evaluation", independent_records=True)
    preview = svc.preview(context)
    records["sample-2"] = records["sample-2"].model_copy(update={"question": "changed"})
    with pytest.raises(ValueError, match="context changed"):
        svc.converse(ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id="local", approved_record_ids=list(records), prompt="Answer"))


def test_context_digest_binds_provider_endpoint(tmp_path):
    svc = service(tmp_path)
    context = ContextRequest(provider_id="local", record_ids=["sample-1"])
    before = svc.preview(context)
    svc.put_provider(ProviderConfig(id="local", base_url="http://127.0.0.1:4321/v1", model="mock"))
    after = svc.preview(context)
    assert before.context_digest != after.context_digest
    assert after.policy["provider_endpoint"] == "http://127.0.0.1:4321/v1"


@pytest.mark.parametrize('content,reason,message',[('', 'stop','empty response'),('   ','stop','empty response'),('', 'length','output limit'),('partial answer','length','incomplete'),('','content_filter','content filtering')])
def test_incomplete_provider_answers_are_saved_as_errors(tmp_path,content,reason,message):
    svc=service(tmp_path,lambda request:httpx.Response(200,json={'choices':[{'message':{'content':content},'finish_reason':reason}]}))
    svc._providers['local'].capabilities['text_generation'].status='supported'
    context=ContextRequest(provider_id='local',record_ids=['sample-1'])
    preview=svc.preview(context)
    result=svc.converse(ConversationRequest(context=context,context_digest=preview.context_digest,approved_provider_id='local',approved_record_ids=['sample-1'],prompt='Answer'))
    assert message in result.error
    assert result.response==content
    assert result.provenance['finish_reasons']==[reason]
    assert svc.get_conversation(result.id).error==result.error


def test_empty_provider_output_does_not_complete_an_evaluation_batch(tmp_path):
    svc=service(tmp_path,lambda request:httpx.Response(200,json={'choices':[{'message':{'content':''},'finish_reason':'length'}]}))
    svc._providers['local'].capabilities['text_generation'].status='supported'
    svc.record_lookup=lambda identity:record().model_copy(update={'id':identity})
    context=ContextRequest(provider_id='local',record_ids=['sample-1','sample-2'],mode='evaluation',independent_records=True)
    preview=svc.preview(context)
    result=svc.converse(ConversationRequest(context=context,context_digest=preview.context_digest,approved_provider_id='local',approved_record_ids=['sample-1','sample-2'],prompt='Answer'))
    assert result.status=='partial' and result.pending_record_ids==['sample-1','sample-2'] and result.completed_record_ids==[]


def test_truncated_probe_remains_unknown_and_respects_configured_budget(tmp_path):
    seen=[]
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'message':{'content':''},'finish_reason':'length'}]})
    svc=service(tmp_path,handler)
    svc.put_provider(ProviderConfig(id='local',base_url='http://127.0.0.1:1234/v1',model='mock',max_output_tokens=32))
    result=svc.probe('local',['text_generation','tool_calls'])
    assert all(result.capabilities[name].status=='unknown' for name in ['text_generation','tool_calls'])
    assert all(x['max_tokens']==32 for x in seen)

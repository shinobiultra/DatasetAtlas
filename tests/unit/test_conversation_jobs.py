import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dataset_atlas.models import Record
from dataset_atlas.providers import ProviderService, create_provider_router
from dataset_atlas.providers.schemas import CapabilityResult, ContextRequest, ConversationRequest, ProviderConfig


def configured(tmp_path, base_url='http://127.0.0.1:1234/v1', client_factory=httpx.Client, second_record=False):
    record = Record(id='synthetic-record', dataset_id='synthetic', release_id='v1', snapshot_id='synthetic-snapshot', text='Synthetic cancellation test')
    records={record.id:record}
    if second_record:records['synthetic-record-2']=record.model_copy(update={'id':'synthetic-record-2'})
    service = ProviderService(tmp_path / 'providers.json', records.get, client_factory=client_factory)
    provider = service.put_provider(ProviderConfig(id='local', base_url=base_url, model='synthetic', timeout_seconds=30))
    provider.capabilities['text_generation'] = CapabilityResult(status='supported')
    context = ContextRequest(provider_id='local', record_ids=list(records), snapshot_ids=[record.snapshot_id],mode='evaluation' if second_record else 'exploration',independent_records=second_record)
    preview = service.preview(context)
    request = ConversationRequest(context=context, context_digest=preview.context_digest, approved_provider_id='local', approved_record_ids=list(records), prompt='Reply OK')
    return service, request


def wait_finished(service, identity, seconds=2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = service.get_conversation_job(identity)
        if job['status'] not in {'running', 'cancelling'}:
            return job
        time.sleep(0.01)
    pytest.fail('Request did not reach a terminal state within the bounded wait')


def test_cancel_closes_actual_provider_socket_and_retains_receipt(tmp_path):
    entered, closed = threading.Event(), threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Length', '10000')
            self.end_headers()
            self.wfile.write(b'{')
            self.wfile.flush()
            entered.set()
            self.connection.settimeout(3)
            try:
                if self.connection.recv(1) == b'':
                    closed.set()
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        service, request = configured(tmp_path, f'http://127.0.0.1:{server.server_port}/v1')
        job = service.start_conversation_job(request)
        assert entered.wait(2)
        with pytest.raises(ValueError, match='already active'):
            service.start_conversation_job(request)
        started = time.monotonic()
        assert service.cancel_conversation_job(job['id'])['status'] == 'cancelling'
        done = wait_finished(service, job['id'])
        assert done['status'] == 'cancelled' and time.monotonic() - started < 1
        assert closed.wait(1), 'Cancellation must close the actual provider connection'
        assert done['result']['error'] == 'conversation cancelled by user'
        assert done['result']['provenance']['input_sent']['context_digest'] == request.context_digest
        assert service.cancel_conversation_job(job['id'])['status'] == 'cancelled'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(1)


def test_completed_async_job_api_guards_and_no_restart_retry(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]}))
    service, request = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))
    app = FastAPI()
    app.include_router(create_provider_router(service), prefix='/api/v1')
    with TestClient(app) as client:
        assert client.post('/api/v1/conversation-jobs', json=request.model_dump(mode='json')).status_code == 403
        invalid = request.model_copy(update={'context_digest': '0' * 64})
        assert client.post('/api/v1/conversation-jobs', json=invalid.model_dump(mode='json'), headers={'X-Atlas-Request': '1'}).status_code == 400
        response = client.post('/api/v1/conversation-jobs', json=request.model_dump(mode='json'), headers={'X-Atlas-Request': '1'})
        assert response.status_code == 200
        done = wait_finished(service, response.json()['id'])
        assert done['status'] == 'completed' and done['result']['response'] == 'OK'
        assert client.get('/api/v1/conversation-jobs').json()[0]['id'] == done['id']
        assert client.get('/api/v1/conversation-jobs/invalid').status_code == 404
        restarted, _ = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))
        path = service._conversation_job_path(done['id'])
        state = json.loads(path.read_text())
        state['status'] = 'running'
        path.write_text(json.dumps(state))
        assert restarted.get_conversation_job(done['id'])['status'] == 'interrupted'


def test_cancel_and_deadline_apply_while_waiting_for_batch_lock(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]}))
    service, request = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs),second_record=True)
    context = request.context.model_copy(update={'mode': 'evaluation', 'independent_records': True})
    preview = service.preview(context)
    request = request.model_copy(update={'context': context, 'context_digest': preview.context_digest})
    service._batch_lock.acquire()
    try:
        job = service.start_conversation_job(request)
        time.sleep(0.02)
        worker = service._conversation_job_threads[job['id']]
        service.cancel_conversation_job(job['id'])
        assert wait_finished(service, job['id'])['status'] == 'cancelled'
        worker.join(5)  # the terminal state is written before the worker releases its admission
        job = service.start_conversation_job(request.model_copy(update={'deadline_seconds': 0.1}))
        worker = service._conversation_job_threads[job['id']]
        done = wait_finished(service, job['id'])
        assert done['status'] == 'failed' and 'deadline' in done['error']
        worker.join(5)
        assert not service._conversation_cancel_events
    finally:
        service._batch_lock.release()
        service.close()


def test_terminal_write_failure_releases_request_slot_and_reports_error(tmp_path, monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]}))
    service, request = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))
    original = service._write_conversation_job
    def fail_terminal(job):
        if job['status'] in {'completed', 'failed', 'cancelled'}:
            raise OSError('synthetic disk failure')
        return original(job)
    monkeypatch.setattr(service, '_write_conversation_job', fail_terminal)
    done = wait_finished(service, service.start_conversation_job(request)['id'])
    assert done['status'] == 'failed' and 'persist terminal' in done['error']
    assert done['result']['response'] == 'OK' and not service._conversation_cancel_events
    monkeypatch.setattr(service, '_write_conversation_job', original)
    assert wait_finished(service, service.start_conversation_job(request)['id'])['status'] == 'completed'
    service.close()


def test_service_close_cancels_waiting_jobs_and_denies_new_requests(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]}))
    service, request = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs),second_record=True)
    context = request.context.model_copy(update={'mode': 'evaluation', 'independent_records': True})
    request = request.model_copy(update={'context': context, 'context_digest': service.preview(context).context_digest})
    service._batch_lock.acquire()
    try:
        job = service.start_conversation_job(request)
        service.close()
        assert service.get_conversation_job(job['id'])['status'] == 'cancelled'
        assert not service._conversation_job_threads
        with pytest.raises(ValueError, match='shutting down'):
            service.start_conversation_job(request)
    finally:
        service._batch_lock.release()


def test_stale_probe_cannot_restore_prior_config_and_probes_share_admission(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def handler(request):
        entered.set()
        assert release.wait(2)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})
    transport = httpx.MockTransport(handler)
    service, request = configured(tmp_path, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))
    worker = threading.Thread(target=lambda: service.probe('local', ['text_generation']))
    worker.start()
    try:
        assert entered.wait(1)
        changed = service.get_provider('local').config.model_copy(update={'model': 'changed-config'})
        service.put_provider(changed)
        # Approval preview itself has become stale, while admission also protects the network operation.
        with pytest.raises(ValueError):
            service.start_conversation_job(request)
        with pytest.raises(ValueError, match='already active'):
            service.probe('local', ['text_generation'])
        release.set();worker.join(2)
        assert not worker.is_alive()
        assert service.get_provider('local').config.model == 'changed-config'
        assert service.get_provider('local').capabilities['text_generation'].status == 'unknown'
    finally:
        release.set();worker.join(2);service.close()
    with pytest.raises(ValueError, match='shutting down'):
        service.probe('local', ['text_generation'])

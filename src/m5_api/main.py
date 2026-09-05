import time
from dataclasses import asdict
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src.m2_rag import RAGRequest, build_light_service
from src.m2_rag.corpus import load_m1_corpus
from src.m5_api.core.security import verify_user, create_token, get_current_user
from src.m5_api.core.cache import get_cached_response, set_cached_response
from src.m5_api.core.tasks import analyze_document_task, celery_app
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI(title="Assistant Juridique — API M5")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
service = build_light_service(load_m1_corpus())

@app.get("/health")
def health_check():
    return {"status": "ok", "module": "M5 - API & Serving"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not verify_user(form_data.username, form_data.password):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    token = create_token(form_data.username)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/chat")
@limiter.limit("5/minute")
def chat(request: Request, question: str, current_user: str = Depends(get_current_user)):
    cached = get_cached_response(question)
    if cached:
        cached["from_cache"] = True
        return cached

    response = service.query(RAGRequest(question=question))
    result = {
        "answer": response.answer,
        "citations": [asdict(c) for c in response.citations],
        "refused": response.refused,
        "from_cache": False,
    }
    set_cached_response(question, result)
    return result

def generate_chunks(text: str):
    for word in text.split():
        yield f"data: {word}\n\n"
        time.sleep(0.05)

@app.get("/chat/stream")
def chat_stream(question: str, current_user: str = Depends(get_current_user)):
    response = service.query(RAGRequest(question=question))
    return StreamingResponse(generate_chunks(response.answer), media_type="text/event-stream")

@app.post("/documents/analyze")
def analyze_document(document_name: str, current_user: str = Depends(get_current_user)):
    task = analyze_document_task.delay(document_name)
    return {"task_id": task.id, "status": "processing"}

@app.get("/documents/status/{task_id}")
def get_task_status(task_id: str, current_user: str = Depends(get_current_user)):
    task = celery_app.AsyncResult(task_id)
    if task.state == "PENDING":
        return {"status": "processing"}
    elif task.state == "SUCCESS":
        return {"status": "completed", "result": task.result}
    else:
        return {"status": task.state}
import hashlib, hmac
from app.core.config import settings

def test_webhook_verification(client):
    test,_=client
    ok=test.get("/api/v1/whatsapp/webhook",params={"hub.mode":"subscribe","hub.verify_token":settings.whatsapp_verify_token,"hub.challenge":"1234"})
    assert ok.status_code==200 and ok.text=="1234"
    assert test.get("/api/v1/whatsapp/webhook",params={"hub.mode":"subscribe","hub.verify_token":"wrong","hub.challenge":"1234"}).status_code==403

def test_whatsapp_help_type_description_location_conversation(client):
    test,_=client
    def event(message,kind="text"):
        entry={"from":"2348000000000","id":message.get("id","m1"),"type":kind}
        if kind=="text": entry["text"]={"body":message["body"]}
        else: entry["location"]={"latitude":7.2,"longitude":5.1}
        return {"entry":[{"changes":[{"value":{"messages":[entry]}}]}]}
    assert "What type" in test.post("/api/v1/whatsapp/webhook",json=event({"id":"a","body":"HELP"})).json()["replies"][0]["text"]
    assert "describe" in test.post("/api/v1/whatsapp/webhook",json=event({"id":"b","body":"1"})).json()["replies"][0]["text"]
    assert "share your current WhatsApp location" in test.post("/api/v1/whatsapp/webhook",json=event({"id":"c","body":"Person collapsed"})).json()["replies"][0]["text"]
    result=test.post("/api/v1/whatsapp/webhook",json=event({"id":"d"},"location")).json()
    assert "Incident ID" in result["replies"][0]["text"]
    assert test.get("/api/v1/incidents").status_code==401

def test_natural_language_message_starts_location_collection(client):
    test,_=client
    event={"entry":[{"changes":[{"value":{"messages":[{"from":"2348111222333","id":"natural-1","type":"text","text":{"body":"There has been an accident on Ondo Road. Two people are injured."}}]}}]}]}
    reply=test.post("/api/v1/whatsapp/webhook",json=event).json()["replies"][0]["text"]
    assert "road accident" in reply.lower() and "location" in reply.lower()

def test_meta_webhook_checks_hmac_signature(client):
    test,_=client
    old_provider,old_secret=settings.whatsapp_provider,settings.whatsapp_app_secret
    settings.whatsapp_provider="meta"; settings.whatsapp_app_secret="unit-test-secret"
    raw=b'{"entry":[]}'
    good="sha256="+hmac.new(settings.whatsapp_app_secret.encode(),raw,hashlib.sha256).hexdigest()
    try:
        assert test.post("/api/v1/whatsapp/webhook",content=raw,headers={"Content-Type":"application/json","X-Hub-Signature-256":"sha256=bad"}).status_code==401
        assert test.post("/api/v1/whatsapp/webhook",content=raw,headers={"Content-Type":"application/json","X-Hub-Signature-256":good}).status_code==200
    finally:
        settings.whatsapp_provider=old_provider; settings.whatsapp_app_secret=old_secret

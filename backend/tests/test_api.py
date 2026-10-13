from app.main import pwd

def auth(test, email="resq.test@example.test", password="testing-password-123"):
    db=test.SessionLocal()
    db.add(__import__('app.models',fromlist=['User']).User(name="Test Operator",email=email,password_hash=pwd.hash(password),role="ADMIN")); db.commit(); db.close()
    response=test.client.post("/api/v1/auth/login",data={"username":email,"password":password})
    assert response.status_code==200
    return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_create_track_and_protect_incident_list(client):
    client,Session=client
    assert client.get("/api/v1/incidents").status_code==401
    created=client.post("/api/v1/incidents",json={"incident_type":"medical","description":"A person collapsed near the market","latitude":7.1,"longitude":5.2})
    assert created.status_code==201
    data=created.json()["data"]
    assert data["verification_status"]=="PENDING"
    tracked=client.get(f"/api/v1/incidents/{data['incident_code']}").json()["data"]
    assert tracked["incident_code"]==data["incident_code"]
    assert "latitude" not in tracked and "reporter_phone" not in tracked
    headers=auth(type("X",(),{"client":client,"SessionLocal":Session})())
    assert client.get("/api/v1/incidents",headers=headers).status_code==200
    detail=client.get(f"/api/v1/incidents/{data['id']}/detail",headers=headers).json()["data"]
    assert detail["ai_detected_type"]=="medical" and detail["ai_assessment_details"]["confidence"]>0
    analytics=client.get("/api/v1/analytics",headers=headers).json()
    assert analytics["by_location"]=={"Coordinates only":1} and analytics["over_time"]

def test_invalid_login(client):
    test,_=client
    assert test.post("/api/v1/auth/login",data={"username":"nobody@example.test","password":"wrong"}).status_code==401

def test_status_lifecycle_and_assignment_requires_database_available_unit(client):
    test,Session=client
    headers=auth(type("X",(),{"client":test,"SessionLocal":Session})())
    created=test.post("/api/v1/incidents",json={"incident_type":"fire","description":"Fire reported at building","latitude":7.2,"longitude":5.1}).json()["data"]
    iid=created["id"]
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"VERIFIED"}).status_code==409
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"VERIFYING"}).status_code==200
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"VERIFIED"}).status_code==200
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"AWAITING_RESPONSE"}).status_code==200
    unit=test.post("/api/v1/response-units",headers=headers,json={"unit_code":"T-01","unit_type":"Ambulance"}).json()
    assigned=test.post(f"/api/v1/incidents/{iid}/assign",headers=headers,json={"unit_id":unit["id"]})
    assert assigned.status_code==200 and assigned.json()["data"]["status"]=="ASSIGNED"
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"RESOLVED"}).status_code==409
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"EN_ROUTE"}).status_code==200
    assert test.get("/api/v1/response-units",headers=headers).json()[0]["status"]=="EN_ROUTE"
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"ARRIVED"}).status_code==200
    assert test.patch(f"/api/v1/incidents/{iid}/status",headers=headers,json={"status":"RESOLVED"}).status_code==200
    assert test.get("/api/v1/response-units",headers=headers).json()[0]["status"]=="AVAILABLE"

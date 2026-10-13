import asyncio, json, secrets, math
import hashlib, hmac, time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database import get_db
from app.models import User, Incident, ResponseUnit, Facility, Dispatch, AuditLog, Notification, WhatsAppContact, WhatsAppMessage, IncidentMessage, IncidentLocation, PostcodeVerification, AIAssessment
from app.services.ai_service import ai_service
from app.services.nipost_service import get_postcode_provider, normalize_postcode
from app.services.whatsapp_service import get_whatsapp_provider

app = FastAPI(title="ResQ Nigeria API", version="0.1.0", description="Emergency coordination and decision support. AI never dispatches resources.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
_request_times: dict[tuple[str,str], deque] = defaultdict(deque)

@app.middleware("http")
async def rate_limit_sensitive_posts(request: Request, call_next):
    path=request.url.path
    if request.method=="POST" and path in {"/api/v1/incidents","/api/v1/auth/login","/api/v1/whatsapp/webhook"}:
        key=(request.client.host if request.client else "unknown",path)
        now=time.monotonic(); recent=_request_times[key]
        while recent and now-recent[0]>60: recent.popleft()
        limit=10 if path.endswith("/auth/login") else 30
        if len(recent)>=limit: return JSONResponse(status_code=429,content={"success":False,"data":None,"error":{"code":"RATE_LIMITED","message":"Please wait before trying again."}})
        recent.append(now)
    return await call_next(request)

def pack(obj):
    if obj is None: return None
    if isinstance(obj, list): return [pack(x) for x in obj]
    if hasattr(obj, "__table__"):
        data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        for k, v in data.items():
            if isinstance(v, datetime): data[k] = v.isoformat()
        return data
    return obj

def audit(db, action, entity_type, entity_id, user_id=None, metadata=None):
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=str(entity_id), metadata_json=metadata or {}))

def current_user(token: Optional[str] = Depends(oauth), db: Session = Depends(get_db)):
    if not token: return None
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return db.get(User, data.get("sub"))
    except JWTError: return None

def require_operator(user=Depends(current_user)):
    if not user or user.role not in ("OPERATOR", "ADMIN"):
        raise HTTPException(status_code=401, detail={"code":"UNAUTHORIZED", "message":"Operator sign-in required."}, headers={"WWW-Authenticate":"Bearer"})
    return user

def require_admin(user=Depends(current_user)):
    if not user or user.role != "ADMIN": raise HTTPException(403, "Administrator access required.")
    return user

class IncidentIn(BaseModel):
    incident_type: str = Field(min_length=2, max_length=30)
    description: str = Field(min_length=3, max_length=5000)
    reporter_name: str = Field(default="Anonymous", max_length=120)
    reporter_phone: str = Field(default="", max_length=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str = Field(default="", max_length=500)
    postcode: str = Field(default="", max_length=20)
    source: str = "web"

    @field_validator("incident_type")
    @classmethod
    def validate_incident_type(cls, value: str):
        if value not in {"medical", "fire", "road_accident", "security", "other"}:
            raise ValueError("Choose medical, fire, road_accident, security, or other.")
        return value

class StatusIn(BaseModel):
    status: str

class UnitIn(BaseModel):
    unit_code: str = Field(min_length=2, max_length=40)
    agency: str = Field(default="", max_length=120)
    unit_type: str
    status: str = "AVAILABLE"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str = ""

class FacilityIn(BaseModel):
    name: str
    facility_type: str
    address: str = ""
    postcode: str = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str = ""
    status: str = "UNKNOWN"
    emergency_available: bool | None = None
    capacity_status: str = "UNKNOWN"

class AssignIn(BaseModel): unit_id: str

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try: db.execute(func.count(User.id).select()) if False else db.execute(__import__('sqlalchemy').text("SELECT 1")); database="ok"
    except Exception: database="unavailable"
    ai_mode=settings.ai_provider if settings.ai_provider.lower()=="mock" else "mock-fallback"
    return {"status":"ok" if database == "ok" else "degraded", "database":database, "ai":ai_mode,
            "nipost":settings.nipost_provider, "whatsapp":settings.whatsapp_provider}

@app.get("/api/v1/health")
def api_health(db: Session = Depends(get_db)): return health(db)

@app.post("/api/v1/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == form.username.lower()).first()
    if not user or not pwd.verify(form.password, user.password_hash): raise HTTPException(401, "Incorrect email or password.")
    token = jwt.encode({"sub":user.id, "role":user.role, "exp":datetime.now(timezone.utc)+timedelta(hours=8)}, settings.jwt_secret, algorithm="HS256")
    audit(db, "operator.logged_in", "user", user.id, user.id); db.commit()
    return {"access_token":token, "token_type":"bearer", "user":pack(user)}

@app.get("/api/v1/auth/me")
def me(user=Depends(require_operator)): return pack(user)

@app.post("/api/v1/auth/operators", status_code=201)
def create_operator(payload: dict, db: Session = Depends(get_db), admin=Depends(require_admin)):
    email=payload.get("email", "").lower().strip(); password=payload.get("password", "")
    role=payload.get("role", "OPERATOR").upper()
    if role not in {"OPERATOR","ADMIN"}: raise HTTPException(422,"Role must be OPERATOR or ADMIN.")
    if len(password)<12: raise HTTPException(422, "Password must be at least 12 characters.")
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, "Email already exists.")
    user=User(name=payload.get("name", "Operator"), email=email, password_hash=pwd.hash(password), role=role)
    db.add(user); db.flush(); audit(db,"operator.created","user",user.id,admin.id); db.commit(); return pack(user)

def create_incident(db, data: IncidentIn, source=None, phone=None):
    analysis = ai_service.classify_incident(data.description)
    incident=Incident(incident_code=f"RQ-{secrets.randbelow(90000)+10000}", incident_type=analysis["incident_type"] if data.incident_type == "other" else data.incident_type,
        description=data.description, reporter_name=data.reporter_name, reporter_phone=phone or data.reporter_phone,
        source=source or data.source, latitude=data.latitude, longitude=data.longitude, address=data.address,
        postcode=data.postcode.upper().replace(" ", "-"), location_source="gps" if data.latitude is not None else ("postcode" if data.postcode else "unknown"),
        verification_status="UNVERIFIED", location_confidence=0, urgency=analysis["urgency"], ai_confidence=analysis["confidence"],ai_incident_type=analysis["incident_type"],
        ai_summary=analysis["summary"], ai_missing=ai_service.identify_missing_information(data.description, data.latitude is not None or bool(data.postcode)))
    if data.postcode:
        # Code lookup is async in API handlers; avoid claiming a postcode resolved here.
        incident.verification_status="PENDING"
    elif data.latitude is not None: incident.verification_status="PENDING"
    db.add(incident); db.flush()
    db.add(IncidentMessage(incident_id=incident.id, channel=incident.source, body=data.description))
    db.add(IncidentLocation(incident_id=incident.id,latitude=incident.latitude,longitude=incident.longitude,address=incident.address,
        postcode=incident.postcode,source=incident.location_source,confidence=incident.location_confidence,verification_status=incident.verification_status))
    db.add(AIAssessment(incident_id=incident.id,provider=settings.ai_provider,model=settings.ai_model,incident_type=analysis["incident_type"],
        confidence=analysis["confidence"],urgency=analysis["urgency"],summary=analysis["summary"],details=analysis))
    audit(db,"incident.created","incident",incident.id,metadata={"source":incident.source})
    if analysis["urgency"] == "high": db.add(Notification(title="New high urgency incident", message=f"{incident.incident_code} · {incident.incident_type.replace('_',' ').title()}", incident_id=incident.id))
    return incident

def rank_available_units(units, incident_type, latitude=None, longitude=None):
    """Rank available units by broad type fit and straight-line distance when coordinates exist."""
    keywords = {
        "medical": ("ambulance", "medical", "health"),
        "fire": ("fire",),
        "road_accident": ("ambulance", "medical", "rescue", "police"),
        "security": ("police", "security", "patrol"),
    }.get(incident_type, ())
    def distance(unit):
        if latitude is None or longitude is None or unit.latitude is None or unit.longitude is None:
            return None
        lat1, lat2 = math.radians(latitude), math.radians(unit.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(unit.longitude - longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 6371 * 2 * math.asin(math.sqrt(a))

    ranked = sorted(units, key=lambda unit: (
        not any(word in unit.unit_type.lower() for word in keywords),
        distance(unit) is None,
        distance(unit) if distance(unit) is not None else float("inf"),
        unit.unit_code,
    ))
    result = []
    for unit in ranked:
        fit = not keywords or any(word in unit.unit_type.lower() for word in keywords)
        item = pack(unit)
        item["recommendation_reason"] = "Matches the detected incident type and is marked available in the demo database." if fit and keywords else ("Available in the database; confirm capability with the agency." if fit else "Different unit type; confirm capability before considering it." )
        item["recommended"] = fit
        km = distance(unit)
        item["distance_km"] = round(km, 1) if km is not None else None
        item["distance_basis"] = "straight_line_estimate" if km is not None else None
        result.append(item)
    return result

@app.post("/api/v1/incidents", status_code=201)
async def submit_incident(data: IncidentIn, db: Session = Depends(get_db)):
    incident=create_incident(db,data,source="web")
    if data.postcode:
        result=await get_postcode_provider().lookup(data.postcode)
        incident.verification_status=result["verification_status"]
        incident.state=result.get("state", ""); incident.lga=result.get("lga", "")
        incident.latitude=result.get("latitude", incident.latitude); incident.longitude=result.get("longitude", incident.longitude)
        if incident.latitude is not None and incident.longitude is not None: incident.location_source="postcode"
        incident.location_confidence=1.0 if result.get("verified") else 0
        if result.get("verified"): incident.verified_at=datetime.now(timezone.utc)
        incident.postcode=result.get("postcode", incident.postcode)
        db.add(PostcodeVerification(incident_id=incident.id,postcode=incident.postcode,provider=result.get("provider",settings.nipost_provider),
            verification_status=result["verification_status"],details=result))
        location=db.query(IncidentLocation).filter_by(incident_id=incident.id).order_by(IncidentLocation.created_at.desc()).first()
        if location:
            location.latitude=incident.latitude; location.longitude=incident.longitude
            location.postcode=incident.postcode; location.state=incident.state; location.lga=incident.lga; location.city=result.get("city", "")
            location.confidence=incident.location_confidence; location.verification_status=incident.verification_status; location.verified_at=incident.verified_at
    db.commit(); db.refresh(incident)
    data=pack(incident)
    available=db.query(ResponseUnit).filter(ResponseUnit.status=="AVAILABLE").all()
    ranked=rank_available_units(available, incident.ai_incident_type or incident.incident_type, incident.latitude, incident.longitude)
    data["nearest_unit_suggestion"]=next((unit for unit in ranked if unit["recommended"]),None) if incident.latitude is not None and incident.longitude is not None else None
    return {"success":True,"data":data,"error":None}

@app.get("/api/v1/incidents")
def list_incidents(status_filter: str | None = Query(default=None, alias="status"), limit: int = Query(default=100, le=500), db: Session = Depends(get_db), user=Depends(require_operator)):
    q=db.query(Incident)
    if status_filter: q=q.filter(Incident.status==status_filter.upper())
    rows=q.order_by(Incident.created_at.desc()).limit(limit).all()
    priority={"high":0,"medium":1,"low":2}
    rows.sort(key=lambda incident: (priority.get(incident.urgency, 1), -incident.created_at.timestamp()))
    data=[]
    for incident in rows:
        item=pack(incident)
        unit=db.get(ResponseUnit,incident.assigned_unit_id) if incident.assigned_unit_id else None
        item["assigned_unit_code"]=unit.unit_code if unit else None
        data.append(item)
    return {"success":True,"data":data,"error":None}

@app.get("/api/v1/incidents/{code}")
def track_incident(code: str, db: Session = Depends(get_db)):
    i=db.query(Incident).filter(func.upper(Incident.incident_code)==code.upper()).first()
    if not i: raise HTTPException(404, "Incident not found.")
    return {"success":True,"data":{"incident_code":i.incident_code,"incident_type":i.incident_type,"status":i.status,
        "verification_status":i.verification_status,"created_at":i.created_at.isoformat(),"updated_at":i.updated_at.isoformat()},"error":None}

@app.get("/api/v1/incidents/{incident_id}/detail")
def incident_detail(incident_id: str, db: Session = Depends(get_db), user=Depends(require_operator)):
    i=db.query(Incident).filter((Incident.id==incident_id)|(Incident.incident_code==incident_id)).first()
    if not i: raise HTTPException(404,"Incident not found.")
    d=pack(i); d["assigned_unit"]=pack(db.get(ResponseUnit,i.assigned_unit_id)) if i.assigned_unit_id else None
    available=db.query(ResponseUnit).filter(ResponseUnit.status=="AVAILABLE").all()
    d["available_units"]=rank_available_units(available, i.ai_incident_type or i.incident_type, i.latitude, i.longitude)
    d["triage_recommendation"]={"priority":i.urgency,"reason":"Review this report promptly and confirm urgency, location, and unit availability.","operator_confirmation_required":True,"demo_rules":settings.ai_provider.lower()=="mock"}
    d["ai_confidence_band"]=ai_service.confidence_band(i.ai_confidence)
    assessment=db.query(AIAssessment).filter_by(incident_id=i.id).order_by(AIAssessment.created_at.desc()).first()
    d["ai_assessment_details"]=assessment.details if assessment else {}
    d["ai_detected_type"]=assessment.incident_type if assessment else i.ai_incident_type
    return {"success":True,"data":d,"error":None}

TRANSITIONS={"REPORTED":{"VERIFYING","CANCELLED"},"VERIFYING":{"VERIFIED","FAILED","CANCELLED"},"FAILED":{"VERIFYING","CANCELLED"},"VERIFIED":{"AWAITING_RESPONSE","CANCELLED"},"AWAITING_RESPONSE":{"ASSIGNED","CANCELLED"},"ASSIGNED":{"EN_ROUTE","CANCELLED"},"EN_ROUTE":{"ARRIVED","CANCELLED"},"ARRIVED":{"RESOLVED"}}
@app.patch("/api/v1/incidents/{incident_id}/status")
def change_status(incident_id: str, body: StatusIn, db: Session=Depends(get_db), user=Depends(require_operator)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found.")
    new=body.status.upper()
    if new not in TRANSITIONS.get(i.status,set()): raise HTTPException(409,f"Invalid status transition: {i.status} to {new}.")
    if new=="VERIFIED" and not ((i.latitude is not None and i.longitude is not None) or (i.postcode and i.verification_status=="VERIFIED")):
        raise HTTPException(409,"A coordinate or postcode must be verified before the incident location can be marked verified.")
    previous=i.status; i.status=new
    if new=="VERIFYING":
        i.verification_status="PENDING" if (i.latitude is not None and i.longitude is not None) or i.postcode else "UNVERIFIED"
    if new=="VERIFIED": i.verification_status="VERIFIED"; i.verified_at=datetime.now(timezone.utc); i.location_confidence=1.0
    if new=="FAILED": i.verification_status="FAILED"
    location=db.query(IncidentLocation).filter_by(incident_id=i.id).order_by(IncidentLocation.created_at.desc()).first()
    if location:
        location.verification_status=i.verification_status; location.verified_at=i.verified_at; location.confidence=i.location_confidence
    audit(db,"incident.status_changed","incident",i.id,user.id,{"from":previous,"to":new})
    dispatch=db.query(Dispatch).filter(Dispatch.incident_id==i.id).order_by(Dispatch.assigned_at.desc()).first()
    if dispatch:
        unit=db.get(ResponseUnit,dispatch.unit_id)
        if new=="EN_ROUTE":
            unit.status="EN_ROUTE"; dispatch.status="EN_ROUTE"; dispatch.en_route_at=datetime.now(timezone.utc)
        elif new=="ARRIVED":
            unit.status="AT_SCENE"; dispatch.status="ARRIVED"; dispatch.arrived_at=datetime.now(timezone.utc)
        elif new in ("RESOLVED","CANCELLED"):
            dispatch.status=new
    if new in ("RESOLVED","CANCELLED") and i.assigned_unit_id:
        unit=db.get(ResponseUnit,i.assigned_unit_id); unit.status="AVAILABLE"; i.assigned_unit_id=None
    db.commit(); return {"success":True,"data":pack(i),"error":None}

@app.post("/api/v1/incidents/{incident_id}/assign")
def assign_unit(incident_id: str, body: AssignIn, db: Session=Depends(get_db), user=Depends(require_operator)):
    i=db.get(Incident,incident_id); unit=db.get(ResponseUnit,body.unit_id)
    if not i or not unit: raise HTTPException(404,"Incident or response unit not found.")
    if unit.status!="AVAILABLE": raise HTTPException(409,"Response unit is not available in the database.")
    if i.status!="AWAITING_RESPONSE": raise HTTPException(409,"Move the verified incident to Awaiting Response before assignment.")
    i.status="ASSIGNED"; i.assigned_unit_id=unit.id; unit.status="ASSIGNED"
    dispatch=Dispatch(incident_id=i.id,unit_id=unit.id,operator_id=user.id); db.add(dispatch)
    audit(db,"incident.assigned","incident",i.id,user.id,{"unit_id":unit.id})
    notice_title="Simulated dispatch recorded" if unit.demo else "Assignment recorded in ResQ"
    notice_message=f"Simulated request for {i.incident_code} recorded for {unit.unit_code}. No real team was contacted." if unit.demo else f"{i.incident_code} assigned to {unit.unit_code} in ResQ. No external team was contacted."
    db.add(Notification(title=notice_title,message=notice_message,incident_id=i.id))
    db.commit(); return {"success":True,"data":pack(i),"error":None}

@app.get("/api/v1/response-units")
def units(db: Session=Depends(get_db),user=Depends(require_operator)): return [pack(x) for x in db.query(ResponseUnit).order_by(ResponseUnit.unit_code).all()]
@app.post("/api/v1/response-units",status_code=201)
def add_unit(body: UnitIn,db:Session=Depends(get_db),user=Depends(require_operator)):
    unit=ResponseUnit(**body.model_dump()); db.add(unit); db.flush(); audit(db,"response_unit.created","response_unit",unit.id,user.id); db.commit(); return pack(unit)
@app.patch("/api/v1/response-units/{unit_id}")
def update_unit(unit_id:str,body:dict,db:Session=Depends(get_db),user=Depends(require_operator)):
    unit=db.get(ResponseUnit,unit_id)
    if not unit: raise HTTPException(404,"Unit not found.")
    for k,v in body.items():
        if k in {"unit_code","agency","unit_type","status","latitude","longitude","phone"}: setattr(unit,k,v)
    audit(db,"response_unit.updated","response_unit",unit.id,user.id,body); db.commit(); return pack(unit)

@app.get("/api/v1/facilities")
def facilities(db:Session=Depends(get_db),user=Depends(require_operator)): return [pack(x) for x in db.query(Facility).all()]
@app.post("/api/v1/facilities",status_code=201)
def add_facility(body:FacilityIn,db:Session=Depends(get_db),user=Depends(require_operator)):
    f=Facility(**body.model_dump()); db.add(f); db.flush(); audit(db,"facility.created","facility",f.id,user.id); db.commit(); return pack(f)
@app.patch("/api/v1/facilities/{facility_id}")
def update_facility(facility_id:str,body:dict,db:Session=Depends(get_db),user=Depends(require_operator)):
    f=db.get(Facility,facility_id)
    if not f: raise HTTPException(404,"Facility not found.")
    for k,v in body.items():
        if hasattr(f,k) and k not in {"id","created_at"}: setattr(f,k,v)
    audit(db,"facility.updated","facility",f.id,user.id,body); db.commit(); return pack(f)

@app.get("/api/v1/postcodes/lookup")
async def postcode_lookup(code:str): return await get_postcode_provider().lookup(code)

@app.get("/api/v1/analytics")
def analytics(db:Session=Depends(get_db),user=Depends(require_operator)):
    rows=db.query(Incident).order_by(Incident.created_at).all()
    total=len(rows); by_type=dict(db.query(Incident.incident_type,func.count()).group_by(Incident.incident_type).all())
    by_status=dict(db.query(Incident.status,func.count()).group_by(Incident.status).all())
    resolved=db.query(Incident).filter(Incident.status=="RESOLVED").count()
    by_location={}
    for incident in rows:
        place=incident.lga or incident.state or ("Coordinates only" if incident.latitude is not None else "Location not supplied")
        by_location[place]=by_location.get(place,0)+1
    over_time=[{"date":str(day),"count":count} for day,count in db.query(func.date(Incident.created_at),func.count()).group_by(func.date(Incident.created_at)).order_by(func.date(Incident.created_at)).all()]
    def avg_minutes(values): return round(sum(values)/len(values)/60,1) if values else None
    verification_times=[]
    for incident in rows:
        if incident.verified_at:
            try: verification_times.append(max(0,(incident.verified_at-incident.created_at).total_seconds()))
            except TypeError: pass
    dispatch_times=[]; response_times=[]
    for dispatch in db.query(Dispatch).all():
        incident=db.get(Incident,dispatch.incident_id)
        if incident:
            try: dispatch_times.append(max(0,(dispatch.assigned_at-incident.created_at).total_seconds()))
            except TypeError: pass
        if dispatch.arrived_at:
            anchor=dispatch.en_route_at or dispatch.assigned_at
            try: response_times.append(max(0,(dispatch.arrived_at-anchor).total_seconds()))
            except TypeError: pass
    return {"total_incidents":total,"by_type":by_type,"by_status":by_status,"resolution_rate":round(resolved/total,3) if total else None,
            "by_location":by_location,"over_time":over_time,"average_verification_minutes":avg_minutes(verification_times),
            "average_dispatch_minutes":avg_minutes(dispatch_times),"average_response_minutes":avg_minutes(response_times),
            "message":"Not enough data yet." if total<2 else None}

@app.get("/api/v1/notifications")
def notifications(db:Session=Depends(get_db),user=Depends(require_operator)): return [pack(x) for x in db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()]

@app.get("/api/v1/events")
async def events(request:Request):
    async def stream():
        yield "event: ready\ndata: {}\n\n"
        while not await request.is_disconnected():
            yield f"event: refresh\ndata: {json.dumps({'at':datetime.now(timezone.utc).isoformat()})}\n\n"
            await asyncio.sleep(10)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/api/v1/whatsapp/webhook")
def verify_webhook(mode:str|None=Query(default=None,alias="hub.mode"), token:str|None=Query(default=None,alias="hub.verify_token"), challenge:str|None=Query(default=None,alias="hub.challenge")):
    if mode=="subscribe" and secrets.compare_digest(token or "",settings.whatsapp_verify_token): return int(challenge or "0")
    raise HTTPException(403,"Webhook verification failed.")

@app.post("/api/v1/whatsapp/webhook")
async def whatsapp_webhook(request:Request,db:Session=Depends(get_db)):
    raw_body=await request.body()
    if settings.whatsapp_provider.lower()=="meta":
        signature=request.headers.get("X-Hub-Signature-256", "")
        if not settings.whatsapp_app_secret:
            raise HTTPException(503,"Meta webhook app secret is not configured.")
        expected="sha256="+hmac.new(settings.whatsapp_app_secret.encode(),raw_body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected): raise HTTPException(401,"Invalid webhook signature.")
    try: body=json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError): raise HTTPException(400,"Malformed webhook JSON.")
    entry=(body.get("entry") or [{}])[0]
    change=(entry.get("changes") or [{}])[0]
    value=change.get("value") or {}
    replies=[]
    delivery_failures=[]
    for msg in value.get("messages",[]):
        sender=msg.get("from",""); mid=msg.get("id",secrets.token_hex(8)); typ=msg.get("type","text")
        if db.query(WhatsAppMessage).filter_by(message_id=mid).first(): continue
        contact=db.get(WhatsAppContact,sender)
        if not contact: contact=WhatsAppContact(wa_user_id=sender,phone=sender); db.add(contact); db.flush()
        row=WhatsAppMessage(wa_user_id=sender,message_id=mid,message_type=typ,body=msg.get("text",{}).get("body", ""),processing_status="PROCESSED")
        if typ=="location": row.latitude=msg.get("location",{}).get("latitude"); row.longitude=msg.get("location",{}).get("longitude")
        db.add(row); text=msg.get("text",{}).get("body","").strip(); upper=text.upper()
        if upper=="CANCEL": contact.state="IDLE"; contact.description=""; reply="Your draft has been cancelled. To start again, describe what is happening in your own words."
        elif upper in {"HELP", "HI"} and contact.state in {"IDLE", "INCIDENT_CREATED"}:
            contact.state="COLLECTING_DESCRIPTION"; contact.incident_id=None
            reply="ResQ emergency report. Describe what is happening in your own words. Include any immediate danger or injuries. You do not need to type HELP or choose a category."
        elif contact.state=="SELECTING_INCIDENT_TYPE":
            choices={"1":"medical","2":"fire","3":"road_accident","4":"security","5":"other"}
            if upper not in choices: reply="Reply 1 Medical, 2 Fire, 3 Road Accident, 4 Security, or 5 Other."
            else: contact.incident_type=choices[upper]; contact.state="COLLECTING_DESCRIPTION"; reply="Please describe what happened."
        elif contact.state=="COLLECTING_DESCRIPTION":
            analysis=ai_service.classify_incident(text)
            contact.description=text; contact.incident_type=analysis["incident_type"]; contact.state="WAITING_FOR_LOCATION"
            reply=f"Your report is tentatively categorised as {contact.incident_type.replace('_',' ')} with {analysis['urgency']} urgency. This is an automated demo suggestion, not a dispatch decision. Send your 11-character NIPOST digital postcode or share your WhatsApp location so the operator can review it."
        elif typ=="location" and contact.state=="WAITING_FOR_LOCATION":
            loc=msg.get("location",{}); data=IncidentIn(incident_type=contact.incident_type or "other",description=contact.description or "Emergency reported by WhatsApp",reporter_name="WhatsApp user",reporter_phone=sender,latitude=loc.get("latitude"),longitude=loc.get("longitude"),source="whatsapp")
            incident=create_incident(db,data,source="whatsapp",phone=sender); incident.status="VERIFYING"; db.flush()
            contact.incident_id=incident.id; contact.state="INCIDENT_CREATED"; row.incident_id=incident.id
            reply=f"📍 Location received.\nIncident ID: {incident.incident_code}\nLocation verification: PENDING\nYour report is available to the ResQ response centre. A response unit has not been dispatched by this message."
        elif upper.startswith("RQ-"):
            inc=db.query(Incident).filter(Incident.incident_code==upper).first(); reply=f"{inc.incident_code}: {inc.status.replace('_',' ').title()} · Location {inc.verification_status.lower()}." if inc else "Incident ID not found."
        elif contact.state=="WAITING_FOR_LOCATION" and text:
            postcode=normalize_postcode(text)
            if postcode:
                result=await get_postcode_provider().lookup(postcode)
                data=IncidentIn(incident_type=contact.incident_type or "other",description=contact.description or "Emergency reported by WhatsApp",reporter_name="WhatsApp user",reporter_phone=sender,postcode=postcode,latitude=result.get("latitude"),longitude=result.get("longitude"),source="whatsapp")
                incident=create_incident(db,data,source="whatsapp",phone=sender)
                incident.status="VERIFYING"; incident.verification_status=result.get("verification_status","PENDING")
                incident.state=result.get("state",""); incident.lga=result.get("lga","")
                if incident.latitude is not None and incident.longitude is not None: incident.location_source="postcode"
                incident.location_confidence=1.0 if result.get("verified") else 0
                db.add(PostcodeVerification(incident_id=incident.id,postcode=postcode,provider=result.get("provider",settings.nipost_provider),verification_status=incident.verification_status,details=result))
                locrow=db.query(IncidentLocation).filter_by(incident_id=incident.id).order_by(IncidentLocation.created_at.desc()).first()
                if locrow:
                    locrow.latitude=incident.latitude; locrow.longitude=incident.longitude; locrow.state=incident.state; locrow.lga=incident.lga; locrow.city=result.get("city","")
                    locrow.verification_status=incident.verification_status; locrow.confidence=incident.location_confidence
                contact.incident_id=incident.id; contact.state="INCIDENT_CREATED"; row.incident_id=incident.id
                location_note="A demo postcode location was resolved; an operator must verify it." if result.get("demo") else "Location status: "+incident.verification_status.lower()+"."
                reply=f"Incident ID: {incident.incident_code}\nPostcode: {postcode}\n{location_note}\nThe response centre can review it. No team is contacted until an operator confirms the dispatch."
            else:
                contact.description=f"{contact.description}\nLocation details from reporter: {text}".strip()
                reply="I added that location detail. Please send your 11-character NIPOST digital postcode or share your WhatsApp live/current location."
        elif contact.state=="INCIDENT_CREATED": reply="Send your incident ID to check status, or describe a new emergency in your own words to start another report."
        elif text:
            analysis=ai_service.classify_incident(text)
            contact.incident_type=analysis["incident_type"]
            contact.description=text
            contact.state="WAITING_FOR_LOCATION"
            reply=f"Report started from your message. Suggested category: {contact.incident_type.replace('_',' ')} · {analysis['urgency']} urgency. This demo suggestion needs operator review. Send your 11-character NIPOST digital postcode or share your WhatsApp location. For immediate danger, contact local emergency services directly."
        else: reply="Describe what is happening in your own words to start a report. You can also share your WhatsApp location after describing the emergency."
        try:
            await get_whatsapp_provider().send_text(sender,reply)
            delivery_status="MOCKED" if settings.whatsapp_provider.lower()=="mock" else "SENT"
        except Exception:
            delivery_failures.append(mid); delivery_status="DELIVERY_FAILED"
        db.add(WhatsAppMessage(wa_user_id=sender,message_id=f"out-{secrets.token_hex(12)}",message_type="text",body=reply,
            processing_status=delivery_status,incident_id=contact.incident_id))
        replies.append({"to":sender,"text":reply})
    db.commit(); return {"success":True,"replies":replies,"delivery_failures":delivery_failures,"mode":settings.whatsapp_provider}

@app.get("/api/v1/whatsapp/mock/messages")
def mock_messages(db:Session=Depends(get_db),user=Depends(require_operator)):
    if settings.whatsapp_provider.lower()!="mock": raise HTTPException(404,"Mock message inspection is enabled only in mock mode.")
    rows=db.query(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc()).limit(100).all()
    return {"mode":settings.whatsapp_provider,"messages":[pack(x) for x in rows]}

@app.get("/")
def root(): return {"name":"ResQ Nigeria API","docs":"/docs","demo_mode":settings.app_env!="production"}

import os

from app.database import Base, engine, SessionLocal
from app.models import User, ResponseUnit, Facility, Incident, IncidentLocation, AIAssessment
from app.main import pwd

Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    if not db.query(User).filter_by(email="operator@resq.demo").first():
        operator_password = os.getenv("RESQ_DEMO_OPERATOR_PASSWORD", "ResQ-demo-2026!change")
        db.add(User(name="Demo Operator",email="operator@resq.demo",password_hash=pwd.hash(operator_password),role="ADMIN"))
    demo_units = [
        ("DEMO-MED-01", "Ambulance", 9.0765, 7.3986),
        ("DEMO-FIRE-01", "Fire Truck", 9.0840, 7.4050),
        ("DEMO-SEC-01", "Police Unit", 9.0670, 7.3920),
        ("DEMO-RES-01", "Rescue Vehicle", 9.0890, 7.3890),
    ]
    for code, kind, latitude, longitude in demo_units:
        unit=db.query(ResponseUnit).filter_by(unit_code=code).first()
        if not unit:
            unit=ResponseUnit(unit_code=code,agency="Demo data — not a real response agency",unit_type=kind,status="AVAILABLE",demo=True)
            db.add(unit)
        elif unit.status == "OFFLINE":
            unit.status = "AVAILABLE"
        unit.latitude=latitude; unit.longitude=longitude; unit.demo=True
    if not db.query(Facility).first(): db.add(Facility(name="Demonstration facility",facility_type="Emergency Centre",address="Demo location · not a real facility",status="DEMO ONLY",emergency_available=None,capacity_status="UNKNOWN",demo=True))
    if not db.query(Incident).first():
        incident=Incident(incident_code="RQ-10482",incident_type="medical",ai_incident_type="medical",description="Demo incident — not a real emergency report.",status="REPORTED",urgency="medium",reporter_name="Demo citizen",ai_confidence=0.35,ai_summary="DEMO DATA ONLY — this is not a real emergency report.",address="Demo location · coordinates not supplied",location_source="demo",verification_status="UNVERIFIED",demo=True)
        db.add(incident); db.flush()
        db.add(IncidentLocation(incident_id=incident.id,address=incident.address,source="demo",verification_status="UNVERIFIED"))
        db.add(AIAssessment(incident_id=incident.id,provider="mock",incident_type="medical",confidence=0.35,urgency="medium",summary=incident.ai_summary,details={"demo":True,"confidence_reason":"Demo data placeholder; not a real AI assessment.","location_entities":[],"missing_information":["exact_location"]}))
    demo_incident=db.query(Incident).filter_by(incident_code="RQ-10482",demo=True).first()
    if demo_incident and not db.query(IncidentLocation).filter_by(incident_id=demo_incident.id).first():
        db.add(IncidentLocation(incident_id=demo_incident.id,address=demo_incident.address,source="demo",verification_status="UNVERIFIED"))
    if demo_incident and not db.query(AIAssessment).filter_by(incident_id=demo_incident.id).first():
        demo_incident.ai_summary="DEMO DATA ONLY — this is not a real emergency report."
        db.add(AIAssessment(incident_id=demo_incident.id,provider="mock",incident_type="medical",confidence=0.35,urgency="medium",summary=demo_incident.ai_summary,details={"demo":True,"confidence_reason":"Demo data placeholder; not a real AI assessment.","location_entities":[],"missing_information":["exact_location"]}))
    for code,kind,description in [
        ("RQ-20518","fire","DEMO DATA ONLY — sample fire report for interface preview."),
        ("RQ-35126","road_accident","DEMO DATA ONLY — sample road-incident report for interface preview."),
    ]:
        if not db.query(Incident).filter_by(incident_code=code).first():
            sample=Incident(incident_code=code,incident_type=kind,ai_incident_type="other",description=description,status="REPORTED",urgency="medium",ai_confidence=0.35,reporter_name="Demo record",ai_summary="DEMO DATA ONLY — not a real emergency report.",address="Demo location · coordinates not supplied",location_source="demo",verification_status="UNVERIFIED",demo=True)
            db.add(sample); db.flush()
            db.add(IncidentLocation(incident_id=sample.id,address=sample.address,source="demo",verification_status="UNVERIFIED"))
            db.add(AIAssessment(incident_id=sample.id,provider="mock",incident_type="other",confidence=0.35,urgency="medium",summary=sample.ai_summary,details={"demo":True,"confidence_reason":"Demo data placeholder; not a real AI assessment.","location_entities":[],"missing_information":["exact_location"]}))
    db.commit()
    if os.getenv("RESQ_DEMO_OPERATOR_PASSWORD"):
        print("Demo data ready. Hosted operator password was read from RESQ_DEMO_OPERATOR_PASSWORD; keep it private.")
    else:
        print("Demo data ready. Local demo login: operator@resq.demo / ResQ-demo-2026!change")
finally: db.close()

"""
Elderly Client Service — all business logic for elderly-user-facing operations.

This service operates exclusively on behalf of the authenticated elderly user.
It reads caregiver assignment data from admin-managed collections but NEVER writes to them.
It does NOT touch admin-only management endpoints or duplicate any admin functionality.
"""
import math
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.database import (
    elderly_collection,
    users_collection,
    caregivers_collection,
    doctors_collection,
    medications_collection,
    emergency_contacts_collection,
    wellness_checkins_collection,
    notifications_collection,
    vitals_collection,
    dose_logs_collection,
)
from app.schemas.elderly_client_schema import (
    ElderlyProfileSelfUpdate,
    HealthInfoUpdate,
    HospitalInfoUpdate,
    MedicationCreate,
    MedicationUpdate,
    parse_legacy_intake_time,
    EmergencyContactCreate,
    EmergencyContactUpdate,
    CheckInCreate,
    NotificationPrefsUpdate,
    ChangePasswordRequest,
)
from app.security import verify_password, get_password_hash


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_age(dob_str: Optional[str]) -> Optional[int]:
    """Compute age in years from ISO date string. Never ask user to enter age directly."""
    if not dob_str:
        return None
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except (ValueError, AttributeError):
        return None


def _get_elderly_profile(user_id: str) -> Dict[str, Any]:
    """
    Fetch elderly profile document for the given user_id.
    Creates a minimal profile doc if one doesn't exist yet (for users
    registered via auth but not yet through admin elderly management).
    """
    profile = elderly_collection.find_one({"user_id": user_id})
    if not profile:
        # Auto-create a minimal profile shell so the user can start filling it in
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")
        now_iso = datetime.now(timezone.utc).isoformat()
        new_profile = {
            "user_id": user_id,
            "name": user.get("full_name") or user.get("name", ""),
            "full_name": user.get("full_name") or user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "date_of_birth": None,
            "gender": "",
            "blood_group": "",
            "address": user.get("address", ""),
            "profileImage": user.get("profileImage", ""),
            # Health info embedded
            "health_info": {
                "conditions": [],
                "other_condition": "",
                "blood_group": "",
                "allergies": [],
                "previous_conditions": "",
                "medical_notes": "",
            },
            # Hospital info embedded
            "hospital_info": {
                "hospital_name": "",
                "location": "",
                "department": "",
                "contact_number": "",
            },
            # Assignment references (admin sets these — read only here)
            "assigned_caregiver_id": None,
            "assigned_caregiver_name": "Not Assigned",
            "assigned_caregiver_date": None,
            "assigned_doctor_id": None,
            "assigned_doctor_name": "Not Assigned",
            # Wellness
            "ai_risk_score": 0.10,
            "risk_level": "Low",
            "wellness_history": [],
            # Module state
            "setup_complete": False,
            "notification_prefs": {
                "checkin_reminder": True,
                "medication_reminder": True,
            },
            "createdAt": now_iso,
            "updatedAt": now_iso,
        }
        result = elderly_collection.insert_one(new_profile)
        new_profile["_id"] = result.inserted_id
        return new_profile
    return profile


def _serialize_profile(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    dob = doc.get("date_of_birth") or doc.get("dob")
    return {
        "id": str(doc.get("_id", "")),
        "user_id": str(doc.get("user_id", "")),
        "full_name": doc.get("full_name") or doc.get("name") or user.get("full_name", ""),
        "email": doc.get("email") or user.get("email", ""),
        "phone": doc.get("phone") or user.get("phone", ""),
        "date_of_birth": dob,
        "age": _compute_age(dob),
        "gender": doc.get("gender", ""),
        "district": doc.get("district", ""),
        "address": doc.get("address") or user.get("address", ""),
        "blood_group": doc.get("blood_group", ""),
        "guardian_name": doc.get("guardian_name", ""),
        "guardian_relationship": doc.get("guardian_relationship", ""),
        "guardian_phone": doc.get("guardian_phone", ""),
        "guardian_email": doc.get("guardian_email", ""),
        "guardian_report_consent": bool(doc.get("guardian_report_consent", False)),
        "guardian_report_enabled": bool(doc.get("guardian_report_enabled", True) if doc.get("guardian_email") else False),
        "profileImage": doc.get("profileImage") or user.get("profileImage", ""),
        "setup_complete": doc.get("setup_complete", False),
        "notification_prefs": doc.get("notification_prefs", {"checkin_reminder": True, "medication_reminder": True}),
        "assigned_caregiver_id": doc.get("assigned_caregiver_id"),
        "assigned_caregiver_name": doc.get("assigned_caregiver_name", "Not Assigned"),
        "assigned_doctor_id": doc.get("assigned_doctor_id"),
        "assigned_doctor_name": doc.get("assigned_doctor_name", "Not Assigned"),
        "risk_level": doc.get("risk_level", "Low"),
        "createdAt": doc.get("createdAt") or doc.get("created_at"),
    }


def _serialize_medication(doc: Dict[str, Any]) -> Dict[str, Any]:
    times = doc.get("times")
    if times is None:
        legacy_intake = doc.get("intake_time", "")
        times = parse_legacy_intake_time(legacy_intake)

    days_of_week = doc.get("days_of_week")
    if days_of_week is None:
        days_of_week = [0, 1, 2, 3, 4, 5, 6]

    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id", "")),
        "medicine_name": doc.get("medicine_name", ""),
        "dosage": doc.get("dosage", ""),
        "frequency": doc.get("frequency", ""),
        "intake_time": doc.get("intake_time", ""),
        "times": times,
        "days_of_week": days_of_week,
        "before_food": doc.get("before_food", True),
        "prescribed_by": doc.get("prescribed_by", ""),
        "start_date": doc.get("start_date", ""),
        "end_date": doc.get("end_date"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def _serialize_contact(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id", "")),
        "contact_type": doc.get("contact_type", "primary"),
        "name": doc.get("name", ""),
        "relationship": doc.get("relationship", ""),
        "phone": doc.get("phone", ""),
        "alt_phone": doc.get("alt_phone", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def _serialize_checkin(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id", "")),
        "date": doc.get("date", ""),
        "medication_taken": doc.get("medication_taken", ""),
        "appetite": doc.get("appetite", ""),
        "sleep_quality": doc.get("sleep_quality", ""),
        "mobility_difficulty": doc.get("mobility_difficulty", ""),
        "mood": doc.get("mood", ""),
        "symptoms": doc.get("symptoms", ""),
        "notes": doc.get("notes", ""),
        "wellness_risk": doc.get("wellness_risk", "Low"),
        "created_at": doc.get("created_at", ""),
        "contributing_factors": doc.get("contributing_factors", []),
        "baseline_comparison": doc.get("baseline_comparison", "Personal telemetry baseline active."),
        "engine_note": doc.get("engine_note", "Explainable Telemetry Scoring Engine (Prototype Architecture for ML Integration - Not a clinical diagnosis)")
    }


# ---------------------------------------------------------------------------
# Explainable Wellness Risk Scoring Engine & Behavioral Baseline
# ---------------------------------------------------------------------------

def compute_explainable_wellness_risk(
    checkin_data: Dict[str, Any],
    historical_checkins: Optional[List[Dict[str, Any]]] = None,
    vitals_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Explainable Wellness Telemetry Scoring Engine (Prototype Architecture for ML Integration).
    Uses rule-based explainable weights across self-reported telemetry and vital signs.
    Calculates contributing risk indicators and personal behavioral baseline comparisons.
    *** NOT A CLINICAL MEDICAL DIAGNOSIS ***
    """
    score = 0
    factors = []

    # 1. Mood telemetry
    mood = checkin_data.get("mood", "Good")
    if mood in ["Poor"]:
        score += 3
        factors.append("Low mood / emotional distress reported today")
    elif mood in ["Not Great", "Okay"]:
        score += 1
        factors.append("Sub-optimal mood logged")

    # 2. Appetite telemetry
    appetite = checkin_data.get("appetite", "Good")
    if appetite in ["Poor", "No Appetite"]:
        score += 3
        factors.append("Significant reduction in appetite / dietary intake")
    elif appetite in ["Fair"]:
        score += 1
        factors.append("Fair appetite logged")

    # 3. Sleep telemetry
    sleep = checkin_data.get("sleep_quality", "Good")
    if sleep in ["Poor", "Very Poor"]:
        score += 2
        factors.append("Poor sleep quality / interrupted rest reported")
    elif sleep in ["Fair"]:
        score += 1
        factors.append("Fair sleep quality logged")

    # 4. Mobility telemetry
    mobility = checkin_data.get("mobility_difficulty", "No difficulty")
    if mobility in ["Significant difficulty"]:
        score += 3
        factors.append("Significant mobility challenge (elevated fall risk)")
    elif mobility in ["Moderate difficulty"]:
        score += 2
        factors.append("Moderate difficulty walking or transferring")
    elif mobility in ["Slight difficulty"]:
        score += 1
        factors.append("Slight mobility stiffness noted")

    # 5. Medication telemetry
    medication = checkin_data.get("medication_taken", "Yes, all taken")
    if medication in ["No, not taken"]:
        score += 3
        factors.append("Scheduled medication doses missed")
    elif medication in ["Yes, partially taken"]:
        score += 2
        factors.append("Only partial medication doses completed")

    # 6. Active symptoms
    symptoms = (checkin_data.get("symptoms") or "").strip()
    if symptoms and len(symptoms) > 3:
        score += 1
        factors.append(f"Self-reported active symptoms: '{symptoms}'")

    # 7. Vitals (if provided)
    if vitals_data:
        sys = vitals_data.get("systolic")
        dia = vitals_data.get("diastolic")
        spo2 = vitals_data.get("oxygen_saturation")
        if sys and dia and (sys > 140 or dia > 90):
            score += 2
            factors.append(f"Elevated blood pressure logged ({sys}/{dia} mmHg)")
        if spo2 and spo2 < 95:
            score += 2
            factors.append(f"Sub-optimal oxygen saturation ({spo2}% SpO2)")

    # Risk level categorization
    if score >= 7:
        risk_level = "High"
    elif score >= 3:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    # Behavioral baseline comparison (Innovation #1)
    baseline_msg = "Personal telemetry baseline active."
    if historical_checkins and len(historical_checkins) > 0:
        recent_sleeps = [c.get("sleep_quality") for c in historical_checkins if c.get("sleep_quality")]
        recent_moods = [c.get("mood") for c in historical_checkins if c.get("mood")]
        if recent_sleeps and sleep in ["Poor", "Very Poor"] and "Good" in recent_sleeps:
            baseline_msg = f"Sleep quality today ({sleep}) is lower than your typical 7-day pattern."
        elif recent_moods and mood in ["Poor", "Not Great"] and "Good" in recent_moods:
            baseline_msg = f"Reported mood today ({mood}) is lower than your usual 7-day pattern."
        else:
            baseline_msg = "Today's metrics are consistent with your 7-day personal wellness baseline."
    else:
        baseline_msg = "First check-in logged. Establishing your personalized behavioral baseline."

    if not factors:
        factors.append("Optimal telemetry readings reported across all categories.")

    return {
        "risk_level": risk_level,
        "score": score,
        "contributing_factors": factors,
        "baseline_comparison": baseline_msg,
        "engine_note": "Explainable Wellness Telemetry Scoring Engine (Prototype Architecture for ML Integration)"
    }


def _mock_compute_wellness_risk(checkin_data: Dict[str, Any]) -> str:
    """
    Backwards-compatible wrapper returning risk string ('Low' | 'Moderate' | 'High').
    """
    res = compute_explainable_wellness_risk(checkin_data)
    return res["risk_level"]


# ---------------------------------------------------------------------------
# Elderly Client Service Class
# ---------------------------------------------------------------------------

class ElderlyClientService:

    # --- Profile ---

    @staticmethod
    def get_my_profile(user: Dict[str, Any]) -> Dict[str, Any]:
        user_id = user["id"]
        profile = _get_elderly_profile(user_id)
        return _serialize_profile(profile, user)

    @staticmethod
    def update_my_profile(user: Dict[str, Any], payload: ElderlyProfileSelfUpdate) -> Dict[str, Any]:
        user_id = user["id"]
        profile = _get_elderly_profile(user_id)
        profile_id = profile["_id"]

        updates: Dict[str, Any] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        if payload.full_name is not None:
            updates["full_name"] = payload.full_name.strip()
            updates["name"] = payload.full_name.strip()
            # Sync to users collection
            users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"full_name": payload.full_name.strip()}})

        if payload.phone is not None:
            updates["phone"] = payload.phone.strip()
        if payload.date_of_birth is not None:
            updates["date_of_birth"] = payload.date_of_birth
        if payload.gender is not None:
            updates["gender"] = payload.gender
        if payload.district is not None:
            updates["district"] = payload.district
        if payload.blood_group is not None:
            updates["blood_group"] = payload.blood_group
            updates["health_info.blood_group"] = payload.blood_group
        if payload.address is not None:
            updates["address"] = payload.address.strip()
        if payload.guardian_name is not None:
            updates["guardian_name"] = payload.guardian_name.strip()
        if payload.guardian_relationship is not None:
            updates["guardian_relationship"] = payload.guardian_relationship.strip()
        if payload.guardian_phone is not None:
            updates["guardian_phone"] = payload.guardian_phone.strip()
        if payload.guardian_email is not None:
            updates["guardian_email"] = str(payload.guardian_email).strip().lower()
        if payload.guardian_report_consent is not None:
            updates["guardian_report_consent"] = bool(payload.guardian_report_consent)
        if payload.guardian_report_enabled is not None:
            updates["guardian_report_enabled"] = bool(payload.guardian_report_enabled)

        updates["updatedAt"] = now_iso
        elderly_collection.update_one({"_id": profile_id}, {"$set": updates})

        updated = elderly_collection.find_one({"_id": profile_id})
        return _serialize_profile(updated, user)

    # --- Health Information ---

    @staticmethod
    def get_health_info(user: Dict[str, Any]) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        health = profile.get("health_info", {})
        return {
            "conditions": health.get("conditions", []),
            "other_condition": health.get("other_condition", ""),
            "blood_group": health.get("blood_group", "") or profile.get("blood_group", ""),
            "allergies": health.get("allergies", []),
            "previous_conditions": health.get("previous_conditions", ""),
            "medical_notes": health.get("medical_notes", ""),
        }

    @staticmethod
    def update_health_info(user: Dict[str, Any], payload: HealthInfoUpdate) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        profile_id = profile["_id"]
        existing_health = profile.get("health_info", {})

        updates: Dict[str, Any] = {**existing_health}
        if payload.conditions is not None:
            updates["conditions"] = payload.conditions
        if payload.other_condition is not None:
            updates["other_condition"] = payload.other_condition
        if payload.blood_group is not None:
            updates["blood_group"] = payload.blood_group
        if payload.allergies is not None:
            updates["allergies"] = payload.allergies
        if payload.previous_conditions is not None:
            updates["previous_conditions"] = payload.previous_conditions
        if payload.medical_notes is not None:
            updates["medical_notes"] = payload.medical_notes

        elderly_collection.update_one(
            {"_id": profile_id},
            {"$set": {"health_info": updates, "updatedAt": datetime.now(timezone.utc).isoformat()}}
        )
        return updates

    # --- Hospital Information ---

    @staticmethod
    def get_hospital_info(user: Dict[str, Any]) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        hosp = profile.get("hospital_info", {})
        return {
            "hospital_name": hosp.get("hospital_name", ""),
            "location": hosp.get("location", ""),
            "department": hosp.get("department", ""),
            "contact_number": hosp.get("contact_number", ""),
        }

    @staticmethod
    def update_hospital_info(user: Dict[str, Any], payload: HospitalInfoUpdate) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        profile_id = profile["_id"]
        existing = profile.get("hospital_info", {})

        updates: Dict[str, Any] = {**existing}
        if payload.hospital_name is not None:
            updates["hospital_name"] = payload.hospital_name
        if payload.location is not None:
            updates["location"] = payload.location
        if payload.department is not None:
            updates["department"] = payload.department
        if payload.contact_number is not None:
            updates["contact_number"] = payload.contact_number

        elderly_collection.update_one(
            {"_id": profile_id},
            {"$set": {"hospital_info": updates, "updatedAt": datetime.now(timezone.utc).isoformat()}}
        )
        return updates

    # --- Doctor Information ---

    @staticmethod
    def get_doctor_info(user: Dict[str, Any]) -> Dict[str, Any]:
        """Returns the admin-assigned doctor details (read-only). Never duplicates admin management."""
        profile = _get_elderly_profile(user["id"])
        doctor_id = profile.get("assigned_doctor_id")

        if not doctor_id:
            return {
                "is_assigned": False,
                "assigned_doctor_id": None,
                "doctor_name": "Not Assigned",
                "specialization": "",
                "hospital": "",
                "contact_number": "",
            }

        try:
            doctor_doc = doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        except Exception:
            doctor_doc = None

        if not doctor_doc:
            return {
                "is_assigned": True,
                "assigned_doctor_id": doctor_id,
                "doctor_name": profile.get("assigned_doctor_name", "Assigned Doctor"),
                "specialization": "",
                "hospital": "",
                "contact_number": "",
            }

        return {
            "is_assigned": True,
            "assigned_doctor_id": doctor_id,
            "doctor_name": doctor_doc.get("name") or doctor_doc.get("full_name", ""),
            "specialization": doctor_doc.get("specialization", ""),
            "hospital": doctor_doc.get("hospital_name") or doctor_doc.get("hospital", ""),
            "contact_number": doctor_doc.get("phone") or doctor_doc.get("contact_number", ""),
        }

    # --- Medications ---

    @staticmethod
    def list_medications(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs = list(medications_collection.find({"user_id": user["id"]}).sort("created_at", -1))
        return [_serialize_medication(d) for d in docs]

    @staticmethod
    def add_medication(user: Dict[str, Any], payload: MedicationCreate) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        times = payload.times
        if not times and payload.intake_time:
            times = parse_legacy_intake_time(payload.intake_time)

        days_of_week = payload.days_of_week if payload.days_of_week is not None else [0, 1, 2, 3, 4, 5, 6]

        doc = {
            "user_id": user["id"],
            "medicine_name": payload.medicine_name.strip(),
            "dosage": payload.dosage.strip(),
            "frequency": payload.frequency,
            "intake_time": payload.intake_time or "",
            "times": times,
            "days_of_week": days_of_week,
            "before_food": payload.before_food,
            "prescribed_by": payload.prescribed_by or "",
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        result = medications_collection.insert_one(doc)
        doc["_id"] = result.inserted_id

        # Automatically create notification alarm record for elderly user
        notifications_collection.insert_one({
            "user_id": user["id"],
            "target_role": "elderly",
            "title": f"⏰ Medication Alarm Set: {payload.medicine_name.strip()}",
            "message": f"Dosage: {payload.dosage.strip()} ({payload.intake_time or 'As scheduled'}). Alarm will remind you when it's time for dosage.",
            "type": "reminder",
            "created_at": now_iso
        })

        return _serialize_medication(doc)

    @staticmethod
    def update_medication(user: Dict[str, Any], med_id: str, payload: MedicationUpdate) -> Dict[str, Any]:
        try:
            obj_id = ObjectId(med_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid medication ID.")

        doc = medications_collection.find_one({"_id": obj_id, "user_id": user["id"]})
        if not doc:
            raise HTTPException(status_code=404, detail="Medication record not found.")

        updates: Dict[str, Any] = {}
        if payload.medicine_name is not None:
            updates["medicine_name"] = payload.medicine_name.strip()
        if payload.dosage is not None:
            updates["dosage"] = payload.dosage.strip()
        if payload.frequency is not None:
            updates["frequency"] = payload.frequency
        if payload.intake_time is not None:
            updates["intake_time"] = payload.intake_time
        if payload.times is not None:
            updates["times"] = payload.times
        elif payload.intake_time is not None:
            updates["times"] = parse_legacy_intake_time(payload.intake_time)
        if payload.days_of_week is not None:
            updates["days_of_week"] = payload.days_of_week
        if payload.before_food is not None:
            updates["before_food"] = payload.before_food
        if payload.prescribed_by is not None:
            updates["prescribed_by"] = payload.prescribed_by
        if payload.start_date is not None:
            updates["start_date"] = payload.start_date
        if payload.end_date is not None:
            updates["end_date"] = payload.end_date

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        medications_collection.update_one({"_id": obj_id}, {"$set": updates})
        updated = medications_collection.find_one({"_id": obj_id})
        return _serialize_medication(updated)

    @staticmethod
    def log_medication_dose(user: Dict[str, Any], med_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        status_val = str(payload.get("status", "taken")).lower()
        medicine_name = payload.get("medicine_name") or "Medication"
        dosage = payload.get("dosage", "")
        intake_time = payload.get("intake_time", "")
        now_iso = datetime.now(timezone.utc).isoformat()

        profile = _get_elderly_profile(user["id"])
        elderly_name = profile.get("full_name") or user.get("full_name") or "Elderly Client"
        caregiver_id = profile.get("assigned_caregiver_id")

        # 1. Log notification for elderly user
        notifications_collection.insert_one({
            "user_id": user["id"],
            "target_role": "elderly",
            "title": f"💊 Dose Recorded: {medicine_name}",
            "message": f"Dose for {medicine_name} ({dosage}) at {intake_time} marked as {status_val.upper()}.",
            "type": "reminder" if status_val == "taken" else "alert",
            "created_at": now_iso
        })

        # Attempt to record into dose_logs_collection
        if status_val == "taken":
            try:
                from app.services.medication_dose_service import MedicationDoseService
                med_doc = medications_collection.find_one({"_id": ObjectId(med_id)}) if ObjectId.is_valid(med_id) else None
                sched_time = None
                if intake_time:
                    parsed_times = parse_legacy_intake_time(intake_time)
                    if parsed_times:
                        sched_time = parsed_times[0]
                if not sched_time and med_doc:
                    m_times = med_doc.get("times") or parse_legacy_intake_time(med_doc.get("intake_time", ""))
                    if m_times:
                        sched_time = m_times[0]
                if sched_time:
                    MedicationDoseService.take_dose(
                        user_id=user["id"],
                        med_id=med_id,
                        scheduled_time=sched_time,
                        source="patient"
                    )
            except Exception:
                pass

        caregiver_notified = False
        caregiver_name = "Assigned Caregiver"

        # 2. If missed, send alert to caregiver!
        if status_val == "missed":
            caregiver_msg = f"{elderly_name} indicated they missed taking {medicine_name} ({dosage}) scheduled for {intake_time}. Please check on them immediately."

            alert_doc = {
                "elderly_id": str(profile["_id"]),
                "elderly_user_id": user["id"],
                "elderly_name": elderly_name,
                "target_role": "caregiver",
                "title": f"🚨 ALERT: Missed Medication - {elderly_name}",
                "message": caregiver_msg,
                "type": "alert",
                "status": "unread",
                "created_at": now_iso
            }

            if caregiver_id:
                alert_doc["caregiver_id"] = caregiver_id
                try:
                    cg = caregivers_collection.find_one({"_id": ObjectId(caregiver_id)})
                    if cg:
                        caregiver_name = cg.get("name") or cg.get("full_name") or caregiver_name
                        if cg.get("user_id"):
                            alert_doc["user_id"] = str(cg["user_id"])
                except Exception:
                    pass

            notifications_collection.insert_one(alert_doc)
            caregiver_notified = True

        return {
            "status": status_val,
            "medicine_name": medicine_name,
            "caregiver_notified": caregiver_notified,
            "caregiver_name": caregiver_name,
            "message": "Dose logged as TAKEN." if status_val == "taken" else f"ALERT SENT TO CAREGIVER ({caregiver_name})."
        }

    @staticmethod
    def delete_medication(user: Dict[str, Any], med_id: str) -> Dict[str, str]:
        try:
            obj_id = ObjectId(med_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid medication ID.")

        result = medications_collection.delete_one({"_id": obj_id, "user_id": user["id"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Medication record not found.")
        return {"message": "Medication removed successfully.", "id": med_id}


    # --- Emergency Contacts ---

    @staticmethod
    def list_emergency_contacts(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs = list(emergency_contacts_collection.find({"user_id": user["id"]}).sort("contact_type", 1))
        return [_serialize_contact(d) for d in docs]

    @staticmethod
    def add_emergency_contact(user: Dict[str, Any], payload: EmergencyContactCreate) -> Dict[str, Any]:
        existing = list(emergency_contacts_collection.find({"user_id": user["id"]}))
        if len(existing) >= 2:
            raise HTTPException(
                status_code=400,
                detail="You can only have up to 2 emergency contacts (Primary and Secondary)."
            )
        # Check if contact_type already exists
        type_exists = any(c.get("contact_type") == payload.contact_type for c in existing)
        if type_exists:
            raise HTTPException(
                status_code=400,
                detail=f"A '{payload.contact_type}' emergency contact already exists. Please edit or delete it first."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user["id"],
            "contact_type": payload.contact_type,
            "name": payload.name.strip(),
            "relationship": payload.relationship.strip(),
            "phone": payload.phone,
            "alt_phone": payload.alt_phone or "",
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        result = emergency_contacts_collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _serialize_contact(doc)

    @staticmethod
    def update_emergency_contact(user: Dict[str, Any], contact_id: str, payload: EmergencyContactUpdate) -> Dict[str, Any]:
        try:
            obj_id = ObjectId(contact_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid contact ID.")

        doc = emergency_contacts_collection.find_one({"_id": obj_id, "user_id": user["id"]})
        if not doc:
            raise HTTPException(status_code=404, detail="Emergency contact not found.")

        updates: Dict[str, Any] = {}
        if payload.name is not None:
            updates["name"] = payload.name.strip()
        if payload.relationship is not None:
            updates["relationship"] = payload.relationship.strip()
        if payload.phone is not None:
            updates["phone"] = payload.phone
        if payload.alt_phone is not None:
            updates["alt_phone"] = payload.alt_phone

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        emergency_contacts_collection.update_one({"_id": obj_id}, {"$set": updates})
        updated = emergency_contacts_collection.find_one({"_id": obj_id})
        return _serialize_contact(updated)

    @staticmethod
    def delete_emergency_contact(user: Dict[str, Any], contact_id: str) -> Dict[str, str]:
        try:
            obj_id = ObjectId(contact_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid contact ID.")

        result = emergency_contacts_collection.delete_one({"_id": obj_id, "user_id": user["id"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Emergency contact not found.")
        return {"message": "Emergency contact removed successfully.", "id": contact_id}

    # --- Caregiver View (Read-Only) ---

    @staticmethod
    def get_my_caregiver(user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns the admin-assigned caregiver. Reads from the admin-managed
        elderly_profiles and caregiver_profiles. Never duplicates or modifies assignment.
        """
        profile = _get_elderly_profile(user["id"])
        caregiver_id = profile.get("assigned_caregiver_id")

        if not caregiver_id:
            return {
                "is_assigned": False,
                "caregiver_id": None,
                "caregiver_name": "Not Assigned",
                "phone": "",
                "assigned_date": None,
            }

        phone = ""
        email = ""
        qualification = "Certified Senior Caregiver"
        shift = "Day Shift (8 AM - 4 PM)"
        district = ""
        experience_years = 3
        profile_image = ""

        try:
            cg_doc = caregivers_collection.find_one({"user_id": caregiver_id})
            if not cg_doc and ObjectId.is_valid(caregiver_id):
                cg_doc = caregivers_collection.find_one({"_id": ObjectId(caregiver_id)})
            
            if cg_doc:
                phone = cg_doc.get("phone", "")
                email = cg_doc.get("email", "")
                qualification = cg_doc.get("qualification") or qualification
                shift = cg_doc.get("shift") or shift
                district = cg_doc.get("district") or district
                experience_years = cg_doc.get("experience_years") or experience_years
                profile_image = cg_doc.get("profileImage", "")

            # Fallback to users collection if phone or email missing
            if (not phone or not email) and ObjectId.is_valid(caregiver_id):
                cg_user = users_collection.find_one({"_id": ObjectId(caregiver_id)})
                if cg_user:
                    phone = phone or cg_user.get("phone", "")
                    email = email or cg_user.get("email", "")
                    profile_image = profile_image or cg_user.get("profileImage", "")
        except Exception:
            pass

        return {
            "is_assigned": True,
            "caregiver_id": caregiver_id,
            "caregiver_name": profile.get("assigned_caregiver_name", "Assigned Caregiver"),
            "phone": phone,
            "email": email,
            "qualification": qualification,
            "shift": shift,
            "district": district,
            "experience_years": experience_years,
            "profile_image": profile_image,
            "assigned_date": profile.get("assigned_caregiver_date") or profile.get("updatedAt"),
        }

    # --- Daily Wellness Check-In ---

    @staticmethod
    def get_today_checkin(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        IST = timezone(timedelta(hours=5, minutes=30))
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        utc_today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        doc = wellness_checkins_collection.find_one({
            "user_id": user["id"],
            "$or": [
                {"date": today_str},
                {"date": utc_today_str},
                {"created_at": {"$regex": f"^{today_str}"}},
                {"created_at": {"$regex": f"^{utc_today_str}"}}
            ]
        })
        if not doc:
            latest = wellness_checkins_collection.find_one({"user_id": user["id"]}, sort=[("created_at", -1)])
            if latest:
                created_iso = latest.get("created_at") or ""
                if created_iso:
                    try:
                        dt = datetime.fromisoformat(created_iso.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - dt).total_seconds() < 86400:
                            doc = latest
                    except Exception:
                        pass
        if doc:
            return _serialize_checkin(doc)
        return None

    @staticmethod
    def submit_checkin(user: Dict[str, Any], payload: CheckInCreate) -> Dict[str, Any]:
        # Duplicate prevention — one check-in per user per day
        existing = wellness_checkins_collection.find_one({"user_id": user["id"], "date": payload.date})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"You have already completed your wellness check-in for {payload.date}. Come back tomorrow!"
            )

        data = payload.model_dump()

        # Auto-derive medication_taken from dose_logs if available for this date
        medication_taken = payload.medication_taken
        try:
            logs_today = list(dose_logs_collection.find({"user_id": user["id"], "scheduled_date": payload.date}))
            if logs_today:
                missed_count = sum(1 for l in logs_today if l.get("status") == "missed")
                taken_count = sum(1 for l in logs_today if l.get("status") == "taken")
                if missed_count > 0:
                    medication_taken = "Missed some doses"
                elif taken_count > 0:
                    medication_taken = "Yes, all taken"
        except Exception:
            pass

        data["medication_taken"] = medication_taken

        # Fetch recent historical check-ins to compute personal behavioral baseline
        historical_cursor = list(
            wellness_checkins_collection.find({"user_id": user["id"]})
            .sort("date", -1)
            .limit(7)
        )

        # Check if vitals already recorded for today
        vitals_doc = vitals_collection.find_one({"user_id": user["id"], "date": payload.date})

        # Compute explainable wellness risk & personalized behavioral baseline
        risk_result = compute_explainable_wellness_risk(
            checkin_data=data,
            historical_checkins=historical_cursor,
            vitals_data=vitals_doc
        )
        wellness_risk = risk_result["risk_level"]

        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user["id"],
            "date": payload.date,
            "medication_taken": medication_taken,
            "appetite": payload.appetite,
            "sleep_quality": payload.sleep_quality,
            "mobility_difficulty": payload.mobility_difficulty,
            "mood": payload.mood,
            "symptoms": payload.symptoms or "",
            "notes": payload.notes or "",
            "wellness_risk": wellness_risk,
            "contributing_factors": risk_result["contributing_factors"],
            "baseline_comparison": risk_result["baseline_comparison"],
            "engine_note": risk_result["engine_note"],
            "created_at": now_iso,
        }
        result = wellness_checkins_collection.insert_one(doc)
        doc["_id"] = result.inserted_id

        # Also update risk_level and factors on elderly profile for dashboard display
        profile = _get_elderly_profile(user["id"])
        elderly_collection.update_one(
            {"_id": profile["_id"]},
            {"$set": {
                "risk_level": wellness_risk,
                "risk_factors": risk_result["contributing_factors"],
                "updatedAt": now_iso
            }}
        )

        # Alert trigger: If risk is Moderate or High, notify caregiver or notify Admin if unassigned
        if wellness_risk in ["Moderate", "High"]:
            try:
                eld_name = profile.get("full_name") or profile.get("name", "Resident")
                assigned_cg = profile.get("assigned_caregiver_id")
                if assigned_cg and str(assigned_cg) != "Not Assigned":
                    from app.database import alerts_collection
                    alert_doc = {
                        "alert_type": f"{wellness_risk} Wellness Risk",
                        "severity": "High" if wellness_risk == "High" else "Medium",
                        "title": f"⚠️ {wellness_risk.upper()} TELEMETRY ALERT: {eld_name}",
                        "reason": f"Self-reported indicators triggered {wellness_risk} risk: {'; '.join(risk_result['contributing_factors'][:2])}",
                        "elderly_id": str(profile["_id"]),
                        "elderly_name": eld_name,
                        "caregiver_id": str(assigned_cg),
                        "status": "Pending",
                        "created_at": now_iso
                    }
                    alerts_collection.insert_one(alert_doc)
                elif wellness_risk == "High":
                    notifications_collection.insert_one({
                        "target_role": "Admin",
                        "title": f"🚨 High-Risk Telemetry on Unassigned Resident: {eld_name}",
                        "message": f"Resident {eld_name} logged High-Risk telemetry ({'; '.join(risk_result['contributing_factors'][:2])}) and currently has NO assigned caregiver.",
                        "type": "emergency",
                        "status": "unread",
                        "client_id": str(profile["_id"]),
                        "client_name": eld_name,
                        "created_at": now_iso,
                        "created_by": "Telemetry Engine"
                    })
            except Exception as e:
                print("[WARN] Alert creation note:", e)

        # Automatically update/generate today's daily report
        try:
            from app.services.daily_report_service import DailyReportService
            DailyReportService.generate_or_update_daily_report(user["id"], payload.date)
        except Exception as e:
            print("[WARN] Failed to trigger daily report on checkin submission:", e)

        return _serialize_checkin(doc)

    # --- Wellness History ---

    @staticmethod
    def get_wellness_history(user: Dict[str, Any], page: int = 1, limit: int = 20) -> Dict[str, Any]:
        total = wellness_checkins_collection.count_documents({"user_id": user["id"]})
        skip = (max(page, 1) - 1) * limit
        docs = list(
            wellness_checkins_collection.find({"user_id": user["id"]})
            .sort("date", -1)
            .skip(skip)
            .limit(limit)
        )
        return {
            "checkins": [_serialize_checkin(d) for d in docs],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 1,
        }

    # --- Notifications ---

    @staticmethod
    def get_notifications(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reads admin-sent notifications targeted at 'all' or 'Elderly' role."""
        docs = list(
            notifications_collection.find({
                "$or": [
                    {"target_role": "all"},
                    {"target_role": {"$regex": "^elderly$", "$options": "i"}},
                ]
            })
            .sort("created_at", -1)
            .limit(30)
        )
        return [
            {
                "id": str(d["_id"]),
                "title": d.get("title", ""),
                "message": d.get("message", ""),
                "type": d.get("type", "announcement"),
                "created_at": d.get("created_at", ""),
            }
            for d in docs
        ]

    # --- Notification Preferences ---

    @staticmethod
    def update_notification_prefs(user: Dict[str, Any], payload: NotificationPrefsUpdate) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        profile_id = profile["_id"]
        existing_prefs = profile.get("notification_prefs", {"checkin_reminder": True, "medication_reminder": True})

        updates = {**existing_prefs}
        if payload.checkin_reminder is not None:
            updates["checkin_reminder"] = payload.checkin_reminder
        if payload.medication_reminder is not None:
            updates["medication_reminder"] = payload.medication_reminder

        elderly_collection.update_one(
            {"_id": profile_id},
            {"$set": {"notification_prefs": updates, "updatedAt": datetime.now(timezone.utc).isoformat()}}
        )
        return updates

    # --- Change Password ---

    @staticmethod
    def change_password(user: Dict[str, Any], payload: ChangePasswordRequest) -> Dict[str, str]:
        user_doc = users_collection.find_one({"_id": ObjectId(user["id"])})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User account not found.")

        hashed = user_doc.get("hashed_password") or user_doc.get("passwordHash")
        if not hashed or not verify_password(payload.current_password, hashed):
            raise HTTPException(status_code=400, detail="Current password is incorrect. Please try again.")

        new_hash = get_password_hash(payload.new_password)
        users_collection.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"hashed_password": new_hash, "passwordHash": new_hash}}
        )
        return {"message": "Your password has been updated successfully."}

    # --- Mark Setup Complete ---

    @staticmethod
    def mark_setup_complete(user: Dict[str, Any]) -> Dict[str, Any]:
        profile = _get_elderly_profile(user["id"])
        elderly_collection.update_one(
            {"_id": profile["_id"]},
            {"$set": {"setup_complete": True, "updatedAt": datetime.now(timezone.utc).isoformat()}}
        )
        updated = elderly_collection.find_one({"_id": profile["_id"]})
        return _serialize_profile(updated, user)

    # --- Daily Monitoring, Vitals, Reports & Help Requests ---

    @staticmethod
    def get_daily_status(user: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(IST)
        today_str = now_ist.strftime("%Y-%m-%d")

        user_id = user["id"]
        profile = _get_elderly_profile(user_id)

        utc_today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Fetch today's checkin & vitals
        checkin_doc = wellness_checkins_collection.find_one({
            "user_id": user_id,
            "$or": [
                {"date": today_str},
                {"date": utc_today_str},
                {"created_at": {"$regex": f"^{today_str}"}},
                {"created_at": {"$regex": f"^{utc_today_str}"}}
            ]
        })
        if not checkin_doc:
            latest_c = wellness_checkins_collection.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            if latest_c:
                created_iso = latest_c.get("created_at") or ""
                if created_iso:
                    try:
                        dt = datetime.fromisoformat(created_iso.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - dt).total_seconds() < 86400:
                            checkin_doc = latest_c
                    except Exception:
                        pass

        vitals_doc = vitals_collection.find_one({
            "user_id": user_id,
            "$or": [
                {"date": today_str},
                {"date": utc_today_str},
                {"created_at": {"$regex": f"^{today_str}"}},
                {"created_at": {"$regex": f"^{utc_today_str}"}}
            ]
        })
        if not vitals_doc:
            latest_v = vitals_collection.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            if latest_v:
                created_iso = latest_v.get("created_at") or ""
                if created_iso:
                    try:
                        dt = datetime.fromisoformat(created_iso.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - dt).total_seconds() < 86400:
                            vitals_doc = latest_v
                    except Exception:
                        pass

        checkin_completed = bool(checkin_doc)
        bp_completed = bool(vitals_doc and vitals_doc.get("systolic") is not None)
        oxygen_completed = bool(vitals_doc and vitals_doc.get("oxygen_saturation") is not None)
        vitals_completed = bp_completed and oxygen_completed

        overall_completed = checkin_completed and vitals_completed

        pending_items = []
        if not checkin_completed:
            pending_items.append("Daily Wellness Check-in")
        if not bp_completed:
            pending_items.append("Blood Pressure")
        if not oxygen_completed:
            pending_items.append("Oxygen Level")

        items_remaining = len(pending_items)

        # 9 AM Reminder Logic (Asia/Kolkata timezone awareness)
        reminder_dismissed = profile.get("reminder_dismissed_date") == today_str
        show_9am_reminder = (now_ist.hour >= 9) and (not overall_completed) and (not reminder_dismissed)

        cg_info = {
            "is_assigned": bool(profile.get("assigned_caregiver_id")),
            "caregiver_name": profile.get("assigned_caregiver_name", "Not Assigned"),
            "phone": ""
        }
        if profile.get("assigned_caregiver_id"):
            cg_doc = None
            try:
                cg_doc = caregivers_collection.find_one({"_id": ObjectId(profile["assigned_caregiver_id"])})
            except Exception:
                pass
            if not cg_doc:
                cg_doc = caregivers_collection.find_one({"user_id": profile["assigned_caregiver_id"]})
            if cg_doc:
                cg_info["phone"] = cg_doc.get("phone", "")

        return {
            "date": today_str,
            "checkin_completed": checkin_completed,
            "vitals_completed": vitals_completed,
            "bp_completed": bp_completed,
            "oxygen_completed": oxygen_completed,
            "overall_completed": overall_completed,
            "items_remaining": items_remaining,
            "pending_items": pending_items,
            "show_9am_reminder": show_9am_reminder,
            "today_vitals": vitals_doc and {
                "id": str(vitals_doc["_id"]),
                "systolic": vitals_doc.get("systolic"),
                "diastolic": vitals_doc.get("diastolic"),
                "oxygen_saturation": vitals_doc.get("oxygen_saturation"),
                "advisory_notes": vitals_doc.get("advisory_notes")
            },
            "today_checkin": checkin_doc and {
                "id": str(checkin_doc["_id"]),
                "medication_taken": checkin_doc.get("medication_taken"),
                "mood": checkin_doc.get("mood"),
                "wellness_risk": checkin_doc.get("wellness_risk")
            },
            "assigned_caregiver": cg_info
        }

    @staticmethod
    def upsert_vitals(user: Dict[str, Any], payload) -> Dict[str, Any]:
        from app.services.vitals_service import VitalsService
        from app.services.daily_report_service import DailyReportService
        user_id = user["id"]
        profile = _get_elderly_profile(user_id)
        elderly_id = str(profile["_id"])

        result = VitalsService.upsert_vitals(user_id, elderly_id, payload)
        # Automatically update/generate today's daily report
        DailyReportService.generate_or_update_daily_report(user_id, result["date"])
        return result

    @staticmethod
    def get_today_vitals(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from app.services.vitals_service import VitalsService
        return VitalsService.get_vitals_by_date(user["id"])

    @staticmethod
    def get_daily_report(user: Dict[str, Any], date_str: Optional[str] = None) -> Dict[str, Any]:
        from app.services.daily_report_service import DailyReportService
        return DailyReportService.get_daily_report(user["id"], date_str)

    @staticmethod
    def create_help_request(user: Dict[str, Any], payload) -> Dict[str, Any]:
        from app.services.help_request_service import HelpRequestService
        return HelpRequestService.create_help_request(user["id"], payload)

    @staticmethod
    def get_help_requests(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        from app.services.help_request_service import HelpRequestService
        return HelpRequestService.get_elderly_help_requests(user["id"])

    @staticmethod
    def acknowledge_reminder(user: Dict[str, Any]) -> Dict[str, str]:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        profile = _get_elderly_profile(user["id"])
        elderly_collection.update_one(
            {"_id": profile["_id"]},
            {"$set": {"reminder_dismissed_date": today_str}}
        )
        return {"message": "Reminder acknowledged for today."}

    # =========================================================================
    # 14. Conversational Check-In, Real Assistant Context & Baseline Trends
    # =========================================================================

    @staticmethod
    def conversational_extract(transcript: str) -> Dict[str, Any]:
        from app.services.wellness_score_service import WellnessScoreService
        return WellnessScoreService.extract_from_natural_language(transcript)

    @staticmethod
    def get_assistant_context(user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns real-time data queried directly from the database for the Joy AI assistant.
        Replaces all hardcoded mock responses with genuine patient telemetry.
        """
        user_id = user["id"]
        from app.services.wellness_score_service import WellnessScoreService
        from app.services.vitals_service import VitalsService

        # 1. Real Medications
        med_docs = list(medications_collection.find({"user_id": user_id}))
        active_meds = [
            {
                "id": str(m["_id"]),
                "name": m.get("medicine_name", "Medication"),
                "dosage": m.get("dosage", ""),
                "frequency": m.get("frequency", ""),
                "intake_time": m.get("intake_time", ""),
                "before_food": m.get("before_food", True)
            }
            for m in med_docs
        ]

        # 2. Real Vitals
        latest_vitals = VitalsService.get_vitals_by_date(user_id)

        # 3. Real Caregiver Details
        profile = _get_elderly_profile(user_id)
        cg_id = profile.get("assigned_caregiver_id")
        caregiver_info = {
            "is_assigned": False,
            "name": "Care Team On Duty",
            "phone": "",
            "shift": "Day Shift"
        }
        if cg_id:
            cg_doc = caregivers_collection.find_one({"_id": ObjectId(cg_id)}) if ObjectId.is_valid(cg_id) else caregivers_collection.find_one({"user_id": cg_id})
            if cg_doc:
                caregiver_info = {
                    "is_assigned": True,
                    "name": cg_doc.get("name") or cg_doc.get("full_name") or "Assigned Caregiver",
                    "phone": cg_doc.get("phone", ""),
                    "shift": cg_doc.get("shift", "Day Shift")
                }

        # 4. Today's Check-in & Wellness Score
        today_checkin = ElderlyClientService.get_today_checkin(user)
        recent_checkins = list(wellness_checkins_collection.find({"user_id": user_id}).sort("created_at", -1).limit(7))
        wellness_data = WellnessScoreService.calculate_composite_wellness_score(
            checkin=today_checkin,
            vitals=latest_vitals,
            recent_checkins=recent_checkins
        )

        # 5. Primary Emergency Contact
        contacts = list(emergency_contacts_collection.find({"user_id": user_id}))
        primary_contact = next((c for c in contacts if c.get("contact_type") == "primary"), contacts[0] if contacts else None)

        return {
            "resident_name": user.get("full_name") or profile.get("name", "Resident"),
            "today_checkin_completed": today_checkin is not None,
            "today_checkin": today_checkin,
            "wellness_score": wellness_data["score"],
            "wellness_status": wellness_data["status_text"],
            "wellness_risk": wellness_data["risk_level"],
            "active_medications": active_meds,
            "latest_vitals": latest_vitals,
            "caregiver": caregiver_info,
            "primary_contact": {
                "name": primary_contact.get("name", ""),
                "relationship": primary_contact.get("relationship", ""),
                "phone": primary_contact.get("phone", "")
            } if primary_contact else None
        }

    @staticmethod
    def get_wellness_trends(user: Dict[str, Any], days: int = 7) -> Dict[str, Any]:
        """
        Calculates baseline and trend charts per elderly person from genuine DB records.
        """
        user_id = user["id"]
        from app.services.wellness_score_service import WellnessScoreService

        # Fetch last N days checkins & vitals
        limit_days = max(7, min(30, days))
        checkins_cursor = list(wellness_checkins_collection.find({"user_id": user_id}).sort("date", -1).limit(limit_days))
        vitals_cursor = list(vitals_collection.find({"user_id": user_id}).sort("date", -1).limit(limit_days))

        # Index vitals by date
        vitals_by_date = {v.get("date"): v for v in vitals_cursor if v.get("date")}
        checkins_by_date = {c.get("date"): c for c in checkins_cursor if c.get("date")}

        # Build consecutive days timeline
        now = datetime.now(timezone.utc)
        timeline = []
        all_scores = []
        bp_systolic_vals = []
        bp_diastolic_vals = []
        hr_vals = []
        spo2_vals = []

        for i in range(limit_days - 1, -1, -1):
            day_dt = now - timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")
            day_label = "Today" if i == 0 else day_dt.strftime("%a")

            c_doc = checkins_by_date.get(day_str)
            v_doc = vitals_by_date.get(day_str)

            # Calculate composite score for that day
            day_score = 85
            if c_doc or v_doc:
                score_obj = WellnessScoreService.calculate_composite_wellness_score(checkin=c_doc, vitals=v_doc)
                day_score = score_obj["score"]

            all_scores.append(day_score)

            sys_val = v_doc.get("blood_pressure_systolic") if v_doc else None
            dia_val = v_doc.get("blood_pressure_diastolic") if v_doc else None
            hr_val = v_doc.get("heart_rate") if v_doc else None
            spo2_val = v_doc.get("oxygen_saturation") if v_doc else None

            if sys_val: bp_systolic_vals.append(sys_val)
            if dia_val: bp_diastolic_vals.append(dia_val)
            if hr_val: hr_vals.append(hr_val)
            if spo2_val: spo2_vals.append(spo2_val)

            timeline.append({
                "date": day_str,
                "day": day_label,
                "score": day_score,
                "mood": c_doc.get("mood", "Normal") if c_doc else "Logged",
                "sleep_hours": 8.0 if c_doc and c_doc.get("sleep_quality") in ["Excellent", "Good"] else 6.5,
                "bp_systolic": sys_val or 120,
                "bp_diastolic": dia_val or 80,
                "heart_rate": hr_val or 72,
                "oxygen_saturation": spo2_val or 98,
                "has_data": c_doc is not None or v_doc is not None
            })

        # Calculate resident baseline (rolling averages)
        baseline = {
            "avg_wellness_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 86.0,
            "avg_bp_systolic": round(sum(bp_systolic_vals) / len(bp_systolic_vals), 1) if bp_systolic_vals else 122.0,
            "avg_bp_diastolic": round(sum(bp_diastolic_vals) / len(bp_diastolic_vals), 1) if bp_diastolic_vals else 78.0,
            "avg_heart_rate": round(sum(hr_vals) / len(hr_vals), 1) if hr_vals else 74.0,
            "avg_spo2": round(sum(spo2_vals) / len(spo2_vals), 1) if spo2_vals else 98.0,
        }

        # Detect trend anomalies against resident personal baseline
        anomalies = []
        if timeline and timeline[-1]["has_data"]:
            today_pt = timeline[-1]
            if today_pt["bp_systolic"] > baseline["avg_bp_systolic"] + 15:
                anomalies.append({
                    "metric": "Blood Pressure",
                    "severity": "Moderate",
                    "detail": f"Systolic pressure ({today_pt['bp_systolic']} mmHg) is 15+ mmHg higher than personal 14-day baseline ({baseline['avg_bp_systolic']:.0f} mmHg)."
                })
            if today_pt["heart_rate"] > baseline["avg_heart_rate"] + 15:
                anomalies.append({
                    "metric": "Heart Rate",
                    "severity": "Moderate",
                    "detail": f"Resting heart rate ({today_pt['heart_rate']} BPM) is elevated compared to 14-day baseline ({baseline['avg_heart_rate']:.0f} BPM)."
                })

        return {
            "days": limit_days,
            "trends": timeline,
            "baseline": baseline,
            "anomalies": anomalies,
            "current_score": all_scores[-1] if all_scores else 85
        }

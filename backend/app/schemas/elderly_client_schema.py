"""
Pydantic schemas for the Elderly Client Module.
All schemas here are used exclusively by elderly-user-facing endpoints
(/api/elderly/me/...). They are separate from the admin-facing schemas
in elderly_schema.py which are used by admin-only routes.
"""
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
from typing import Optional, List, Dict, Any
import re
from datetime import date, datetime
from app.constants import validate_district


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_CONDITIONS = [
    "Diabetes", "Blood Pressure", "Heart Problem", "Arthritis",
    "Asthma", "Thyroid", "Kidney Problem", "Cholesterol", "Other", "None",
    "Hypertension (High BP)", "Diabetes (Type 2)", "Heart Condition",
    "Arthritis / Joint Pain", "Asthma / Breathing", "None / Good Health"
]

ALLOWED_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]


# ---------------------------------------------------------------------------
# Profile Schemas
# ---------------------------------------------------------------------------

class ElderlyProfileSelfUpdate(BaseModel):
    """Fields an elderly user can update about their own profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None  # ISO date string YYYY-MM-DD
    gender: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relationship: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[EmailStr] = None
    guardian_report_consent: Optional[bool] = None
    guardian_report_enabled: Optional[bool] = None

    @field_validator("district")
    @classmethod
    def check_self_district(cls, v):
        if v is not None:
            return validate_district(v, required=False)
        return v

    @field_validator("blood_group")
    @classmethod
    def check_blood_group(cls, v):
        if v is not None and v != "":
            if v not in ALLOWED_BLOOD_GROUPS:
                raise ValueError(f"Blood group must be one of: {', '.join(ALLOWED_BLOOD_GROUPS)}")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_be_past(cls, v):
        if v is None:
            return v
        try:
            dob = date.fromisoformat(v)
        except ValueError:
            raise ValueError("Date of birth must be a valid date in YYYY-MM-DD format.")
        if dob >= date.today():
            raise ValueError("Date of birth must be in the past.")
        return v

    @field_validator("gender")
    @classmethod
    def gender_must_be_valid(cls, v):
        if v is None:
            return v
        allowed = {"Male", "Female", "Other", "Prefer not to say"}
        if v not in allowed:
            raise ValueError(f"Gender must be one of: {', '.join(allowed)}")
        return v


class ElderlyProfileResponse(BaseModel):
    """Response shape for the elderly user's own profile."""
    id: str
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = ""
    date_of_birth: Optional[str] = None
    age: Optional[int] = None   # computed server-side from DOB — never user-entered
    gender: Optional[str] = ""
    district: Optional[str] = ""
    address: Optional[str] = ""
    blood_group: Optional[str] = ""
    guardian_name: Optional[str] = ""
    guardian_relationship: Optional[str] = ""
    guardian_phone: Optional[str] = ""
    guardian_email: Optional[str] = ""
    guardian_report_consent: Optional[bool] = False
    guardian_report_enabled: Optional[bool] = True
    profileImage: Optional[str] = ""
    setup_complete: bool = False
    notification_prefs: Optional[Dict[str, Any]] = None
    assigned_caregiver_id: Optional[str] = None
    assigned_caregiver_name: Optional[str] = "Not Assigned"
    assigned_doctor_id: Optional[str] = None
    assigned_doctor_name: Optional[str] = "Not Assigned"
    risk_level: Optional[str] = "Low"
    createdAt: Optional[str] = None


# ---------------------------------------------------------------------------
# Health Information Schemas
# ---------------------------------------------------------------------------



class HealthInfoUpdate(BaseModel):
    """User-provided health information — never AI-generated or diagnostic."""
    conditions: Optional[List[str]] = None
    other_condition: Optional[str] = Field(None, max_length=200)
    blood_group: Optional[str] = None
    allergies: Optional[List[str]] = None
    previous_conditions: Optional[str] = Field(None, max_length=500)
    medical_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v):
        if v is None:
            return v
        for c in v:
            if c not in ALLOWED_CONDITIONS:
                raise ValueError(f"'{c}' is not a valid condition. Choose from: {', '.join(ALLOWED_CONDITIONS)}")
        # "None" is mutually exclusive with all others
        if "None" in v and len(v) > 1:
            raise ValueError('"None" cannot be selected together with other conditions.')
        return v

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_BLOOD_GROUPS:
            raise ValueError(f"Blood group must be one of: {', '.join(ALLOWED_BLOOD_GROUPS)}")
        return v


class HealthInfoResponse(BaseModel):
    conditions: List[str] = []
    other_condition: Optional[str] = ""
    blood_group: Optional[str] = ""
    allergies: List[str] = []
    previous_conditions: Optional[str] = ""
    medical_notes: Optional[str] = ""


# ---------------------------------------------------------------------------
# Hospital Information Schemas
# ---------------------------------------------------------------------------

class HospitalInfoUpdate(BaseModel):
    hospital_name: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=300)
    department: Optional[str] = Field(None, max_length=200)
    contact_number: Optional[str] = None


class HospitalInfoResponse(BaseModel):
    hospital_name: Optional[str] = ""
    location: Optional[str] = ""
    department: Optional[str] = ""
    contact_number: Optional[str] = ""


# ---------------------------------------------------------------------------
# Doctor Information Schemas (view only for assigned doctor)
# ---------------------------------------------------------------------------

class DoctorInfoResponse(BaseModel):
    assigned_doctor_id: Optional[str] = None
    doctor_name: Optional[str] = "Not Assigned"
    specialization: Optional[str] = ""
    hospital: Optional[str] = ""
    contact_number: Optional[str] = ""
    is_assigned: bool = False


# ---------------------------------------------------------------------------
# Medication Schemas
# ---------------------------------------------------------------------------

ALLOWED_FREQUENCIES = [
    "Once daily", "Twice daily", "Three times daily", "Four times daily",
    "Every 8 hours", "Every 12 hours", "Weekly", "As needed"
]


def _validate_phone(v: Optional[str]) -> Optional[str]:
    if not v:
        return v
    cleaned = re.sub(r"[\s\-\(\)\+]", "", v)
    if not cleaned.isdigit() or len(cleaned) < 7:
        raise ValueError("Please enter a valid phone number (at least 7 digits).")
    return v


def parse_legacy_intake_time(intake_time: Optional[str]) -> List[str]:
    """
    Parses legacy intake_time strings into sorted 24h 'HH:MM' strings.
    Supports formats like '8:00 AM', '1:00 PM', '8:00 AM, 8:00 PM', '08:00',
    'Morning', 'Afternoon', 'Evening', 'Night', etc.
    """
    if not intake_time or not str(intake_time).strip():
        return []

    text = str(intake_time).strip()
    named_slots = {
        "morning": "08:00",
        "breakfast": "08:00",
        "afternoon": "13:00",
        "lunch": "13:00",
        "evening": "18:30",
        "dinner": "19:30",
        "night": "21:30",
        "bedtime": "21:30"
    }

    parts = re.split(r"[,;]|\band\b", text, flags=re.IGNORECASE)
    results = set()

    for part in parts:
        p = part.strip()
        if not p:
            continue
        p_lower = p.lower()
        if p_lower in named_slots:
            results.add(named_slots[p_lower])
            continue

        p_norm = re.sub(r"\s+", " ", p)
        for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M", "%H"):
            try:
                t = datetime.strptime(p_norm.upper(), fmt).time()
                results.add(f"{t.hour:02d}:{t.minute:02d}")
                break
            except ValueError:
                pass

    return sorted(list(results))


class MedicationCreate(BaseModel):
    medicine_name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100, json_schema_extra={"example": "10mg"})
    frequency: str = Field(..., json_schema_extra={"example": "Once daily"})
    intake_time: Optional[str] = Field(None, max_length=100, json_schema_extra={"example": "8:00 AM"})
    times: List[str] = Field(default_factory=list, description="Scheduled times in 24h HH:MM format (max 6)")
    days_of_week: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], description="Days of week: 0=Mon, 6=Sun")
    before_food: bool = Field(default=True)   # True = Before food, False = After food
    prescribed_by: Optional[str] = Field(None, max_length=200)
    start_date: str = Field(..., json_schema_extra={"example": "2026-01-01"})
    end_date: Optional[str] = Field(None, json_schema_extra={"example": "2026-12-31"})

    @field_validator("times", mode="before")
    @classmethod
    def validate_times(cls, v, info):
        if v is None or (isinstance(v, list) and len(v) == 0):
            # Check if legacy intake_time is present
            intake = info.data.get("intake_time") if hasattr(info, "data") else None
            v = parse_legacy_intake_time(intake) if intake else []
        elif isinstance(v, str):
            v = [v]

        if not isinstance(v, list):
            raise ValueError("times must be a list of 24-hour 'HH:MM' strings.")
        if len(v) > 6:
            raise ValueError("At most 6 scheduled times per day are allowed.")

        time_regex = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")
        clean_times = set()
        for t in v:
            if not isinstance(t, str) or not time_regex.match(t.strip()):
                raise ValueError(f"Invalid time format '{t}'. Must be 24-hour 'HH:MM' format.")
            clean_times.add(t.strip())
        return sorted(list(clean_times))

    @field_validator("days_of_week", mode="before")
    @classmethod
    def validate_days_of_week(cls, v):
        if v is None or (isinstance(v, list) and len(v) == 0):
            return [0, 1, 2, 3, 4, 5, 6]
        if not isinstance(v, list):
            raise ValueError("days_of_week must be a list of integers from 0 to 6.")
        clean_days = set()
        for d in v:
            if not isinstance(d, int) or d < 0 or d > 6:
                raise ValueError("days_of_week elements must be integers from 0 (Monday) to 6 (Sunday).")
            clean_days.add(d)
        return sorted(list(clean_days))

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Please enter a valid date in YYYY-MM-DD format.")
        return v

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if v is None:
            return v
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("End date must be on or after start date.")
        return v

    @model_validator(mode="after")
    def populate_times_from_intake(self):
        if not self.times and self.intake_time:
            self.times = parse_legacy_intake_time(self.intake_time)
        return self


class MedicationUpdate(BaseModel):
    medicine_name: Optional[str] = Field(None, max_length=200)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = None
    intake_time: Optional[str] = Field(None, max_length=100)
    times: Optional[List[str]] = None
    days_of_week: Optional[List[int]] = None
    before_food: Optional[bool] = None
    prescribed_by: Optional[str] = Field(None, max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @field_validator("times", mode="before")
    @classmethod
    def validate_times(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            raise ValueError("times must be a list of 24-hour 'HH:MM' strings.")
        if len(v) > 6:
            raise ValueError("At most 6 scheduled times per day are allowed.")
        time_regex = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")
        clean_times = set()
        for t in v:
            if not isinstance(t, str) or not time_regex.match(t.strip()):
                raise ValueError(f"Invalid time format '{t}'. Must be 24-hour 'HH:MM' format.")
            clean_times.add(t.strip())
        return sorted(list(clean_times))

    @field_validator("days_of_week", mode="before")
    @classmethod
    def validate_days_of_week(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("days_of_week must be a list of integers from 0 to 6.")
        clean_days = set()
        for d in v:
            if not isinstance(d, int) or d < 0 or d > 6:
                raise ValueError("days_of_week elements must be integers from 0 (Monday) to 6 (Sunday).")
            clean_days.add(d)
        return sorted(list(clean_days))


class MedicationResponse(BaseModel):
    id: str
    user_id: str
    medicine_name: str
    dosage: str
    frequency: str
    intake_time: Optional[str] = ""
    times: List[str] = []
    days_of_week: List[int] = [0, 1, 2, 3, 4, 5, 6]
    before_food: bool = True
    prescribed_by: Optional[str] = ""
    start_date: str
    end_date: Optional[str] = None
    created_at: str
    updated_at: str


class TakeDosePayload(BaseModel):
    scheduled_time: str = Field(..., pattern=r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", json_schema_extra={"example": "08:00"})
    med_id: Optional[str] = None


class UndoDosePayload(BaseModel):
    scheduled_time: str = Field(..., pattern=r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", json_schema_extra={"example": "08:00"})


class DoseSlotResponse(BaseModel):
    med_id: str
    name: str
    dosage: str
    scheduled_time: str
    scheduled_time_display: Optional[str] = None
    slot: str  # Morning | Afternoon | Evening | Night
    state: str  # upcoming | due | taken | taken_late | missed | skipped
    opens_at: str
    opens_at_display: Optional[str] = None
    closes_at: str
    closes_at_display: Optional[str] = None
    taken_at: Optional[str] = None
    late_minutes: Optional[int] = 0
    source: Optional[str] = None
    before_food: bool = True
    prescribed_by: Optional[str] = ""


class DoseAdherenceResponse(BaseModel):
    today: Optional[dict] = None
    today_taken: int
    today_total: int
    seven_day_percentage: float
    streak_days: int


class DoseLogRequest(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "taken"})  # "taken" or "missed"
    medicine_name: Optional[str] = "Medication"
    dosage: Optional[str] = ""
    intake_time: Optional[str] = ""



# ---------------------------------------------------------------------------
# Emergency Contact Schemas
# ---------------------------------------------------------------------------

CONTACT_TYPES = ["primary", "secondary"]


class EmergencyContactCreate(BaseModel):
    contact_type: str = Field(..., example="primary")   # primary or secondary
    name: str = Field(..., min_length=2, max_length=100)
    relationship: str = Field(..., min_length=1, max_length=100, example="Son")
    phone: str = Field(..., example="+601234567890")
    alt_phone: Optional[str] = None

    @field_validator("contact_type")
    @classmethod
    def validate_type(cls, v):
        if v not in CONTACT_TYPES:
            raise ValueError("Contact type must be 'primary' or 'secondary'.")
        return v

    @field_validator("phone", "alt_phone")
    @classmethod
    def validate_phones(cls, v):
        return _validate_phone(v)


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    relationship: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = None
    alt_phone: Optional[str] = None

    @field_validator("phone", "alt_phone")
    @classmethod
    def validate_phones(cls, v):
        return _validate_phone(v)


class EmergencyContactResponse(BaseModel):
    id: str
    user_id: str
    contact_type: str
    name: str
    relationship: str
    phone: str
    alt_phone: Optional[str] = ""
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Assigned Caregiver View Schemas
# ---------------------------------------------------------------------------

class CaregiverViewResponse(BaseModel):
    is_assigned: bool
    caregiver_id: Optional[str] = None
    caregiver_name: Optional[str] = "Not Assigned"
    phone: Optional[str] = ""
    assigned_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Daily Wellness Check-In Schemas
# ---------------------------------------------------------------------------

MOOD_OPTIONS = ["Great", "Good", "Okay", "Not Great", "Poor"]
APPETITE_OPTIONS = ["Excellent", "Good", "Fair", "Poor", "No Appetite"]
SLEEP_OPTIONS = ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
MOBILITY_OPTIONS = ["No difficulty", "Slight difficulty", "Moderate difficulty", "Significant difficulty"]
MEDICATION_OPTIONS = ["Yes, all taken", "Yes, partially taken", "No, not taken", "No medication today"]


class CheckInCreate(BaseModel):
    """One daily wellness check-in covering 6 wellness dimensions."""
    date: str = Field(..., example="2026-08-10")
    medication_taken: str = Field(..., example="Yes, all taken")
    appetite: str = Field(..., example="Good")
    sleep_quality: str = Field(..., example="Good")
    mobility_difficulty: str = Field(..., example="No difficulty")
    mood: str = Field(..., example="Good")
    symptoms: Optional[str] = Field(default="", max_length=500, example="Mild headache")
    notes: Optional[str] = Field(default="", max_length=1000)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Please provide a valid date in YYYY-MM-DD format.")
        return v

    @field_validator("medication_taken")
    @classmethod
    def validate_medication(cls, v):
        if v not in MEDICATION_OPTIONS:
            raise ValueError(f"Invalid medication response. Choose from: {', '.join(MEDICATION_OPTIONS)}")
        return v

    @field_validator("mood")
    @classmethod
    def validate_mood(cls, v):
        if v not in MOOD_OPTIONS:
            raise ValueError(f"Invalid mood. Choose from: {', '.join(MOOD_OPTIONS)}")
        return v

    @field_validator("appetite")
    @classmethod
    def validate_appetite(cls, v):
        if v not in APPETITE_OPTIONS:
            raise ValueError(f"Invalid appetite. Choose from: {', '.join(APPETITE_OPTIONS)}")
        return v

    @field_validator("sleep_quality")
    @classmethod
    def validate_sleep(cls, v):
        if v not in SLEEP_OPTIONS:
            raise ValueError(f"Invalid sleep quality. Choose from: {', '.join(SLEEP_OPTIONS)}")
        return v

    @field_validator("mobility_difficulty")
    @classmethod
    def validate_mobility(cls, v):
        if v not in MOBILITY_OPTIONS:
            raise ValueError(f"Invalid mobility option. Choose from: {', '.join(MOBILITY_OPTIONS)}")
        return v


class CheckInResponse(BaseModel):
    id: str
    user_id: str
    date: str
    medication_taken: str
    appetite: str
    sleep_quality: str
    mobility_difficulty: str
    mood: str
    symptoms: Optional[str] = ""
    notes: Optional[str] = ""
    wellness_risk: str   # Low / Moderate / High — never phrased as a diagnosis
    created_at: str
    contributing_factors: Optional[List[str]] = Field(default_factory=list)
    baseline_comparison: Optional[str] = ""
    engine_note: Optional[str] = ""


# ---------------------------------------------------------------------------
# Notification Schemas (in-app, read-only for elderly users)
# ---------------------------------------------------------------------------

class NotificationItemResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str            # announcement, system, reminder
    created_at: str


# ---------------------------------------------------------------------------
# Settings Schemas
# ---------------------------------------------------------------------------

class NotificationPrefsUpdate(BaseModel):
    checkin_reminder: Optional[bool] = None
    medication_reminder: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, example="newpassword123")

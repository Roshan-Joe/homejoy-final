import React, { useState } from 'react';
import { 
  Heart, 
  Pill, 
  Calendar, 
  Activity, 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Check, 
  AlertCircle, 
  Clock, 
  Sparkles,
  ArrowRight,
  ArrowLeft
} from 'lucide-react';
import elderlyClientService from '../../services/elderlyClientService';

const CONDITIONS_OPTIONS = [
  { value: 'Blood Pressure', label: 'Blood Pressure / Hypertension' },
  { value: 'Diabetes', label: 'Diabetes' },
  { value: 'Heart Problem', label: 'Heart Condition' },
  { value: 'Arthritis', label: 'Arthritis / Joint Pain' },
  { value: 'Asthma', label: 'Asthma / Respiratory' },
  { value: 'Cholesterol', label: 'Cholesterol' },
  { value: 'Thyroid', label: 'Thyroid' },
  { value: 'None', label: 'None / Good Health' }
];

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];

export const HealthAndMedicationIntakeModal = ({ isOpen, onClose, onComplete, caregiverName }) => {
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Step 1: Personal Health Details
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('Female');
  const [bloodGroup, setBloodGroup] = useState('O+');

  // Step 2: Health Conditions & Allergies
  const [selectedConditions, setSelectedConditions] = useState([]);
  const [otherCondition, setOtherCondition] = useState('');
  const [allergies, setAllergies] = useState('');
  const [medicalNotes, setMedicalNotes] = useState('');

  // Step 3: Daily Medications
  const [hasMedications, setHasMedications] = useState(true);
  const [medications, setMedications] = useState([
    {
      medicine_name: '',
      dosage: '1 tablet',
      morning: true,
      afternoon: false,
      night: true,
      instructions: 'After meal'
    }
  ]);

  if (!isOpen) return null;

  const calculateAge = (dateStr) => {
    if (!dateStr) return '';
    try {
      const birth = new Date(dateStr);
      const today = new Date();
      let age = today.getFullYear() - birth.getFullYear();
      const m = today.getMonth() - birth.getMonth();
      if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
      return age > 0 ? `${age} years old` : '';
    } catch {
      return '';
    }
  };

  const toggleCondition = (val) => {
    if (val === 'None') {
      setSelectedConditions(['None']);
      return;
    }
    setSelectedConditions(prev => {
      const filtered = prev.filter(c => c !== 'None');
      if (filtered.includes(val)) {
        return filtered.filter(c => c !== val);
      } else {
        return [...filtered, val];
      }
    });
  };

  const handleAddMedicationRow = () => {
    setMedications(prev => [
      ...prev,
      {
        medicine_name: '',
        dosage: '1 tablet',
        morning: true,
        afternoon: false,
        night: false,
        instructions: 'After meal'
      }
    ]);
  };

  const handleRemoveMedicationRow = (index) => {
    setMedications(prev => prev.filter((_, i) => i !== index));
  };

  const handleMedChange = (index, field, value) => {
    setMedications(prev => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const handleNext = () => {
    setError('');
    if (step === 1) {
      if (!dob) {
        setError('Please select your Date of Birth so your care team can monitor age-appropriate health indicators.');
        return;
      }
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    }
  };

  const handleBack = () => {
    setError('');
    setStep(prev => Math.max(1, prev - 1));
  };

  const handleSubmit = async () => {
    setError('');
    setSubmitting(true);
    try {
      // 1. Update basic health profile (DOB, Gender, Blood Group)
      await elderlyClientService.updateProfile({
        date_of_birth: dob,
        gender: gender,
        blood_group: bloodGroup
      });

      // 2. Update health conditions & allergies
      let finalConditions = [...selectedConditions];
      if (otherCondition.trim() && !finalConditions.includes('Other')) {
        finalConditions = finalConditions.filter(c => c !== 'None');
        finalConditions.push('Other');
      }
      if (finalConditions.length === 0) {
        finalConditions = ['None'];
      }
      const allergiesList = allergies
        .split(',')
        .map(a => a.trim())
        .filter(Boolean);

      await elderlyClientService.updateHealthInfo({
        conditions: finalConditions,
        other_condition: otherCondition.trim(),
        blood_group: bloodGroup,
        allergies: allergiesList,
        previous_conditions: '',
        medical_notes: medicalNotes.trim()
      });

      // 3. Add medications if client takes any
      if (hasMedications) {
        for (const med of medications) {
          if (med.medicine_name && med.medicine_name.trim()) {
            const times = [];
            if (med.morning) times.push('08:00');
            if (med.afternoon) times.push('13:00');
            if (med.night) times.push('20:00');
            if (times.length === 0) times.push('08:00');

            await elderlyClientService.addMedication({
              medicine_name: med.medicine_name.trim(),
              dosage: med.dosage.trim() || '1 tablet',
              frequency: times.length === 1 ? 'Once daily' : times.length === 2 ? 'Twice daily' : 'Three times daily',
              times: times,
              intake_time: times[0],
              instructions: med.instructions || 'After meal',
              prescribed_by: 'Doctor / Self-reported',
              days_of_week: [0, 1, 2, 3, 4, 5, 6]
            });
          }
        }
      }

      // 4. Mark onboarding intake complete
      await elderlyClientService.markSetupComplete();

      if (onComplete) onComplete();
      if (onClose) onClose();
    } catch (err) {
      console.error('Failed to save health intake details:', err);
      let errorMsg = 'Failed to save health information. Please try again.';
      if (typeof err.response?.data?.detail === 'string') {
        errorMsg = err.response.data.detail;
      } else if (err.response?.data?.message && typeof err.response.data.message === 'string') {
        errorMsg = err.response.data.message;
      } else if (err.message && typeof err.message === 'string') {
        errorMsg = err.message;
      }
      setError(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '16px'
    }}>
      <div 
        className="animate-fade-in"
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '24px',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '24px 28px',
          background: 'linear-gradient(135deg, #0d9488 0%, #0284c7 100%)',
          color: '#ffffff',
          position: 'relative'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{
              background: 'rgba(255, 255, 255, 0.2)',
              padding: '4px 10px',
              borderRadius: '9999px',
              fontSize: '0.78rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Step {step} of 3
            </span>
            <span style={{ fontSize: '0.82rem', opacity: 0.9 }}>
              Personal Health Intake
            </span>
          </div>

          <h2 style={{ fontSize: '1.45rem', fontWeight: 800, margin: 0 }}>
            {step === 1 && 'Welcome! Let’s Add Your Health Basics'}
            {step === 2 && 'Existing Health Conditions'}
            {step === 3 && 'Daily Medicines & Vitamins'}
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.88rem', opacity: 0.9 }}>
            {step === 1 && 'This ensures your assigned caregiver and care team provide age-appropriate safety monitoring.'}
            {step === 2 && 'Select any conditions you manage so your daily check-in can track relevant symptoms.'}
            {step === 3 && 'Add your daily prescription pills or supplements so HomeJoy can chime timely reminders.'}
          </p>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px 28px', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div style={{
              padding: '12px 16px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '12px',
              color: '#b91c1c',
              fontSize: '0.88rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '20px'
            }}>
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{typeof error === 'string' ? error : (error?.message || JSON.stringify(error))}</span>
            </div>
          )}

          {/* STEP 1: Basic Health Details */}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
                  Date of Birth <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <input
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    max={new Date().toISOString().split('T')[0]}
                    style={{
                      flex: 1,
                      padding: '12px 16px',
                      borderRadius: '12px',
                      border: '1px solid #cbd5e1',
                      fontSize: '1rem',
                      outline: 'none'
                    }}
                  />
                  {calculateAge(dob) && (
                    <span style={{
                      padding: '10px 14px',
                      background: '#f0fdfa',
                      color: '#0d9488',
                      borderRadius: '12px',
                      fontWeight: 800,
                      fontSize: '0.9rem',
                      border: '1px solid #99f6e4',
                      whiteSpace: 'nowrap'
                    }}>
                      🎂 {calculateAge(dob)}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
                    Gender <span style={{ color: '#dc2626' }}>*</span>
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      borderRadius: '12px',
                      border: '1px solid #cbd5e1',
                      fontSize: '1rem',
                      outline: 'none',
                      backgroundColor: '#ffffff'
                    }}
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
                    Blood Group <span style={{ color: '#dc2626' }}>*</span>
                  </label>
                  <select
                    value={bloodGroup}
                    onChange={(e) => setBloodGroup(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      borderRadius: '12px',
                      border: '1px solid #cbd5e1',
                      fontSize: '1rem',
                      outline: 'none',
                      backgroundColor: '#ffffff'
                    }}
                  >
                    {BLOOD_GROUPS.map(bg => (
                      <option key={bg} value={bg}>{bg}</option>
                    ))}
                  </select>
                </div>
              </div>

              {caregiverName && (
                <div style={{
                  padding: '14px 18px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  <ShieldCheck size={22} style={{ color: '#0d9488', flexShrink: 0 }} />
                  <span style={{ fontSize: '0.86rem', color: '#475569' }}>
                    Your primary caregiver <strong>{caregiverName}</strong> will use these details to help configure safety alerts.
                  </span>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Conditions & Allergies */}
          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '8px' }}>
                  Select Any Existing Health Conditions
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {CONDITIONS_OPTIONS.map(opt => {
                    const isSelected = selectedConditions.includes(opt.value);
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => toggleCondition(opt.value)}
                        style={{
                          padding: '8px 16px',
                          borderRadius: '9999px',
                          fontSize: '0.88rem',
                          fontWeight: 700,
                          border: isSelected ? '2px solid #0d9488' : '1px solid #cbd5e1',
                          backgroundColor: isSelected ? '#f0fdfa' : '#ffffff',
                          color: isSelected ? '#0d9488' : '#475569',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}
                      >
                        {isSelected && <Check size={14} />}
                        <span>{opt.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
                  Other Condition (if any)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Mild Knee Pain, Cataract"
                  value={otherCondition}
                  onChange={(e) => setOtherCondition(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.95rem',
                    outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '6px' }}>
                  Known Allergies (if any)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Penicillin, Sulfa drugs, Peanuts, None"
                  value={allergies}
                  onChange={(e) => setAllergies(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.95rem',
                    outline: 'none'
                  }}
                />
              </div>
            </div>
          )}

          {/* STEP 3: Daily Medications */}
          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 18px',
                background: '#f8fafc',
                borderRadius: '14px',
                border: '1px solid #e2e8f0'
              }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#1e293b' }}>
                    Do you take daily prescription medicines or vitamins?
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '2px' }}>
                    HomeJoy will send you gentle chimes when it’s time to take each dose.
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setHasMedications(true)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '9999px',
                      fontSize: '0.88rem',
                      fontWeight: 800,
                      backgroundColor: hasMedications ? '#0d9488' : '#e2e8f0',
                      color: hasMedications ? '#ffffff' : '#475569',
                      border: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    onClick={() => setHasMedications(false)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '9999px',
                      fontSize: '0.88rem',
                      fontWeight: 800,
                      backgroundColor: !hasMedications ? '#0d9488' : '#e2e8f0',
                      color: !hasMedications ? '#ffffff' : '#475569',
                      border: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    No
                  </button>
                </div>
              </div>

              {hasMedications ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {medications.map((med, idx) => (
                    <div 
                      key={idx}
                      style={{
                        padding: '16px',
                        borderRadius: '16px',
                        border: '1.5px solid #e2e8f0',
                        background: '#ffffff',
                        position: 'relative'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0d9488', textTransform: 'uppercase' }}>
                          Medicine #{idx + 1}
                        </span>
                        {medications.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveMedicationRow(idx)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#dc2626',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.8rem',
                              fontWeight: 700
                            }}
                          >
                            <Trash2 size={14} /> Remove
                          </button>
                        )}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '10px', marginBottom: '12px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                            Medicine Name
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. Metformin, Amlodipine"
                            value={med.medicine_name}
                            onChange={(e) => handleMedChange(idx, 'medicine_name', e.target.value)}
                            style={{
                              width: '100%',
                              padding: '10px 14px',
                              borderRadius: '10px',
                              border: '1px solid #cbd5e1',
                              fontSize: '0.92rem',
                              outline: 'none'
                            }}
                          />
                        </div>

                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                            Dosage
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. 500mg or 1 tab"
                            value={med.dosage}
                            onChange={(e) => handleMedChange(idx, 'dosage', e.target.value)}
                            style={{
                              width: '100%',
                              padding: '10px 14px',
                              borderRadius: '10px',
                              border: '1px solid #cbd5e1',
                              fontSize: '0.92rem',
                              outline: 'none'
                            }}
                          />
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                            Times to Take Daily:
                          </label>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={med.morning}
                                onChange={(e) => handleMedChange(idx, 'morning', e.target.checked)}
                              />
                              Morning (8 AM)
                            </label>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={med.afternoon}
                                onChange={(e) => handleMedChange(idx, 'afternoon', e.target.checked)}
                              />
                              Afternoon (1 PM)
                            </label>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={med.night}
                                onChange={(e) => handleMedChange(idx, 'night', e.target.checked)}
                              />
                              Night (8 PM)
                            </label>
                          </div>
                        </div>

                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                            Meal Timing
                          </label>
                          <select
                            value={med.instructions}
                            onChange={(e) => handleMedChange(idx, 'instructions', e.target.value)}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '8px',
                              border: '1px solid #cbd5e1',
                              fontSize: '0.85rem',
                              backgroundColor: '#ffffff'
                            }}
                          >
                            <option value="After meal">After meal</option>
                            <option value="Before meal">Before meal</option>
                            <option value="With water">With water</option>
                            <option value="At bedtime">At bedtime</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  ))}

                  <button
                    type="button"
                    onClick={handleAddMedicationRow}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '12px',
                      border: '1.5px dashed #0d9488',
                      backgroundColor: '#f0fdfa',
                      color: '#0d9488',
                      fontSize: '0.9rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px'
                    }}
                  >
                    <Plus size={16} />
                    <span>Add Another Daily Medicine</span>
                  </button>
                </div>
              ) : (
                <div style={{
                  padding: '30px',
                  textAlign: 'center',
                  background: '#f8fafc',
                  borderRadius: '16px',
                  border: '1px dashed #cbd5e1'
                }}>
                  <Pill size={36} style={{ color: '#94a3b8', margin: '0 auto 8px' }} />
                  <div style={{ fontWeight: 700, color: '#475569', fontSize: '0.95rem' }}>
                    No daily medications selected
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '2px' }}>
                    You can add medicines anytime later from your Medications tab.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div style={{
          padding: '18px 28px',
          borderTop: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#f8fafc'
        }}>
          {step > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              disabled={submitting}
              className="btn btn-secondary btn-sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                fontWeight: 700,
                borderRadius: '9999px'
              }}
            >
              <ArrowLeft size={16} />
              <span>Back</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#64748b',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '0.9rem'
              }}
            >
              Complete Later
            </button>
          )}

          {step < 3 ? (
            <button
              type="button"
              onClick={handleNext}
              className="btn btn-primary"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 22px',
                fontWeight: 800,
                borderRadius: '9999px',
                background: '#0d9488',
                borderColor: '#0d9488'
              }}
            >
              <span>Continue</span>
              <ArrowRight size={16} />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="btn btn-primary"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 26px',
                fontWeight: 800,
                borderRadius: '9999px',
                background: 'linear-gradient(135deg, #0d9488 0%, #059669 100%)',
                borderColor: '#0d9488',
                boxShadow: '0 4px 12px rgba(13, 148, 136, 0.3)'
              }}
            >
              <Sparkles size={16} />
              <span>{submitting ? 'Saving Profile...' : 'Save & Enter My Care Portal'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
export default HealthAndMedicationIntakeModal;

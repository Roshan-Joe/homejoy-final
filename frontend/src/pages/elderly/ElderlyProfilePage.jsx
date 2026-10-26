import React, { useState, useEffect } from 'react';
import { User, Save, ShieldCheck, Mail, Phone } from 'lucide-react';
import elderlyClientService from '../../services/elderlyClientService';

const GENDER_OPTIONS = ['Male', 'Female', 'Other', 'Prefer not to say'];
const RELATIONSHIP_OPTIONS = ['Son', 'Daughter', 'Spouse', 'Sibling', 'Neighbour', 'Local Guardian', 'Care Assistant', 'Other'];

export const ElderlyProfilePage = ({ onBack }) => {
  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    date_of_birth: '',
    gender: '',
    address: '',
    guardian_name: '',
    guardian_relationship: '',
    guardian_phone: '',
    guardian_email: '',
    guardian_report_consent: false,
    guardian_report_enabled: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    elderlyClientService.getProfile()
      .then(data => {
        setProfile(data);
        setForm({
          full_name: data.full_name || '',
          phone: data.phone || '',
          date_of_birth: data.date_of_birth || '',
          gender: data.gender || '',
          address: data.address || '',
          guardian_name: data.guardian_name || '',
          guardian_relationship: data.guardian_relationship || '',
          guardian_phone: data.guardian_phone || '',
          guardian_email: data.guardian_email || '',
          guardian_report_consent: Boolean(data.guardian_report_consent),
          guardian_report_enabled: data.guardian_report_enabled !== undefined ? Boolean(data.guardian_report_enabled) : true,
        });
      })
      .catch(() => setError('Could not load profile. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (field, value) => {
    setForm(f => ({ ...f, [field]: value }));
    setError('');
    setSuccess('');
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    // Client validation if email is set
    if (form.guardian_email && !form.guardian_report_consent) {
      setError('Please check the consent box: The guardian must agree to receive wellness reports.');
      setSaving(false);
      return;
    }

    try {
      await elderlyClientService.updateProfile({
        ...form,
        guardian_email: form.guardian_email ? form.guardian_email.trim().toLowerCase() : null
      });
      setSuccess('Profile updated successfully!');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : (err.message || 'Could not save profile. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading profile...</div>;

  return (
    <div className="animate-fade-in">
      <PageHeader icon={<User size={22} />} title="My Profile" subtitle="Update your personal information & guardian contact" onBack={onBack} />

      {/* Profile summary card */}
      {profile && (
        <div className="glass-card" style={{ padding: '20px 24px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '16px', background: 'linear-gradient(135deg, #f0fdfa, #ccfbf1)', border: '1px solid rgba(13,148,136,0.2)' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: 'var(--primary)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', fontWeight: 800 }}>
            {(profile.full_name || 'U').charAt(0).toUpperCase()}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{profile.full_name}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>{profile.email}</div>
            {profile.age && <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Age: {profile.age} years</div>}
          </div>
        </div>
      )}

      <div className="glass-card" style={{ padding: '28px' }}>
        {error && <div className="alert alert-error" style={{ marginBottom: '20px' }}>{error}</div>}
        {success && <div className="alert alert-success" style={{ marginBottom: '20px' }}>✓ {success}</div>}

        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>Full Name</label>
              <input className="form-input" value={form.full_name} onChange={e => handleChange('full_name', e.target.value)} placeholder="Your full name" required minLength={2} style={{ fontSize: '1rem', minHeight: '52px' }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>Phone Number</label>
              <input className="form-input" value={form.phone} onChange={e => handleChange('phone', e.target.value)} placeholder="+60 12-345 6789" type="tel" style={{ fontSize: '1rem', minHeight: '52px' }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>Date of Birth</label>
              <input className="form-input" type="date" value={form.date_of_birth} onChange={e => handleChange('date_of_birth', e.target.value)} max={new Date().toISOString().split('T')[0]} style={{ fontSize: '1rem', minHeight: '52px' }} />
              {form.date_of_birth && <div style={{ fontSize: '0.88rem', color: '#0d9488', marginTop: '6px', fontWeight: 600 }}>
                Your age: {calculateAge(form.date_of_birth)} years old
              </div>}
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>Gender</label>
              <select className="form-select" value={form.gender} onChange={e => handleChange('gender', e.target.value)} style={{ fontSize: '1rem', minHeight: '52px' }}>
                <option value="">Select gender</option>
                {GENDER_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>Home Address</label>
              <textarea className="form-input" value={form.address} onChange={e => handleChange('address', e.target.value)} rows={3} placeholder="Your full home address" style={{ resize: 'vertical', fontSize: '1rem' }} />
            </div>
          </div>

          {/* Guardian / Family Contact Section */}
          <div style={{
            marginTop: '28px',
            padding: '24px',
            backgroundColor: '#f0fdf4',
            border: '1.5px solid #bbf7d0',
            borderRadius: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <ShieldCheck size={22} color="#15803d" />
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#14532d', margin: 0 }}>
                  Designated Guardian & Family Contact
                </h3>
                <span style={{ fontSize: '0.85rem', color: '#166534' }}>
                  This person will receive your daily wellness reports sent by your caregiver
                </span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 700, color: '#14532d' }}>Guardian Name</label>
                <input
                  className="form-input"
                  value={form.guardian_name}
                  onChange={e => handleChange('guardian_name', e.target.value)}
                  placeholder="e.g. Robert Vance"
                  style={{ backgroundColor: '#ffffff', minHeight: '48px' }}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 700, color: '#14532d' }}>Relationship</label>
                <select
                  className="form-select"
                  value={form.guardian_relationship}
                  onChange={e => handleChange('guardian_relationship', e.target.value)}
                  style={{ backgroundColor: '#ffffff', minHeight: '48px' }}
                >
                  <option value="">Select relationship</option>
                  {RELATIONSHIP_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 700, color: '#14532d' }}>Guardian Phone</label>
                <input
                  className="form-input"
                  type="tel"
                  value={form.guardian_phone}
                  onChange={e => handleChange('guardian_phone', e.target.value)}
                  placeholder="+1 (555) 987-6543"
                  style={{ backgroundColor: '#ffffff', minHeight: '48px' }}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 700, color: '#14532d' }}>Guardian Email (For Daily Reports)</label>
                <input
                  className="form-input"
                  type="email"
                  value={form.guardian_email}
                  onChange={e => handleChange('guardian_email', e.target.value)}
                  placeholder="guardian@example.com"
                  style={{ backgroundColor: '#ffffff', minHeight: '48px' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #bbf7d0' }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '0.9rem', color: '#166534', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={form.guardian_report_consent}
                  onChange={e => handleChange('guardian_report_consent', e.target.checked)}
                  style={{ marginTop: '3px', accentColor: '#15803d', width: '16px', height: '16px' }}
                />
                <span style={{ fontWeight: 600 }}>
                  The guardian has agreed to receive daily wellness reports via email
                </span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.9rem', color: '#166534', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={form.guardian_report_enabled}
                  onChange={e => handleChange('guardian_report_enabled', e.target.checked)}
                  style={{ accentColor: '#15803d', width: '16px', height: '16px' }}
                />
                <span>Allow caregiver to email reports to this address</span>
              </label>
            </div>
          </div>

          <div style={{ marginTop: '28px' }}>
            <button type="submit" className="btn btn-primary" disabled={saving} style={{ width: '100%', minHeight: '60px', fontSize: '1.1rem', fontWeight: 800, borderRadius: '14px' }}>
              {saving ? 'Saving…' : '💾  Save My Profile'}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
};

function calculateAge(dobStr) {
  if (!dobStr) return '—';
  const dob = new Date(dobStr);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age--;
  return age;
}

export const PageHeader = ({ icon, title, subtitle, onBack }) => (
  <div style={{ marginBottom: '24px' }}>
    {onBack && (
      <button
        onClick={onBack}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '8px',
          padding: '12px 20px', borderRadius: '12px',
          border: '1.5px solid #e2e8f0', background: '#f8fafc',
          color: '#475569', fontWeight: 700, fontSize: '1rem',
          cursor: 'pointer', marginBottom: '18px', minHeight: '48px',
          transition: 'all 0.18s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = '#e2e8f0'; }}
        onMouseLeave={e => { e.currentTarget.style.background = '#f8fafc'; }}
      >
        ← Back to Home
      </button>
    )}
    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
      <div style={{
        padding: '12px', background: 'var(--primary-light, #ccfbf1)',
        borderRadius: '14px', flexShrink: 0,
      }}>
        {React.cloneElement(icon, { color: 'var(--primary, #0d9488)', size: 24 })}
      </div>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#1e293b', lineHeight: 1.2 }}>{title}</h1>
        {subtitle && <p style={{ color: '#64748b', fontSize: '0.92rem', marginTop: '4px' }}>{subtitle}</p>}
      </div>
    </div>
  </div>
);

export default ElderlyProfilePage;

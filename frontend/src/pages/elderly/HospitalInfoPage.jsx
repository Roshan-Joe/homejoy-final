import React, { useState, useEffect } from 'react';
import { Hospital } from 'lucide-react';
import elderlyClientService from '../../services/elderlyClientService';
import { PageHeader } from './ElderlyProfilePage';

export const HospitalInfoPage = ({ onBack }) => {
  const [form, setForm] = useState({ hospital_name: '', location: '', department: '', contact_number: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    elderlyClientService.getHospitalInfo()
      .then(data => setForm({ hospital_name: data.hospital_name || '', location: data.location || '', department: data.department || '', contact_number: data.contact_number || '' }))
      .catch(() => setError('Could not load hospital information.'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await elderlyClientService.updateHospitalInfo(form);
      setSuccess('Hospital information saved!');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : (err.message || 'Could not save. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>;

  return (
    <div className="animate-fade-in">
      <PageHeader icon={<Hospital size={22} />} title="Hospital Information" subtitle="Store your hospital details for easy reference — not an official medical record" onBack={onBack} />
      <div className="glass-card" style={{ padding: '28px' }}>
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">✓ {success}</div>}
        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
            {[
              { field: 'hospital_name', label: 'Hospital Name', placeholder: 'e.g. General Hospital Kuala Lumpur' },
              { field: 'location', label: 'Hospital Location / Address', placeholder: 'Full address or area' },
              { field: 'department', label: 'Department / Ward', placeholder: 'e.g. Cardiology, Geriatrics' },
              { field: 'contact_number', label: 'Hospital Contact Number', placeholder: '+60 3-2615 5555', type: 'tel' },
            ].map(({ field, label, placeholder, type = 'text' }) => (
              <div key={field} className="form-group">
                <label className="form-label" style={{ fontSize: '1rem', fontWeight: 700 }}>{label}</label>
                <input
                  className="form-input"
                  type={type}
                  value={form[field]}
                  onChange={e => { setError(''); setSuccess(''); setForm(f => ({ ...f, [field]: e.target.value })); }}
                  placeholder={placeholder}
                  style={{ fontSize: '1rem', minHeight: '52px' }}
                />
              </div>
            ))}
          </div>
          <div style={{ marginTop: '28px' }}>
            <button type="submit" className="btn btn-primary" disabled={saving} style={{ width: '100%', minHeight: '60px', fontSize: '1.1rem', fontWeight: 800, borderRadius: '14px' }}>
              {saving ? 'Saving…' : '💾  Save Hospital Information'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

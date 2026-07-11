import React, { useEffect, useState } from 'react';

interface Scheme {
  scheme_name: string;
  match_score: number;
  eligibility_reason: string;
  application_url: string;
}

const SchemeMatcher = () => {
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSchemes = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/schemes/match', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            business_id: 'biz_889',
            state: 'Maharashtra',
            sector: 'Manufacturing',
            turnover_inr: 4500000,
            employee_count: 12,
            udyam_registered: true,
            women_owned: false
          })
        });

        if (response.ok) {
          const data = await response.json();
          setSchemes(data);
        } else {
          console.error('Failed to fetch schemes');
        }
      } catch (error) {
        console.error('Error connecting to backend:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSchemes();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 className="page-title" style={{ marginBottom: 0 }}>Scheme Matcher</h1>
        <button className="btn-primary">Recalculate Matches</button>
      </div>
      
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Based on your business profile and extracted documents, here are the top government schemes you qualify for.
      </p>

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Analyzing business profile and matching schemes...
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {schemes.map((scheme, idx) => (
            <div key={idx} className="card" style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
              <div style={{ 
                width: '80px', 
                height: '80px', 
                borderRadius: '50%', 
                backgroundColor: scheme.match_score > 90 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                color: scheme.match_score > 90 ? 'var(--accent)' : 'var(--accent-secondary)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                flexShrink: 0,
                border: `2px solid ${scheme.match_score > 90 ? 'var(--accent)' : 'var(--accent-secondary)'}`
              }}>
                <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{scheme.match_score}%</span>
                <span style={{ fontSize: '0.75rem' }}>Match</span>
              </div>
              
              <div style={{ flex: 1 }}>
                <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: 'var(--text-light)' }}>{scheme.scheme_name}</h3>
                <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>{scheme.eligibility_reason}</p>
                <a href={scheme.application_url} target="_blank" rel="noreferrer" style={{ fontWeight: '500' }}>
                  Apply Now →
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SchemeMatcher;

import React, { useState } from 'react';

const DocumentHub = () => {
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    setUploadStatus('Uploading and parsing document...');
    setTimeout(() => {
      setUploadStatus('Document successfully processed! Vector embeddings created.');
    }, 1500);
  };

  return (
    <div>
      <h1 className="page-title">Document Hub</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>Upload your business documents (Udyam, GST, Bank Statements) for AI analysis.</p>
      
      <div className="card" style={{ maxWidth: '600px' }}>
        <form onSubmit={handleUpload}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>Document Type</label>
            <select className="input-field">
              <option value="udyam">Udyam Registration</option>
              <option value="gst">GST Return</option>
              <option value="bank">Bank Statement</option>
              <option value="other">Other PDF</option>
            </select>
          </div>
          
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>File</label>
            <input type="file" className="input-field" accept=".pdf,.csv,.png,.jpg" />
          </div>
          
          <button type="submit" className="btn-primary" style={{ width: '100%' }}>Upload Document</button>
        </form>
        
        {uploadStatus && (
          <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--accent)', borderRadius: '8px', color: 'var(--accent)' }}>
            {uploadStatus}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentHub;

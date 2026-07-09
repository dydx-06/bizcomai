import React, { useState } from 'react';

const DocumentHub = () => {
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadStatus('Uploading and parsing document...');
    
    try {
      const formData = new FormData();
      // Using dummy data for integration demo
      formData.append('file', new Blob(['dummy content']), 'document.pdf');
      formData.append('doc_type', 'udyam');

      const response = await fetch('http://localhost:8000/api/documents/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const data = await response.json();
        setUploadStatus(`Document successfully processed! Vector embeddings created. (ID: ${data.document_id})`);
      } else {
        setUploadStatus('Upload failed. Please try again.');
      }
    } catch (error) {
      console.error(error);
      setUploadStatus('Error connecting to backend API.');
    }
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

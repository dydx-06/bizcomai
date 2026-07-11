import React, { useState } from 'react';

const AIAdvisor = () => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your AI Business Advisor. You can ask me questions about your uploaded documents, cashflow, or government schemes.' }
  ]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    // Add user message
    const userMessage = { role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);
    setQuery('');
    
    try {
      const response = await fetch('http://localhost:8000/api/qa/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query_text: userMessage.content,
          language: 'en'
        })
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer_text 
        }]);
      } else {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: 'Sorry, I encountered an error communicating with the server.' 
        }]);
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, the connection to the server failed.' 
      }]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <h1 className="page-title">AI Advisor</h1>
      
      <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
        <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((msg, idx) => (
            <div key={idx} style={{ 
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              backgroundColor: msg.role === 'user' ? 'var(--primary)' : 'rgba(15, 23, 42, 0.6)',
              padding: '1rem',
              borderRadius: '12px',
              maxWidth: '80%',
              border: msg.role === 'user' ? 'none' : '1px solid var(--border)'
            }}>
              {msg.content}
            </div>
          ))}
        </div>
        
        <div style={{ padding: '1.5rem', borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-card)' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '1rem' }}>
            <button type="button" className="btn-primary" style={{ backgroundColor: 'var(--accent)', padding: '0.75rem' }} title="Hold to record (Stub)">
              🎤
            </button>
            <input 
              type="text" 
              className="input-field" 
              style={{ marginBottom: 0, flex: 1 }} 
              placeholder="Ask in English, Hindi, or Marathi..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="btn-primary">Send</button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AIAdvisor;

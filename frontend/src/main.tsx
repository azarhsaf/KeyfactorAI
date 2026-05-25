import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

const qs = ['How many certificates expire next week?', 'Show certificates expiring in 30 days.', 'Show expired certificates.', 'Show failed jobs.', 'Show inventory summary.'];

const cardStyle = { padding: 12, border: '1px solid #d1d5db', borderRadius: 8, background: '#fff' } as React.CSSProperties;

function App() {
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [diag, setDiag] = useState<any>(null);
  const [mode, setMode] = useState<'light'|'dark'>('light');
  const [page, setPage] = useState<'chat'|'diagnostics'|'audit'>('chat');

  const loadDiag = async () => setDiag(await (await fetch('/api/keyfactor/diagnostics')).json());
  useEffect(() => { loadDiag(); }, []);
  const ask = async (q: string) => {
    const payload = { prompt: q, username: 'admin' };
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    setAnswer(await r.json());
  };

  const bg = mode === 'dark' ? '#0f172a' : '#f8fafc';
  const fg = mode === 'dark' ? '#e2e8f0' : '#111827';

  return <div style={{display:'grid',gridTemplateColumns:'250px 1fr',height:'100vh',fontFamily:'Inter,Arial',background:bg,color:fg}}>
    <aside style={{background: mode==='dark' ? '#111827' : '#1f2937', color:'white', padding:16}}>
      <h2>Keyfactor AI</h2>
      <div>Version {diag?.app_version || '0.1.0'} release</div>
      <div style={{marginTop:12}}>Branding Placeholder</div>
      <button onClick={()=>setMode(mode==='dark'?'light':'dark')} style={{marginTop:10}}>Toggle {mode==='dark'?'Light':'Dark'}</button>
      <hr />
      <button onClick={()=>setPage('chat')}>Chat</button>
      <button onClick={()=>setPage('diagnostics')}>Diagnostics</button>
      <button onClick={()=>setPage('audit')}>Audit (placeholder)</button>
    </aside>
    <main style={{padding:16,overflow:'auto'}}>
      {page === 'chat' && <>
        <h1>Assistant Chat</h1>
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{qs.map(q=><button key={q} onClick={()=>{setPrompt(q);ask(q);}}>{q}</button>)}</div>
        <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:80,marginTop:8}} />
        <button onClick={()=>ask(prompt)}>Ask</button>
        {answer && <div style={{...cardStyle, marginTop:12}}>
          <b>Answer</b><p>{answer.answer}</p>
          <p>Source: {answer.source} | Tool: {answer.tool} | Timestamp: {answer.timestamp}</p>
          {answer.diagnostics && <div style={{...cardStyle, background:'#fff7ed'}}>
            <p>Command reachable: {String(answer.diagnostics.api_reachable)}</p>
            <p>Authentication: {String(answer.diagnostics.authenticated)}</p>
            <p>Endpoint: {answer.diagnostics.endpoint_tested}</p>
            <p>HTTP: {answer.diagnostics.http_status_code}</p>
            <p>Message: {answer.diagnostics.message}</p>
          </div>}
        </div>}
      </>}

      {page === 'diagnostics' && <>
        <h1>System Health</h1><button onClick={loadDiag}>Refresh</button>
        {diag && <div style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:10,marginTop:12}}>
          <div style={cardStyle}><b>Frontend status</b><div>{diag.frontend_status}</div></div>
          <div style={cardStyle}><b>Backend status</b><div>{diag.backend_status}</div></div>
          <div style={cardStyle}><b>Last timestamp</b><div>{diag.timestamp}</div></div>
          <div style={cardStyle}><b>Keyfactor API reachable</b><div>{String(diag.keyfactor?.api_reachable)}</div></div>
          <div style={cardStyle}><b>Keyfactor auth</b><div>{String(diag.keyfactor?.authenticated)}</div></div>
          <div style={cardStyle}><b>Endpoint tested</b><div>{diag.keyfactor?.endpoint_tested}</div></div>
          <div style={cardStyle}><b>HTTP status code</b><div>{String(diag.keyfactor?.http_status_code)}</div></div>
          <div style={cardStyle}><b>Ollama status</b><div>{diag.ollama?.status}</div></div>
          <div style={cardStyle}><b>Model</b><div>{diag.ollama?.model}</div></div>
        </div>}
      </>}

      {page === 'audit' && <div style={cardStyle}><h2>Audit Page Placeholder</h2><p>Detailed audit table/charts can be added next.</p></div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />);

import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

const qs = [
  'How many certificates expire next week?',
  'Show certificates expiring in 30 days.',
  'Show expired certificates.',
  'Show failed jobs.',
  'Show inventory summary.'
];

function csv(rows: any[]) {
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')].concat(rows.map(r => headers.map(h => JSON.stringify(r[h] ?? '')).join(',')));
  return lines.join('\n');
}

function App() {
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [diag, setDiag] = useState<any>(null);
  const [expTest, setExpTest] = useState<any>(null);

  const loadDiag = async () => {
    const res = await fetch('/api/keyfactor/diagnostics');
    setDiag(await res.json());
  };

  const testExpiring = async () => {
    const res = await fetch('/api/keyfactor/test-expiring?days=7');
    setExpTest(await res.json());
  };

  useEffect(() => { loadDiag(); }, []);

  const ask = async (q: string) => {
    setPrompt(q);
    const res = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ prompt: q, username: 'admin' })});
    setAnswer(await res.json());
  };

  return <div style={{display:'grid',gridTemplateColumns:'260px 1fr',fontFamily:'Arial',height:'100vh'}}>
    <aside style={{background:'#111827',color:'white',padding:16}}>
      <h2>Keyfactor AI</h2>
      <p>Version {diag?.app_version || '0.1.0'} (release)</p>
      <p>Suggested questions</p>
      {qs.map(q=><button key={q} onClick={()=>ask(q)} style={{display:'block',marginBottom:8,width:'100%'}}>{q}</button>)}
    </aside>
    <main style={{padding:16, overflow:'auto'}}>
      <h1>Chat Assistant</h1>
      <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:80}} />
      <button onClick={()=>ask(prompt)}>Ask</button>

      {answer && <div style={{marginTop:16,padding:12,border:'1px solid #ddd'}}>
        <p><b>Answer:</b> {answer.answer}</p>
        <p>Source: {answer.source} | Tool: {answer.tool} | Timestamp: {answer.timestamp}</p>
        {answer.diagnostics && <div style={{background:'#fff7ed',padding:10}}>
          <b>Connection diagnostics</b>
          <p>Command reachable: {String(answer.diagnostics.command_reachable)}</p>
          <p>Auth OK: {String(answer.diagnostics.auth_ok)}</p>
          <p>Failed URL: {answer.diagnostics.cert_search_url || answer.diagnostics.swagger_url}</p>
          <p>Status code: {String(answer.diagnostics.cert_search_status || answer.diagnostics.swagger_status)}</p>
          <p>Recommended fix: {answer.diagnostics.diagnosis}</p>
        </div>}
        <button onClick={()=>{const blob=new Blob([csv(answer.table||[])],{type:'text/csv'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.csv';a.click();}}>Export CSV</button>
        <table border={1}><thead><tr>{answer.table?.[0] && Object.keys(answer.table[0]).map((h:string)=><th key={h}>{h}</th>)}</tr></thead>
        <tbody>{answer.table?.map((r:any, i:number)=><tr key={i}>{Object.keys(r).map(k=><td key={k}>{String(r[k] ?? '')}</td>)}</tr>)}</tbody></table>
      </div>}

      <h2 style={{marginTop:24}}>Command Connection / System Health</h2>
      <button onClick={loadDiag}>Test Connection</button>
      <button onClick={testExpiring} style={{marginLeft:8}}>Expiring Cert Test (7d)</button>
      {diag && <div style={{marginTop:12,padding:12,border:'1px solid #ddd'}}>
        <p>Last checked: {diag.timestamp}</p>
        <p>Command reachable: {String(diag.keyfactor?.command_reachable)}</p>
        <p>Swagger URL: {diag.keyfactor?.swagger_url}</p>
        <p>Swagger status: {String(diag.keyfactor?.swagger_status)}</p>
        <p>Auth status: {String(diag.keyfactor?.auth_ok)}</p>
        <p>Certificate search status: {String(diag.keyfactor?.cert_search_status)}</p>
        <p>Error: {diag.keyfactor?.error || 'none'}</p>
        <p>Diagnosis: {diag.keyfactor?.diagnosis}</p>
        <p>Model reachable: {String(diag.model?.reachable)}</p>
        <p>Database OK: {String(diag.database?.ok)}</p>
      </div>}
      {expTest && <div style={{marginTop:12,padding:12,border:'1px solid #ddd'}}>
        <p>Expiring test count (days={expTest.days}): {expTest.count}</p>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />);

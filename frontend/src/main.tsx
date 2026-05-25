import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';

const qs = [
  'How many certificates expire next week?',
  'Show certificates expiring in 30 days.',
  'Show failed orchestrator jobs.'
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
  const ask = async (q: string) => {
    setPrompt(q);
    const res = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ prompt: q, username: 'admin' })});
    setAnswer(await res.json());
  };
  return <div style={{display:'grid',gridTemplateColumns:'260px 1fr',fontFamily:'Arial',height:'100vh'}}>
    <aside style={{background:'#111827',color:'white',padding:16}}><h2>Keyfactor AI</h2><p>Suggested questions</p>{qs.map(q=><button key={q} onClick={()=>ask(q)} style={{display:'block',marginBottom:8,width:'100%'}}>{q}</button>)}</aside>
    <main style={{padding:16}}>
      <h1>Chat Assistant</h1>
      <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:80}} />
      <button onClick={()=>ask(prompt)}>Ask</button>
      {answer && <div><p><b>Answer:</b> {answer.answer}</p><p>Source: {answer.source} | Tool: {answer.tool} | Timestamp: {answer.timestamp}</p>
      <button onClick={()=>{const blob=new Blob([csv(answer.table||[])],{type:'text/csv'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.csv';a.click();}}>Export CSV</button>
      <table border={1}><thead><tr>{answer.table?.[0] && Object.keys(answer.table[0]).map((h:string)=><th key={h}>{h}</th>)}</tr></thead>
      <tbody>{answer.table?.map((r:any, i:number)=><tr key={i}>{Object.keys(r).map(k=><td key={k}>{String(r[k] ?? '')}</td>)}</tr>)}</tbody></table></div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />);

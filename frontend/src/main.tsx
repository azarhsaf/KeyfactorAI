import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

function App() {
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [diag, setDiag] = useState<any>(null);
  const [library, setLibrary] = useState<Record<string, [string,string,object][]>>({});
  const [qFilter, setQFilter] = useState('');

  useEffect(() => {
    (async()=>{
      setDiag(await (await fetch('/api/keyfactor/diagnostics')).json());
      setLibrary(await (await fetch('/api/question-library')).json());
    })();
  }, []);

  const ask = async (q: string) => {
    const r = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({prompt:q, username:'admin'})});
    setAnswer(await r.json());
  };

  const filtered = useMemo(() => {
    const out: any = {};
    Object.entries(library).forEach(([cat, items]) => {
      out[cat] = items.filter(([q]) => q.toLowerCase().includes(qFilter.toLowerCase()));
    });
    return out;
  }, [library, qFilter]);

  return <div style={{display:'grid',gridTemplateColumns:'320px 1fr',height:'100vh',fontFamily:'Arial'}}>
    <aside style={{padding:12,background:'#1f2937',color:'#fff',overflow:'auto'}}>
      <h2>Keyfactor AI Assistant</h2>
      <div>v{diag?.app_version || '0.1.0'}</div>
      <input placeholder='Search supported questions' value={qFilter} onChange={e=>setQFilter(e.target.value)} style={{width:'100%',margin:'10px 0'}}/>
      {Object.entries(filtered).map(([cat, items]: any)=><div key={cat}><h4>{cat}</h4>{items.map(([q]: any)=><button key={q} onClick={()=>setPrompt(q)} style={{display:'block',width:'100%',marginBottom:6,textAlign:'left'}}>{q}</button>)}</div>)}
    </aside>
    <main style={{padding:16,overflow:'auto'}}>
      <h1>Deterministic Assistant</h1>
      <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} style={{width:'100%',height:100}} />
      <button onClick={()=>ask(prompt)}>Run Question</button>
      {answer && <div style={{border:'1px solid #ccc',padding:12,marginTop:12}}>
        <h3>Answer</h3>
        <p>{answer.answer}</p>
        {answer.ai_summary && <p><b>AI wording suggestion:</b> {answer.ai_summary}</p>}
        <p><b>Tool used:</b> {answer.tool}</p>
        <p><b>Records scanned:</b> {answer.diagnostics?.records_scanned ?? 0}</p>
        <p><b>Result count:</b> {answer.result_count}</p>
        <p><b>Source:</b> {answer.source}</p>
        <p><b>Timestamp:</b> {answer.timestamp}</p>
        <table border={1}><thead><tr>{answer.table?.[0] && Object.keys(answer.table[0]).map((h:string)=><th key={h}>{h}</th>)}</tr></thead>
        <tbody>{answer.table?.map((r:any,i:number)=><tr key={i}>{Object.keys(r).map(k=><td key={k}>{String(r[k] ?? '')}</td>)}</tr>)}</tbody></table>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />);

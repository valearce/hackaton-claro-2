(async () => {
    if (location.origin !== 'https://q-nexus.vercel.app') throw new Error('Unexpected application origin');
    const sessionResponse = await fetch('/api/auth/me', {credentials:'include',cache:'no-store',signal:AbortSignal.timeout(10000)});
    if (!sessionResponse.ok) throw new Error('Authenticated session unavailable: '+sessionResponse.status);
    const session = await sessionResponse.json();
    if (!session.accessToken || !['admin','dev'].includes(session.usuario?.rol)) throw new Error('Administrative session required');
    const base='https://gskjauouokflcdbqgnxu.supabase.co/rest/v1';
    const headers={apikey:"sb_publishable_IGNrlN9WJO9iKoo05-1kZw_dHiEnfT0",Authorization:'Bearer '+session.accessToken,'Content-Type':'application/json'};
    const beforeResponse=await fetch(base+'/asistencia_obra?id=eq.591&select=id,usuario_cedula,frente_id,fecha,hora_entrada,hora_salida,anulada_at',{headers,cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!beforeResponse.ok)throw new Error('Attendance lookup failed: '+beforeResponse.status);
    const rows=await beforeResponse.json();
    if(rows.length!==1)throw new Error('Attendance row not uniquely visible');
    const row=rows[0];
    if(row.fecha!=='2026-10-30'||row.frente_id!==1||row.anulada_at!==null||row.hora_salida!==null||Date.parse(row.hora_entrada)!==Date.parse('2026-10-30T08:09:01.417-05:00'))throw new Error('Attendance changed since inspection; no correction submitted');
    const response=await fetch(base+'/rpc/rpc_asistencia_corregir',{method:'POST',headers,body:JSON.stringify({p_payload:{
        cedula:row.usuario_cedula,frente_id:row.frente_id,entrada:'2026-10-30T07:00:00-05:00',registro_id:row.id,
        motivo:'Ingreso a las 07:00 por falla de la PWA reportada en Tetuán; ajuste autorizado por administración.'
    }}),signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error('Correction RPC failed: '+response.status);
    const result=await response.json();
    return {status:result.status,registro_id:result.registro_id,message:result.mensaje};
})()

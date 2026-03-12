(function(){
  window.api = window.api || {};

  async function readJson(res){
    try { return await res.json(); } catch (e) { return { ok:false, error:'Invalid JSON response' }; }
  }

  window.api.startVM = async function(vmname){
    const res = await fetch(`/dashboard/api/start/${encodeURIComponent(vmname)}`, {method:'POST'});
    const body = await readJson(res);
    return { ok: !!(res.ok && body && body.ok), status: res.status, body };
  };

  window.api.getVMStatus = async function(vmname){
    const res = await fetch(`/dashboard/api/vm/${encodeURIComponent(vmname)}/status`, { cache:'no-store' });
    return await readJson(res);
  };

  window.api.recoverVM = async function(vmname, payload){
    const res = await fetch(`/dashboard/api/vm/${encodeURIComponent(vmname)}/recover`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload || {})
    });
    const body = await readJson(res);
    return { ok: !!(res.ok && body && body.ok), status: res.status, body };
  };

  window.api.escalateVM = async function(vmname, payload){
    const res = await fetch(`/dashboard/api/vm/${encodeURIComponent(vmname)}/escalate`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload || {})
    });
    const body = await readJson(res);
    return { ok: !!(res.ok && body && body.ok), status: res.status, body };
  };
})();

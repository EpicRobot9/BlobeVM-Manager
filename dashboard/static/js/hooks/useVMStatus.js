(function(){
  window.useVMStatus = function(vmname, opts){
    const interval = (opts && opts.interval) || 1500;
    const { useState, useEffect } = React;
    return (function useHook(){
      const seeded = (window.__VM_WRAPPER_INIT && window.__VM_WRAPPER_INIT.vmname === vmname && window.__VM_WRAPPER_INIT.initialStatus) || { ok:true, status:'unknown', state:'unknown', running:false, healthy:false, crashed:false, exists:false };
      const [state, setState] = useState(seeded);
      useEffect(()=>{
        let cancelled = false;
        let handle = null;
        async function pollOnce(){
          try{
            const j = await window.api.getVMStatus(vmname);
            if(!cancelled) setState(j && typeof j === 'object' ? j : { ok:false, status:'unknown', state:'unknown' });
          }catch(e){
            if(!cancelled) setState({ ok:false, error:String(e), status:'unknown', state:'unknown', running:false, healthy:false, crashed:false, exists:false });
          }
        }
        pollOnce();
        handle = setInterval(pollOnce, interval);
        return ()=>{ cancelled = true; if(handle) clearInterval(handle); };
      }, [vmname, interval]);
      return state;
    })();
  };
})();

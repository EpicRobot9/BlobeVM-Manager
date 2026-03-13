(function(){
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const init = window.__VM_WRAPPER_INIT || { vmname:null, vmurl:null };
  const MIN_LOADING_MS = 1800;

  function App(){
    const vm = window.useVMStatus(init.vmname, { interval: 1600 });
    const [iframeReady, setIframeReady] = React.useState(false);
    const [frameLoaded, setFrameLoaded] = React.useState(false);
    const [panelOpen, setPanelOpen] = React.useState(false);
    const [panelMounted, setPanelMounted] = React.useState(false);
    const [actionMsg, setActionMsg] = React.useState('');
    const [actionTone, setActionTone] = React.useState('ok');
    const [stopBusy, setStopBusy] = React.useState(false);
    const [logoutBusy, setLogoutBusy] = React.useState(false);
    const startMsRef = React.useRef(Date.now());
    const readySinceRef = React.useRef(null);
    const closeTimerRef = React.useRef(null);

    React.useEffect(()=>{
      if(!(vm && vm.running)){
        startMsRef.current = Date.now();
        readySinceRef.current = null;
        setIframeReady(false);
        setFrameLoaded(false);
      }
    }, [vm && vm.running]);

    React.useEffect(()=>{
      const frame = document.getElementById('vmframe');
      if(!frame) return;
      const onLoad = ()=> setFrameLoaded(true);
      frame.addEventListener('load', onLoad);
      return ()=> frame.removeEventListener('load', onLoad);
    }, []);

    const closePanel = React.useCallback(()=>{
      setPanelOpen(false);
      if(closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = window.setTimeout(()=>{
        setPanelMounted(false);
        closeTimerRef.current = null;
      }, 220);
    }, []);

    const openPanel = React.useCallback(()=>{
      if(closeTimerRef.current){
        window.clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      setPanelMounted(true);
      window.requestAnimationFrame(()=> setPanelOpen(true));
    }, []);

    React.useEffect(()=>()=>{
      if(closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
    }, []);

    async function stopVm(){
      if(stopBusy) return;
      setStopBusy(true);
      setActionMsg('');
      try {
        const res = await window.api.stopVMViaPortal(init.vmname);
        if(!res.ok) throw new Error((res.body && (res.body.error || res.body.message)) || `HTTP ${res.status}`);
        setActionTone('ok');
        setActionMsg('Stop request sent. The VM should shut down in a moment.');
      } catch (e) {
        setActionTone('err');
        setActionMsg(String(e));
      }
      setStopBusy(false);
    }

    async function logoutPortal(){
      if(logoutBusy) return;
      setLogoutBusy(true);
      setActionMsg('');
      try {
        const res = await window.api.logoutPortal();
        if(!res.ok) throw new Error((res.body && (res.body.error || res.body.message)) || `HTTP ${res.status}`);
        window.location.href = '/portal/login?next=' + encodeURIComponent(window.location.pathname + window.location.search);
      } catch (e) {
        setActionTone('err');
        setActionMsg(String(e));
      }
      setLogoutBusy(false);
    }

    React.useEffect(()=>{
      let cancelled = false;
      async function check(){
        if(!(vm && vm.running) || !init.vmurl){
          if(!cancelled) {
            setIframeReady(false);
            setFrameLoaded(false);
          }
          return;
        }
        try {
          const res = await fetch(init.vmurl, { method:'GET', cache:'no-store', credentials:'same-origin' });
          const ok = !!(res && res.ok);
          if(ok){
            if(!readySinceRef.current) readySinceRef.current = Date.now();
          } else {
            readySinceRef.current = null;
            if(!cancelled) setFrameLoaded(false);
          }
          const stableReady = ok && readySinceRef.current && (Date.now() - readySinceRef.current >= 1800);
          if(!cancelled) setIframeReady(!!stableReady);
        } catch (e) {
          readySinceRef.current = null;
          if(!cancelled) {
            setIframeReady(false);
            setFrameLoaded(false);
          }
        }
      }
      check();
      const t = setInterval(check, 1200);
      return ()=>{ cancelled = true; clearInterval(t); };
    }, [vm && vm.running, init.vmurl]);

    React.useEffect(()=>{
      const frame = document.getElementById('vmframe');
      if(!frame) return;
      const minElapsed = Date.now() - startMsRef.current >= MIN_LOADING_MS;
      const showFrame = !!(vm && vm.running && iframeReady && frameLoaded && minElapsed);
      if(showFrame){
        if(init.vmurl && frame.src !== init.vmurl) frame.src = init.vmurl;
        frame.style.display = 'block';
      } else {
        if(vm && vm.running && init.vmurl && frame.src !== init.vmurl){
          frame.src = init.vmurl;
        }
        frame.style.display = 'none';
      }
    }, [vm && vm.running, iframeReady, frameLoaded, init.vmurl]);

    const readyForReveal = !!(vm && vm.running && iframeReady && frameLoaded && (Date.now() - startMsRef.current >= MIN_LOADING_MS));
    const controls = React.createElement(React.Fragment, null,
      !panelOpen ? React.createElement('button', {
        className:'vm-controls-handle',
        type:'button',
        onClick: openPanel,
        title:'Open VM controls'
      }, '≡') : null,
      React.createElement('div', { className:'vm-controls-shell' },
        panelMounted ? React.createElement('div', { className:`vm-controls-panel ${panelOpen ? 'open' : 'closed'}` },
          React.createElement('div', { className:'vm-controls-title' }, 'VM Controls'),
          React.createElement('div', { className:'vm-controls-copy' }, 'Quick wrapper controls for the current VM.'),
          React.createElement('div', { className:'vm-controls-row' },
            React.createElement('button', { className:'btn btn-danger', onClick: stopVm, disabled: stopBusy || !(vm && vm.running) }, stopBusy ? 'Stopping…' : ((vm && vm.running) ? 'Stop VM' : 'VM already stopped')),
            React.createElement('button', { className:'btn btn-secondary', onClick: ()=>{ window.location.href = '/portal'; } }, 'Open Portal'),
            React.createElement('button', { className:'btn btn-secondary', onClick: logoutPortal, disabled: logoutBusy }, logoutBusy ? 'Logging out…' : 'Log out'),
            React.createElement('button', { className:'btn btn-ghost', onClick: closePanel }, 'Close')
          ),
          actionMsg ? React.createElement('div', { className:`vm-toast ${actionTone}` }, actionMsg) : null
        ) : null
      )
    );

    return React.createElement(React.Fragment, null,
      controls,
      readyForReveal ? null : React.createElement(window.VMFallback, { vmname:init.vmname, vmurl:init.vmurl, iframeReady: iframeReady && frameLoaded })
    );
  }

  try {
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
  } catch (e) {
    console.error('VM wrapper mount failed', e);
  }
})();

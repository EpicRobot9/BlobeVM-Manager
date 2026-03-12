(function(){
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const init = window.__VM_WRAPPER_INIT || { vmname:null, vmurl:null };
  const MIN_LOADING_MS = 1800;

  function App(){
    const vm = window.useVMStatus(init.vmname, { interval: 1600 });
    const [iframeReady, setIframeReady] = React.useState(false);
    const [frameLoaded, setFrameLoaded] = React.useState(false);
    const startMsRef = React.useRef(Date.now());
    const readySinceRef = React.useRef(null);

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
    if(readyForReveal) return null;
    return React.createElement(window.VMFallback, { vmname:init.vmname, vmurl:init.vmurl, iframeReady: iframeReady && frameLoaded });
  }

  try {
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
  } catch (e) {
    console.error('VM wrapper mount failed', e);
  }
})();

(function(){
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const init = window.__VM_WRAPPER_INIT || { vmname:null, vmurl:null };

  function App(){
    const vm = window.useVMStatus(init.vmname, { interval: 1600 });
    const live = !!(vm && vm.running);

    React.useEffect(()=>{
      const frame = document.getElementById('vmframe');
      if(!frame) return;
      if(live){
        frame.style.display = 'block';
        if(vm.url && frame.src !== vm.url) frame.src = vm.url;
      } else {
        frame.style.display = 'none';
      }
    }, [live, vm && vm.url]);

    if(live) return null;
    return React.createElement(window.VMFallback, { vmname:init.vmname, vmurl:vm && vm.url ? vm.url : init.vmurl });
  }

  try {
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
  } catch (e) {
    console.error('VM wrapper mount failed', e);
  }
})();

(function(){
  const React = window.React;
  const { useState, useEffect, useMemo } = React;

  function statusTone(vm){
    if(vm && vm.running) return 'live';
    if(vm && vm.crashed) return 'crashed';
    if(vm && vm.state === 'restarting') return 'recovering';
    return 'down';
  }

  function humanState(vm){
    if(!vm) return 'Checking VM status…';
    if(vm.running && vm.healthy) return 'Online and healthy';
    if(vm.running) return 'VM is online';
    if(vm.crashed) return 'This VM crashed';
    if(vm.state === 'not-found') return 'This VM is not provisioned correctly';
    if(vm.state === 'restarting') return 'This VM is recovering';
    return 'This VM is currently down';
  }

  function VMFallback(props){
    const vmname = props.vmname;
    const vmurl = props.vmurl;
    const vm = window.useVMStatus(vmname, { interval: 1600 });
    const [phase, setPhase] = useState('idle'); // idle | starting | recovering | error | sent
    const [errorMsg, setErrorMsg] = useState('');
    const [details, setDetails] = useState('');
    const [lastCrashAt, setLastCrashAt] = useState(null);

    const tone = useMemo(()=>statusTone(vm), [vm]);

    useEffect(()=>{
      const frame = document.getElementById('vmframe');
      if(frame) frame.style.display = vm && vm.running ? 'block' : 'none';
      if(vm && vm.running && vmurl && frame && frame.src !== vmurl){
        frame.src = vmurl;
      }
      if(vm && vm.running){
        if(phase !== 'sent') setPhase('idle');
        setErrorMsg('');
      }
    }, [vm && vm.running, vmurl]);

    useEffect(()=>{
      if(vm && vm.crashed){
        setLastCrashAt(Date.now());
        if(phase !== 'recovering' && phase !== 'starting'){
          attemptRecover('The VM crashed while loading or in use.', true);
        }
      }
    }, [vm && vm.crashed]);

    async function waitForUp(timeoutMs){
      const started = Date.now();
      while(Date.now() - started < timeoutMs){
        const status = await window.api.getVMStatus(vmname);
        if(status && status.running){
          const frame = document.getElementById('vmframe');
          if(frame){
            frame.src = vmurl || frame.src;
            frame.style.display = 'block';
          }
          setPhase('idle');
          return { ok:true, status };
        }
        await new Promise(r=>setTimeout(r, 1500));
      }
      return { ok:false, error:`${vmname} did not come online before the timeout.` };
    }

    async function attemptStart(){
      setPhase('starting');
      setErrorMsg('');
      setDetails('');
      try{
        const res = await window.api.startVM(vmname);
        if(!res.ok && !(res.body && /already running/i.test(res.body.error || ''))){
          throw new Error((res.body && (res.body.error || res.body.message)) || `HTTP ${res.status}`);
        }
        const waited = await waitForUp(90000);
        if(!waited.ok){
          setPhase('error');
          setErrorMsg(waited.error || 'Startup timed out.');
          return;
        }
      }catch(e){
        setPhase('error');
        setErrorMsg(String(e));
      }
    }

    async function attemptRecover(reason, autoTriggered){
      setPhase('recovering');
      setErrorMsg('');
      setDetails('');
      try{
        const res = await window.api.recoverVM(vmname, { aggressive:true, reason });
        const body = res.body || {};
        const attempts = Array.isArray(body.attempts) ? body.attempts : [];
        setDetails(attempts.map(a => `${a.action}: ${a.ok ? 'ok' : (a.stderr || 'failed')}`).join('\n'));
        if(!res.ok || !body.recovered){
          setPhase('error');
          setErrorMsg(autoTriggered ? 'The VM crashed and automatic recovery failed.' : (body.message || 'Recovery failed.'));
          return;
        }
        const waited = await waitForUp(90000);
        if(!waited.ok){
          setPhase('error');
          setErrorMsg('The VM was told to recover, but it still never came back online.');
        }
      }catch(e){
        setPhase('error');
        setErrorMsg(String(e));
      }
    }

    async function sendToOpenClaw(){
      setPhase('sent');
      setDetails('');
      try{
        const res = await window.api.escalateVM(vmname, {
          reason: errorMsg || 'User requested OpenClaw recovery help from VM fallback screen.',
          vmStatus: vm,
          lastCrashAt
        });
        if(!res.ok){
          throw new Error((res.body && res.body.error) || `HTTP ${res.status}`);
        }
        const esc = res.body && res.body.escalation ? res.body.escalation : {};
        const rec = res.body && res.body.recovery ? res.body.recovery : {};
        setDetails([
          esc.path ? `Saved escalation: ${esc.path}` : null,
          esc.queued ? 'Sent to OpenClaw successfully.' : (esc.cliError ? `OpenClaw handoff issue: ${esc.cliError}` : 'Saved locally for OpenClaw review.'),
          rec && rec.message ? `Recovery: ${rec.message}` : null
        ].filter(Boolean).join('\n'));
      }catch(e){
        setPhase('error');
        setErrorMsg(`Failed to contact OpenClaw: ${String(e)}`);
      }
    }

    const title = humanState(vm);
    const subtitle = vm && vm.crashed
      ? 'I tried to bring it back automatically. If that failed, you can escalate it to OpenClaw below.'
      : 'You can power it on here and I’ll switch you over once it is actually alive.';

    return (
      React.createElement('div', { className:`fallback tone-${tone}`, role:'status' },
        React.createElement('div', { className:'shell' },
          React.createElement('div', { className:'status-pill' }, vm && vm.crashed ? 'Crash detected' : (vm && vm.running ? 'Live' : 'Offline')),
          React.createElement('div', { className:'card hero-card' },
            React.createElement('div', { className:'orb orb-a' }),
            React.createElement('div', { className:'orb orb-b' }),
            React.createElement('div', { className:'hero-content' },
              React.createElement('div', { className:'vm-name' }, vmname),
              React.createElement('h1', { className:'hero-title' }, title),
              React.createElement('p', { className:'hero-subtitle' }, subtitle),
              React.createElement('div', { className:'meta-row' },
                React.createElement('div', { className:'meta-chip' }, `State: ${(vm && (vm.state || vm.status)) || 'checking'}`),
                React.createElement('div', { className:'meta-chip' }, `Exit: ${vm && vm.exitCode != null ? vm.exitCode : '—'}`),
                React.createElement('div', { className:'meta-chip' }, `Health: ${vm && vm.healthy ? 'healthy' : 'unknown'}`)
              ),
              (phase === 'starting' || phase === 'recovering') && React.createElement('div', { className:'loading-wrap' },
                React.createElement('div', { className:'spinner', 'aria-hidden': true }),
                React.createElement('div', { className:'loading-title' }, phase === 'starting' ? 'Powering on VM…' : 'Recovering crashed VM…'),
                React.createElement('div', { className:'loading-subtitle' }, 'Waiting for a real healthy response before switching you over.')
              ),
              phase !== 'starting' && phase !== 'recovering' && React.createElement('div', { className:'actions' },
                React.createElement('button', { className:'btn btn-primary', onClick: attemptStart }, 'Turn on VM'),
                React.createElement('button', { className:'btn btn-secondary', onClick: ()=>attemptRecover('Manual recovery requested from dashboard', false) }, 'Try recovery'),
                React.createElement('button', { className:'btn btn-ghost', onClick: ()=>window.location.reload() }, 'Refresh')
              ),
              errorMsg && React.createElement('div', { className:'error-box' },
                React.createElement('div', { className:'error-title' }, vm && vm.crashed ? 'The VM crashed and recovery failed.' : 'An error occurred while starting the VM.'),
                React.createElement('div', { className:'error-message' }, errorMsg),
                React.createElement('div', { className:'actions subactions' },
                  React.createElement('button', { className:'btn btn-primary', onClick: ()=>attemptRecover(errorMsg || 'Retry requested after error', false) }, 'Try again'),
                  React.createElement('button', { className:'btn btn-danger', onClick: sendToOpenClaw }, 'Send error to OpenClaw'),
                  React.createElement('button', { className:'btn btn-secondary', onClick: ()=>window.location.reload() }, 'Reload page')
                )
              ),
              phase === 'sent' && React.createElement('div', { className:'sent-box' },
                React.createElement('strong', null, 'OpenClaw escalation requested.'),
                React.createElement('div', { style:{marginTop:8} }, 'I sent the diagnostics and also tried to recover the VM again.')
              ),
              details && React.createElement('pre', { className:'details-box' }, details)
            )
          )
        )
      )
    );
  }

  window.VMFallback = VMFallback;
})();

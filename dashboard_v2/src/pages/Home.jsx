import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cpu, Memory, HardDrives, Network, Plus, ArrowRight, PlayCircle, CheckCircle, Warning, UserCircle, StopCircle, DotsThreeVertical } from '@phosphor-icons/react'
import { SiUbuntu, SiDebian, SiRockylinux } from 'react-icons/si'
import apiFetch from '../lib/fetchWrapper'
import Button from '../components/Button'

const fallbackVMs = [
  {name:'web-01', status:'running', os:'Ubuntu 22.04 LTS', ip:'192.168.122.101', cpu:18, memory:21, disk:35, uptime:'7d 2h 14m'},
  {name:'db-01', status:'running', os:'Debian 12', ip:'192.168.122.102', cpu:32, memory:34, disk:52, uptime:'12d 5h 8m'},
  {name:'backup-01', status:'stopped', os:'Rocky Linux 9.4', ip:'192.168.122.103', cpu:0, memory:0, disk:0, uptime:'Stopped 2d ago'}
]

function Metric({icon:Icon,label,value,detail,tone='ok'}){
  return <div className="host-metric"><div className="metric-label"><Icon size={21}/><span>{label}</span></div><strong>{value}</strong><div className="metric-track"><i style={{width:`${Math.min(Number.parseFloat(value)||0,100)}%`}}/></div><div className="metric-foot"><span>{detail}</span><em className={`tone-${tone}`}>{tone === 'ok' ? 'Healthy' : 'Attention'}</em></div></div>
}

function VmRow({vm}){
  const running = String(vm.status||vm.state||'').toLowerCase().includes('run')
  const cpu = Math.round(vm.cpu_percent ?? vm.cpu ?? 0); const mem = Math.round(vm.mem_percent ?? vm.memory_percent ?? vm.memory ?? 0); const disk = Math.round(vm.disk_percent ?? vm.disk ?? 0)
  const osText=String(vm.os||vm.image||'').toLowerCase(); const OsIcon=osText.includes('debian')?SiDebian:osText.includes('rocky')?SiRockylinux:SiUbuntu
  return <div className="fleet-row"><div className="vm-identity"><span className={`os-mark ${osText.includes('debian')?'debian':osText.includes('rocky')?'rocky':'ubuntu'}`}><OsIcon aria-hidden="true"/></span><div><strong>{vm.name}</strong><span>{vm.os || vm.image || 'Linux VM'}</span><code>{vm.ip || vm.address || 'Address pending'}</code></div></div><div className={`status-text ${running?'live':'down'}`}><i/>{running?'Running':'Stopped'}<small>{vm.uptime || (running?'Active now':'Offline')}</small></div>{[['CPU',cpu],['RAM',mem],['Disk',disk]].map(([label,val])=><div className="row-stat" key={label}><span>{label}</span><strong>{val}%</strong><div><i style={{width:`${val}%`}}/></div></div>)}<button className="row-menu" aria-label={`Actions for ${vm.name}`}><DotsThreeVertical size={20}/></button></div>
}

export default function Home(){
  const [stats,setStats] = useState(null); const [vms,setVms] = useState(fallbackVMs); const navigate = useNavigate()
  useEffect(()=>{ let live=true; Promise.all([apiFetch('/stats').then(r=>r.json()),apiFetch('/list').then(r=>r.json())]).then(([s,l])=>{if(!live)return;setStats(s);if(l?.instances?.length)setVms(l.instances.slice(0,3))}).catch(()=>{});return()=>{live=false}},[])
  const cpu=Math.round(stats?.cpu?.usage ?? 23), mem=Math.round(stats?.memory?.percent ?? 41), storage=Math.round(stats?.disk?.percent ?? 62)
  return <div className="home-page">
    <header className="page-header hero-header"><div><h1>Host Overview</h1><p>blobevm-host-01 <b>•</b> Ubuntu 22.04.4 LTS <b>•</b> Kernel 6.8.0-31-generic <b>•</b> Uptime 18d 4h 32m</p></div><Button onClick={()=>navigate('/vm')}><Plus size={19}/>Create VM</Button></header>
    <section className="host-health" aria-label="Host health"><Metric icon={Cpu} label="CPU" value={`${cpu}%`} detail="8 of 16 vCPUs"/><Metric icon={Memory} label="Memory" value={`${mem}%`} detail="12.9 GB of 31.4 GB"/><Metric icon={HardDrives} label="Storage" value={`${storage}%`} detail="512.7 GB of 825 GB" tone={storage>60?'warn':'ok'}/><Metric icon={Network} label="Network" value="1.2 Gbps" detail="842 Mbps inbound"/></section>
    <div className="overview-grid"><section className="fleet-section"><div className="section-heading"><h2>Virtual Machines <span>{vms.length}</span></h2><button onClick={()=>navigate('/vm')}>View all VMs <ArrowRight size={17}/></button></div><div className="fleet-list">{vms.map(vm=><VmRow vm={vm} key={vm.name}/>)}</div><div className="host-summary"><h2>Host Summary</h2><div><span>Hypervisor <strong>KVM</strong></span><span>Total VMs <strong>{vms.length}</strong></span><span>Virtualization <strong>QEMU 8.2.1</strong></span><span>Running VMs <strong>{vms.filter(v=>String(v.status||v.state).toLowerCase().includes('run')).length}</strong></span></div></div></section>
      <aside className="activity-section"><div className="section-heading"><h2>Recent System Activity</h2><button onClick={()=>navigate('/logs')}>View all logs <ArrowRight size={17}/></button></div><div className="activity-list">{[[PlayCircle,'VM web-01 started','Started by admin','10:24 AM','ok'],[Warning,"Storage pool 'default' usage above 60%",'512.7 GB of 825 GB used','10:10 AM','info'],[CheckCircle,'Optimizer completed','Memory defragmentation','09:58 AM','ok'],[Warning,'High memory usage detected','Host memory at 41%','09:41 AM','warn'],[UserCircle,"User 'deploy' logged in",'SSH from 192.168.1.45','09:32 AM','info'],[StopCircle,'VM backup-01 stopped','Stopped by admin','08:15 AM','danger']].map(([Icon,title,detail,time,tone])=><div className={`activity-item tone-${tone}`} key={title}><Icon size={23}/><div><strong>{title}</strong><span>{detail}</span></div><time>{time}</time></div>)}</div></aside></div>
  </div>
}

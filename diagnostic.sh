#!/bin/bash

echo "=== BlobeVM Connection Refused Diagnostic ==="
echo "Run this on your server and share the output"
echo

echo "1. System Info:"
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo "Docker version: $(docker --version 2>/dev/null || echo 'Docker not found')"
echo "Docker running: $(systemctl is-active docker 2>/dev/null || echo 'systemctl not available')"
echo

echo "2. Environment Variables:"
echo "NO_TRAEFIK: ${NO_TRAEFIK:-not set}"
echo "BLOBEVM_DOMAIN: ${BLOBEVM_DOMAIN:-not set}"
echo "BLOBEVM_DIRECT_PORT_START: ${BLOBEVM_DIRECT_PORT_START:-not set}"
echo

echo "3. VM Manager Status:"
if command -v blobe-vm-manager &> /dev/null; then
    echo "blobe-vm-manager found at: $(which blobe-vm-manager)"
    echo "VM List:"
    blobe-vm-manager list 2>&1 || echo "Failed to list VMs"
else
    echo "blobe-vm-manager not found in PATH"
fi
echo

echo "4. Docker Containers:"
echo "All containers:"
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not accessible"
echo
echo "BlobeVM containers:"
docker ps -a --filter "name=blobevm_" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "No BlobeVM containers or Docker not accessible"
echo

echo "5. Network Configuration:"
echo "Docker networks:"
docker network ls 2>/dev/null || echo "Docker not accessible"
echo
echo "Proxy network inspect:"
docker network inspect proxy 2>/dev/null || echo "Proxy network not found"
echo

echo "6. Traefik Status (if applicable):"
if docker ps | grep -q traefik; then
    echo "Traefik is running"
    docker ps --filter "name=traefik" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo "Traefik logs (last 10 lines):"
    docker logs --tail 10 traefik 2>/dev/null || echo "Could not get Traefik logs"
else
    echo "Traefik is not running"
fi
echo

echo "7. Firewall Status:"
echo "UFW status:"
ufw status 2>/dev/null || echo "UFW not available"
echo
echo "iptables rules (filtered):"
iptables -L -n | grep -E "(3000|tcp|ACCEPT|DROP)" | head -20 2>/dev/null || echo "iptables not accessible"
echo

echo "8. VM Container Logs (if any running):"
for container in $(docker ps -q --filter "name=blobevm_" 2>/dev/null); do
    name=$(docker inspect --format '{{.Name}}' $container 2>/dev/null | sed 's|/blobevm_||')
    echo "Logs for VM: $name (last 20 lines)"
    docker logs --tail 20 $container 2>&1 | tail -20
    echo "---"
done

echo "9. Port Testing (if VMs are running):"
for container in $(docker ps -q --filter "name=blobevm_" 2>/dev/null); do
    name=$(docker inspect --format '{{.Name}}' $container 2>/dev/null | sed 's|/blobevm_||')
    port=$(docker port $container 3000/tcp 2>/dev/null | cut -d: -f2)
    if [ -n "$port" ]; then
        echo "VM $name published on port $port"
        echo "Testing connection to localhost:$port"
        timeout 5 bash -c "</dev/tcp/localhost/$port" && echo "Port $port is open" || echo "Port $port is closed/refused"
        echo "Curl test:"
        curl -s --connect-timeout 5 --max-time 10 http://localhost:$port/ | head -5 2>/dev/null || echo "Curl failed"
    else
        echo "VM $name has no port 3000 published"
    fi
    echo "---"
done

echo "10. Recent Docker Events:"
docker events --since "1 hour ago" --filter "container=blobevm_" 2>/dev/null | head -20 || echo "No recent events or Docker not accessible"

echo
echo "=== End Diagnostic ==="
echo "Copy and paste this entire output when asking for help!"
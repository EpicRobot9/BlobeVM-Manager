#!/bin/bash

echo "=== BlobeVM Diagnostic Script ==="
echo

# Check if blobe-vm-manager exists
if ! command -v blobe-vm-manager &> /dev/null; then
    echo "ERROR: blobe-vm-manager not found in PATH"
    echo "Make sure it's installed and in /usr/local/bin or similar"
    exit 1
fi

echo "1. Checking environment variables:"
echo "NO_TRAEFIK: ${NO_TRAEFIK:-not set}"
echo "BLOBEVM_DOMAIN: ${BLOBEVM_DOMAIN:-not set}"
echo

echo "2. Checking if Traefik is running:"
if docker ps | grep -q traefik; then
    echo "Traefik is running"
else
    echo "Traefik is NOT running"
fi
echo

echo "3. Listing VM containers:"
docker ps -a --filter "name=blobevm_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo

echo "4. Checking proxy network:"
docker network ls | grep proxy
echo

echo "5. For each running VM, checking logs (last 20 lines):"
for container in $(docker ps -q --filter "name=blobevm_"); do
    name=$(docker inspect --format '{{.Name}}' $container | sed 's|/blobevm_||')
    echo "Logs for VM: $name"
    docker logs --tail 20 $container 2>&1 | head -20
    echo "---"
done

echo "6. Testing VM URLs (if in direct mode):"
if [ "${NO_TRAEFIK:-1}" = "1" ]; then
    echo "Direct mode detected"
    for container in $(docker ps -q --filter "name=blobevm_"); do
        name=$(docker inspect --format '{{.Name}}' $container | sed 's|/blobevm_||')
        port=$(docker port $container 3000/tcp | cut -d: -f2)
        if [ -n "$port" ]; then
            echo "VM $name should be at http://localhost:$port/"
            # Try to connect
            if curl -s --connect-timeout 5 http://localhost:$port/ > /dev/null; then
                echo "  Connection OK"
            else
                echo "  Connection FAILED"
            fi
        else
            echo "VM $name has no port published"
        fi
    done
else
    echo "Merged mode (Traefik)"
    echo "Check manager URLs:"
    for vm in $(blobe-vm-manager list | grep -oP '(?<= - )\w+'); do
        url=$(blobe-vm-manager url $vm 2>/dev/null)
        if [ -n "$url" ]; then
            echo "VM $vm URL: $url"
            if curl -s --connect-timeout 5 "$url" > /dev/null; then
                echo "  Connection OK"
            else
                echo "  Connection FAILED"
            fi
        fi
    done
fi

echo
echo "=== End Diagnostic ==="
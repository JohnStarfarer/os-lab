#!/bin/bash

echo "Kernel: $(uname -s) $(uname -r)"
lsb_distro=$(lsb_release -ds | tr -d "\"";)
lsb_ver=$(lsb_release -rs | tr -d "\"";)
echo "Distribution: $lsb_distro $lsb_ver"

ram_t=$(($(cat /proc/meminfo | grep MemTotal | awk '{print $2}')/1024))
ram_f=$(($(cat /proc/meminfo | grep MemFree | awk '{print $2}')/1024))
echo "RAM: $ram_f MB free / $ram_t MB total"

echo "Processors: $(nproc)"

echo "Architecture: $(uname -m)"

echo "Load average: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"

echo "Logic Discs:"
echo "$(cat /proc/mounts | grep '^/' | awk '{print "  ",$1, $2}')"
echo "Statistic:"
echo "$(df | head -n 1)"
echo "$(df | grep '^/')"

echo "User: $(logname)"
echo "Hostname: $(uname -n)"

vram_t=$(($(cat /proc/meminfo | grep VmallocTotal | awk '{print $2}')/1024))
vram_u=$(($(cat /proc/meminfo | grep VmallocUsed | awk '{print $2}')/1024))
vram_f=$(($vram_t - $vram_u))
echo "VRAM: $vram_f MB free / $vram_u MB used / $vram_t MB total"
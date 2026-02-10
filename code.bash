
sudo groupadd developers

sudo useradd -m -s /bin/bash alice
sudo useradd -m -s /bin/bash bob
sudo useradd -m -s /bin/bash eve

sudo passwd alice
sudo passwd bob
sudo passwd eve

sudo usermod -aG developers alice
sudo usermod -aG developers bob

id alice
id bob
id eve

sudo usermod -aG wheel alice

sudo EDITOR=nano visudo

mkdir ~/project

mkdir ~/project/src ~/project/logs ~/project/public ~/project/tmp

sudo chown alice:developers ~/project

sudo chmod 775 ~/project/src
sudo chmod 770 ~/project/logs
sudo chmod 775 ~/project/public
sudo chmod 1777 ~/project/tmp

echo "HardLink Text" > project/src/htl.txt
ln project/src/htl.txt project/src/htl_hardlink.txt

ln -s project/src/htl.txt project/src/htl_symlink.txt
ln -s project/src project/src_link

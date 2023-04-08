#!/usr/bin/python3

import os
import subprocess
from setup import args, distro, distro_name
from shutil import which

# ------------------------------ CORE FUNCTIONS ------------------------------ #

def download_file(url):
    if which("curl"):
        os.system(f"curl -LO {url}") # -JLO
    elif which("wget"):
        os.system(f"wget {url}")

def unarchive(path):
    if which("bsdtar"):
        os.system(f"bsdtar -xf {path}")
    elif which("unzip"):
        os.system(f"unzip {path}")

def refind_ash():
    #download_file("https://sourceforge.net/projects/refind/files/latest/download")
    download_file("https://sourceforge.net/projects/refind/files/0.13.3.1/refind-bin-0.13.3.1.zip/download")
    unarchive("download")
    os.system("cd refind*")
    subprocess.run(['refind-install', os_root])
    os.system("mkdir -p /mnt/boot/efi/EFI/refind/drivers_x64")
    os.system("cp refind/drivers_x64/btrfs_x64.efi /mnt/boot/efi/EFI/refind/drivers_x64/")

def lvm_choice():
    clear()
    while True:
        print("LVM (y/n)?")
        reply = input("> ")
        if reply.casefold() == "y":

            ### NEWLY ADDED
          # Set partition type GUID
            part_type = subprocess.check_output(f'sudo parted {args[2]} p | grep "Partition Table:"', encoding='utf-8', shell=True).strip().split(": ")[1]
            part_number = int(args[1].split(args[2])[1]) # /dev/sda2 - /dev/sda
            if part_type == 'gpt':
                os.system(f"sudo sgdisk --typecode={part_number}:8e00 {args[2]}")
            elif part_type == 'msdos':
                os.system(f"sudo sfdisk --part-type {args[2]} {part_number} 8e")
            
          # LVM on LUKS?
            os.system(f"pvcreate {os_root}") ### REVIEW PREVIOUSLY: args[1]
            os.system(f"vgcreate vg_{distro} {os_root}") ### REVIEW PREVIOUSLY: args[1]
            os.system(f"lvcreate -l +100%FREE vg_{distro} --name lv")
            os_root = f"/dev/mapper/vg{distro}-lv"
            return True
            break
        elif reply.casefold() == "n":
            return False
            break

def choose_filesystem():
    clear()
    while True:
        #print("Please choose file system for target OS:\n1. BTRFS\n2. Ext4\n3. ZFS")
        print("Please choose file system for target OS:\n1. Ext4\n2. XFS\n")
        i = input("> ")
        if i == "1":
            return "ext4"
            break
        elif i == "2":
            return "xfs"
            break
        else:
            print("Invalid choice!")
            continue

#   Mount-points needed for chrooting
def ash_chroot():
    os.system("sudo mount -o x-mount.mkdir --rbind --make-rslave /dev /mnt/dev")
    os.system("sudo mount -o x-mount.mkdir --types proc /proc /mnt/proc")
    os.system("sudo mount -o x-mount.mkdir --bind --make-slave /run /mnt/run")
    os.system("sudo mount -o x-mount.mkdir --rbind --make-rslave /sys /mnt/sys")
    if is_efi:
        os.system("sudo mount -o x-mount.mkdir --rbind --make-rslave /sys/firmware/efi/efivars /mnt/sys/firmware/efi/efivars")
    os.system("sudo cp --dereference /etc/resolv.conf /mnt/etc/") # --remove-destination ### not writing through dangling symlink! (TODO: try except)

#   Clear screen
def clear():
    os.system("#clear")

#   Users
def create_user(u, g):
    os.system(f"sudo chroot /mnt sudo useradd -m -G {g} -s /bin/bash {u}")
    os.system(f"echo '%{g} ALL=(ALL:ALL) ALL' | sudo tee -a /mnt/etc/sudoers")
    os.system(f"echo 'export XDG_RUNTIME_DIR=\"/run/user/1000\"' | sudo tee -a /mnt/home/{u}/.bashrc") ### ToDo bashism

#   BTRFS snapshots
def deploy_base_snapshot():
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system("sudo btrfs sub snap -r /mnt /mnt/.snapshots/rootfs/snapshot-0")
        os.system("sudo btrfs sub create /mnt/.snapshots/boot/boot-deploy")
        os.system("sudo btrfs sub create /mnt/.snapshots/etc/etc-deploy")
    os.system("sudo cp -r --reflink=auto /mnt/boot/. /mnt/.snapshots/boot/boot-deploy")
    os.system("sudo cp -r --reflink=auto /mnt/etc/. /mnt/.snapshots/etc/etc-deploy")
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system("sudo btrfs sub snap -r /mnt/.snapshots/boot/boot-deploy /mnt/.snapshots/boot/boot-0")
        os.system("sudo btrfs sub snap -r /mnt/.snapshots/etc/etc-deploy /mnt/.snapshots/etc/etc-0")
        os.system("sudo btrfs sub snap /mnt/.snapshots/rootfs/snapshot-0 /mnt/.snapshots/rootfs/snapshot-deploy")
        os.system("sudo chroot /mnt sudo btrfs sub set-default /.snapshots/rootfs/snapshot-deploy")
    os.system("sudo cp -r /mnt/root/. /mnt/.snapshots/root/")
    os.system("sudo cp -r /mnt/tmp/. /mnt/.snapshots/tmp/")
    os.system("sudo rm -rf /mnt/root/*")
    os.system("sudo rm -rf /mnt/tmp/*")

#   Copy boot and etc: deployed snapshot <---> common
def deploy_to_common():
    if is_efi:
        os.system("sudo umount /mnt/boot/efi")
    os.system("sudo umount /mnt/boot")
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system(f"sudo mount {os_root} -o subvol=@boot{distro_suffix},compress=zstd,noatime /mnt/.snapshots/boot/boot-deploy")
    os.system("sudo cp -r --reflink=auto /mnt/.snapshots/boot/boot-deploy/. /mnt/boot/")
    os.system("sudo umount /mnt/etc")
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system(f"sudo mount {os_root} -o subvol=@etc{distro_suffix},compress=zstd,noatime /mnt/.snapshots/etc/etc-deploy")
    os.system("sudo cp -r --reflink=auto /mnt/.snapshots/etc/etc-deploy/. /mnt/etc/")
    os.system("sudo cp -r --reflink=auto /mnt/.snapshots/boot/boot-0/. /mnt/.snapshots/rootfs/snapshot-deploy/boot/")
    os.system("sudo cp -r --reflink=auto /mnt/.snapshots/etc/etc-0/. /mnt/.snapshots/rootfs/snapshot-deploy/etc/")

def get_hostname():
    clear()
    while True:
        print("Enter hostname:")
        h = input("> ")
        if h:
            print("Happy with your hostname? (y/n)")
            reply = input("> ")
            if reply.casefold() == "y":
                break
            else:
                continue
    return h

#   This function returns a tuple: (1. choice whether partitioning and formatting should happen
#   2. Underscore plus name of distro if it should be appended to sub-volume names
def get_multiboot(dist):
    clear()
    while True:
        print("Please choose one of the following options:\n1. Initiate a new AshOS install (wipes root partition)\n2. Add to an already installed AshOS.")
        i = input("> ")
        if i in ("1", "2"):
            return i, f"_{dist}"
            break
        else:
            print("Invalid choice!")
            continue

def get_timezone():
    clear()
    while True:
        print("Select a timezone (type list to list):")
        zone = input("> ")
        if zone == "list":
            zoneinfo_path = '/usr/share/zoneinfo'
            zones = []
            for root, _dirs, files in os.walk(zoneinfo_path, followlinks=True):
                for file in files:
                    zones.append(os.path.join(root, file).replace(f"{zoneinfo_path}/", ""))
            zones = "\n".join(sorted(zones))
            os.system(f"echo '{zones}' | less")
        else:
            timezone = str(f"/usr/share/zoneinfo/{zone}")
            if not os.path.isfile(timezone):
                print("Invalid timezone!")
                continue
            break

def get_username():
    clear()
    while True:
        print("Enter username (all lowercase):")
        u = input("> ")
        if u:
            print("Happy with your username? (y/n)")
            reply = input("> ")
            if reply.casefold() == "y":
                break
            else:
                continue
    return u

#   GRUB and EFI
def grub_ash(v):
    os.system(f"sudo sed -i 's/^GRUB_DISTRIBUTOR.*$/GRUB_DISTRIBUTOR=\"{distro_name}\"/' /mnt/etc/default/grub")
    if is_luks:
        os.system("sudo sed -i 's/^#GRUB_ENABLE_CRYPTODISK.*$/GRUB_ENABLE_CRYPTODISK=y/' /mnt/etc/default/grub")
        os.system(f"sudo sed -i -E 's|^#?GRUB_CMDLINE_LINUX=\"|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID={to_uuid(os_root)}:luks_root cryptkey=rootfs:/etc/crypto_keyfile.bin|' /mnt/etc/default/grub")
        os.system(f"sed -e 's|DISTRO|{distro}|' -e 's|LUKS_UUID_NODASH|{to_uuid(os_root).replace('-', '')}|' \
                        -e '/^#/d' ./src/prep/grub_luks2.conf | sudo tee /mnt/etc/grub_luks2.conf")
  # grub-install rewrites default core.img, so run grub-mkimage AFTER!
    if distro != "fedora": # https://bugzilla.redhat.com/show_bug.cgi?id=1917213
        if is_efi:
            os.system(f'sudo chroot /mnt sudo grub{v}-install {args[2]} --bootloader-id={distro} --modules="{luks_grub_args}" --target=x86_64-efi') # --efi-directory=/boot/efi
        else:
            os.system(f'sudo chroot /mnt sudo grub{v}-install {args[2]} --bootloader-id={distro} --modules="{luks_grub_args}"') ### REVIEW: specifying --target for non-uefi needed?
    if is_luks: # Make LUKS2 compatible grub image
        if is_efi:
            os.system(f'sudo chroot /mnt sudo grub{v}-mkimage -p "(crypto0)/@boot_{distro}/grub{v}" -O x86_64-efi -c /etc/grub_luks2.conf -o /boot/efi/EFI/{distro}/grubx64.efi {luks_grub_args}') # without '/grub' gives error normal.mod not found (maybe only one of these here and grub_luks2.conf is enough?!)
        else:
            os.system(f'sudo chroot /mnt sudo grub{v}-mkimage -p "(crypto0)/@boot_{distro}/grub{v}" -O i386-pc -c /etc/grub_luks2.conf -o /boot/grub{v}/i386-pc/core_luks2.img {luks_grub_args}') # without '/grub' gives error normal.mod not found (maybe only one of these here and grub_luks2.conf is enough?!) ### 'biosdisk' module not needed eh?
            os.system(f'dd oflag=seek_bytes seek=512 if=/mnt/boot/grub{v}/i386-pc/core_luks2.img of={args[2]}')
    os.system(f"sudo chroot /mnt sudo grub{v}-mkconfig {args[2]} -o /boot/grub{v}/grub.cfg")
    os.system(f"sudo mkdir -p /mnt/boot/grub{v}/BAK") # Folder for backing up grub configs created by ashpk
    os.system(f"sudo sed -i 's|subvol=@{distro_suffix}|subvol=@.snapshots{distro_suffix}/rootfs/snapshot-deploy|g' /mnt/boot/grub{v}/grub.cfg")
    # Create a mapping of "distro" <=> "BootOrder number". Ash reads from this file to switch between distros.
    if is_efi:
        if not os.path.exists("/mnt/boot/efi/EFI/map.txt"):
            os.system("echo DISTRO,BootOrder | sudo tee /mnt/boot/efi/EFI/map.txt")
        os.system(f"echo '{distro},'$(efibootmgr -v | grep -i {distro} | awk '"'{print $1}'"' | sed '"'s|[^0-9]*||g'"') | sudo tee -a /mnt/boot/efi/EFI/map.txt")

def download_file(url):
    if which("curl"):
        os.system(f"curl -LO {url}") # -JLO
    elif which("wget"):
        os.system(f"wget {url}")

def unarchive(path):
    if which("bsdtar"):
        os.system(f"bsdtar -xf {path}")
    elif which("unzip"):
        os.system(f"unzip {path}")

def refind_ash():
    #download_file("https://sourceforge.net/projects/refind/files/latest/download")
    download_file("https://sourceforge.net/projects/refind/files/0.13.3.1/refind-bin-0.13.3.1.zip/download")
    unarchive("download")
    os.system("cd refind*")
    subprocess.run(['refind-install', os_root])
    os.system("mkdir -p /mnt/boot/efi/EFI/refind/drivers_x64")
    os.system("cp refind/drivers_x64/btrfs_x64.efi /mnt/boot/efi/EFI/refind/drivers_x64/")

def check_efi():
    return os.path.exists("/sys/firmware/efi")

#   Post bootstrap
def post_bootstrap(super_group):
  # Database and config files
    os.system("sudo chmod 700 /mnt/.snapshots/ash/root")
    os.system("sudo chmod 1777 /mnt/.snapshots/ash/tmp")
###    os.system("sudo ln -srf /mnt/.snapshots/ash/root /mnt/root")
###    os.system("sudo ln -srf /mnt/.snapshots/ash/tmp /mnt/tmp")
    os.system("echo '0' | sudo tee /mnt/usr/share/ash/snap")
    os.system("echo 'mutable_dirs::' | sudo tee /mnt/etc/ash.conf")
    os.system("echo 'mutable_dirs_shared::' | sudo tee -a /mnt/etc/ash.conf")
    if distro in ("arch", "cachyos", "endeavouros"):
        os.system("echo 'aur::False' | sudo tee -a /mnt/etc/ash.conf")
  # Update fstab
    #if fs == "btrfs": ###
    if not is_lvm:
        for mntdir in mntdirs:
            os.system(f"echo 'UUID=\"{to_uuid(os_root)}\" /{mntdir} btrfs subvol=@{mntdir}{distro_suffix},compress=zstd,noatime{'' if mntdir else ',ro'} 0 0' | sudo tee -a /mnt/etc/fstab") # ro only for / entry ### complex but one-liner
    else:
        if fs == "ext4":
            print("### TODO")
        elif fs == "xfs":
            print("### TODO")
    if is_efi:
        os.system(f"echo 'UUID=\"{to_uuid(args[3])}\" /boot/efi vfat umask=0077 0 2' | sudo tee -a /mnt/etc/fstab")
    os.system("echo '/.snapshots/ash/root /root none bind 0 0' | sudo tee -a /mnt/etc/fstab")
    os.system("echo '/.snapshots/ash/tmp /tmp none bind 0 0' | sudo tee -a /mnt/etc/fstab")
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system(f"sudo sed -i '0,/@{distro_suffix}/ s|@{distro_suffix}|@.snapshots{distro_suffix}/rootfs/snapshot-deploy|' /mnt/etc/fstab")
        os.system(f"sudo sed -i '0,/@boot{distro_suffix}/ s|@boot{distro_suffix}|@.snapshots{distro_suffix}/boot/boot-deploy|' /mnt/etc/fstab")
        os.system(f"sudo sed -i '0,/@etc{distro_suffix}/ s|@etc{distro_suffix}|@.snapshots{distro_suffix}/etc/etc-deploy|' /mnt/etc/fstab")
  # Copy common ash files and create symlinks
    os.system("sudo mkdir -p /mnt/.snapshots/ash/snapshots")
    os.system(f"echo '{to_uuid(os_root)}' | sudo tee /mnt/.snapshots/ash/part")
    os.system(f"sudo cat ./src/ashpk_core.py ./src/distros/{distro}/ashpk.py > /mnt/.snapshots/ash/ash")
    os.system("sudo chmod +x /mnt/.snapshots/ash/ash")
    os.system("sudo cp -a ./src/detect_os.sh /mnt/.snapshots/ash/detect_os.sh")
    os.system("sudo ln -srf /mnt/.snapshots/ash/ash /mnt/usr/bin/ash")
    os.system("sudo ln -srf /mnt/.snapshots/ash/detect_os.sh /mnt/usr/bin/detect_os.sh")
    os.system("sudo ln -srf /mnt/.snapshots/ash /mnt/var/lib/ash")
    os.system("echo {\\'name\\': \\'root\\', \\'children\\': [{\\'name\\': \\'0\\'}]} | sudo tee /mnt/.snapshots/ash/fstree") # Initialize fstree
  # Create user and set password
    set_password("root")
    username = get_username()
    create_user(username, super_group)
    set_password(username)
  # Modify OS release information (optional)
    os.system(f"sudo sed -i 's|^ID.*$|ID={distro}_ashos|' /mnt/etc/os-release")
    os.system(f"sudo sed -i 's|^NAME=.*$|NAME=\"{distro_name}\"|' /mnt/etc/os-release")
    os.system(f"sudo sed -i 's|^PRETTY_NAME=.*$|PRETTY_NAME=\"{distro_name}\"|' /mnt/etc/os-release")

#   Common steps before bootstrapping
def pre_bootstrap():
  # Prep (format partition, etc.)
    if is_luks and choice != "3":
        os.system("sudo modprobe dm-crypt")
        print("--- Create LUKS partition --- ")
        os.system(f"sudo cryptsetup -y -v -c aes-xts-plain64 -s 512 --hash sha512 --pbkdf pbkdf2 --type luks2 luksFormat {os_root}")
        print("--- Open LUKS partition --- ")
        os.system(f"sudo cryptsetup --allow-discards --persistent --type luks2 open {os_root} luks_root")
    #if fs == "btrfs": ###
    if not is_lvm:
        if choice != "3":
            os.system(f"sudo mkfs.btrfs -L LINUX -f {os_root}")
      # Mount and create necessary sub-volumes and directories
        if choice != "3":
            os.system(f"sudo mount -t btrfs {os_root} /mnt")
        else:
            os.system(f"sudo mount -o subvolid=5 {os_root} /mnt")
        for btrdir in btrdirs:
            os.system(f"sudo btrfs sub create /mnt/{btrdir}")
        os.system("sudo umount /mnt")
        for mntdir in mntdirs:
            os.system(f"sudo mkdir -p /mnt/{mntdir}") # -p to ignore /mnt exists complaint
            os.system(f"sudo mount {os_root} -o subvol={btrdirs[mntdirs.index(mntdir)]},compress=zstd,noatime /mnt/{mntdir}")
        for i in ("tmp", "root"):
            os.system(f"mkdir -p /mnt/{i}")
        for i in ("ash", "boot", "etc", "root", "rootfs", "tmp"):
            os.system(f"mkdir -p /mnt/.snapshots/{i}")
      # Create following two because if not, error when booting in some distros
        for i in ("root", "tmp"):
            os.system(f"mkdir -p /mnt/.snapshots/ash/{i}")

    else:
        
        os.system("sudo modprobe dm_mod")
        os.system("sudo vgscan")
        os.system("sudo vgchange -ay")
        
        if fs == "ext4":
            if choice != "3":
                os.system(f"sudo mkfs.ext4 -L LINUX -f {os_root}")
          # Mount and create necessary sub-volumes and directories
            if choice != "3":
                os.system(f"sudo mount {os_root} /mnt") ### -t ext4 ### OR /dev/<volume_group>/<logical_volume> ?
            for btrdir in btrdirs:
                os.system(f"sudo btrfs sub create /mnt/{btrdir}")
            os.system("sudo umount /mnt")
            for mntdir in mntdirs:
                os.system(f"sudo mkdir -p /mnt/{mntdir}") # -p to ignore /mnt exists complaint
                os.system(f"sudo mount {os_root} -o subvol={btrdirs[mntdirs.index(mntdir)]},compress=zstd,noatime /mnt/{mntdir}")
            for i in ("tmp", "root"):
                os.system(f"mkdir -p /mnt/{i}")
            for i in ("ash", "boot", "etc", "root", "rootfs", "tmp"):
                os.system(f"mkdir -p /mnt/.snapshots/{i}")
          # Create following two because if not, error when booting in some distros
            for i in ("root", "tmp"):
                os.system(f"mkdir -p /mnt/.snapshots/ash/{i}")

        elif fs == "zfs":
            print("### TODO")
    os.system("sudo mkdir -p /mnt/usr/share/ash/db") ### REVIEW was in step "Database and config files" before (better to create after bootstrap for aesthetics)
    if is_efi:
        os.system("sudo mkdir -p /mnt/boot/efi")
        os.system(f"sudo mount {args[3]} /mnt/boot/efi")

def set_password(u):
    clear()
    while True:
        print(f"Setting a password for '{u}':")
        os.system(f"sudo chroot /mnt sudo passwd {u}")
        print("Was your password set properly? (y/n)")
        reply = input("> ")
        if reply.casefold() == "y":
            break
        else:
            continue

def to_uuid(part):
    return subprocess.check_output(f"sudo blkid -s UUID -o value {part}", shell=True).decode('utf-8').strip()

#   Unmount everything and finish
def unmounts():
    os.system("sudo umount --recursive /mnt")
    #if fs == "btrfs": ###
    if not is_lvm:
        os.system(f"sudo mount {os_root} -o subvolid=0 /mnt")
        os.system(f"sudo btrfs sub del /mnt/@{distro_suffix}")
    os.system("sudo umount --recursive /mnt")
    if is_luks:
        os.system("sudo cryptsetup close luks_root")

def use_luks():
    clear()
    while True:
        print("Would you like to use LUKS? (y/n)")
        reply = input("> ")
        if reply.casefold() == "y":
            e = True
            break
        elif reply.casefold() == "n":
            e = False
            break
        else:
            continue
    return e

# ---------------------------------------------------------------------------- #

print("Welcome to the AshOS installer!\n")
with open('res/logos/logo.txt', 'r') as f:
    print(f.read())

#   Define variables
DEBUG = "" # options: "", " >/dev/null 2>&1"
choice, distro_suffix = get_multiboot(distro)
is_luks = use_luks()
is_efi = check_efi()
if is_luks:
    os_root = "/dev/mapper/luks_root"
    if is_efi:
        luks_grub_args = f"luks2 {fs} part_gpt cryptodisk pbkdf2 gcry_rijndael gcry_sha512"
    else:
        luks_grub_args = f"luks2 {fs} biosdisk part_msdos cryptodisk pbkdf2 gcry_rijndael gcry_sha512"
else:
    os_root = args[1]
    luks_grub_args = ""
is_lvm = lvm_choice()
#fs = choose_filesystem()
#if fs == "btrfs":
if not is_lvm:
    btrdirs = [f"@{distro_suffix}", f"@.snapshots{distro_suffix}", f"@boot{distro_suffix}", f"@etc{distro_suffix}", f"@home{distro_suffix}", f"@var{distro_suffix}"]
    mntdirs = ["", ".snapshots", "boot", "etc", "home", "var"]
else:
    fs = choose_filesystem()


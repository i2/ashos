#!/usr/bin/env python3

import os
import subprocess as sp
from setup import args, distro
from shutil import copy
from src.installer_core import * # NOQA
#from src.installer_core import is_luks, ashos_mounts, clear, deploy_base_snapshot, deploy_to_common, grub_ash, is_efi, post_bootstrap, pre_bootstrap, unmounts

def main():
    #   1. Define variables
    ARCH = "x86_64"
    KERNEL = "6.1.2-tinycore64"
    TCL_VERSION="14.x"
    packages = f"curl coreutils tzdata tmux python3.9 bash filesystems-{KERNEL} raid-dm-{KERNEL}" # Required for btrfs module being loaded in linux kernel
                #linux-firmware-none networkmanager linux-firmware nano doas os-prober musl-locales musl-locales-lang dbus #### default mount from busybox gives errors. Do I also need umount?!
    if is_efi:
        packages += " efibootmgr grub2-multi"
    else:
        packages += " grub2-multi"
    if is_format_btrfs:
        packages += " btrfs-progs"
    if is_luks:
        packages += " cryptsetup" ### REVIEW_LATER
    super_group = "root"
    v = "2" # GRUB version number in /boot/grubN
    URL=f"http://tinycorelinux.net/{TCL_VERSION}/{ARCH}/release/distribution_files/"

    #   Pre bootstrap
    pre_bootstrap()

    #   2. Bootstrap and install packages in chroot
    os.system(f"{SUDO} rebuildfstab")
    while True:
        try:
            strap(packages, ARCH, URL)
        except sp.CalledProcessError as e:
            print(e)
            if not yes_no("F: Failed to strap package(s). Retry?"):
                unmounts("failed") # user declined
                sys.exit("F: Install failed!")
        else: # success
            break
    ### redundant os.system("sudo cp --dereference /etc/resolv.conf /mnt/etc/") # --remove-destination ### not writing through dangling symlink! (TODO: try except)

    #   Mount-points for chrooting
    ashos_mounts()

    #   3. Package manager database and config files
    os.system("sudo mkdir -p /mnt/usr/share/ash/db/tce")
    os.system("sudo mkdir -p /mnt/usr/share/ash/db/tcloop")
    os.system("sudo ln -sf /mnt/usr/share/ash/db/tce /tmp/tce")
    os.system("sudo ln -sf /mnt/usr/share/ash/db/tcloop /tmp/tcloop")
    os.system("sudo mv /usr/local/tce.installed /mnt/usr/share/ash/db/")
    os.system("sudo ln -sf /mnt/usr/share/ash/db/tce.installed /usr/local/tce.installed")

    #   4. Update hostname, hosts, locales and timezone, hosts
    os.system(f"echo {hostname} | sudo tee /mnt/etc/hostname")
    os.system(f"echo 127.0.0.1 {hostname} {distro} | sudo tee -a /mnt/etc/hosts")
    #os.system("sudo sed -i 's|^#en_US.UTF-8|en_US.UTF-8|g' /mnt/etc/locale.gen")
    #os.system("sudo chroot /mnt sudo locale-gen")
    #os.system("echo 'LANG=en_US.UTF-8' | sudo tee /mnt/etc/locale.conf")
    os.system(f"sudo ln -sf /mnt/usr/share/zoneinfo/{tz} /mnt/etc/localtime")
    ################TODO os.system("sudo chroot /mnt /usr/local/sbin/hwclock --systohc")
    os.system(f"echo {username} | sudo tee -a /mnt/etc/sysconfig/tcuser") # Required for tce-load to work in chroot

    #   Post bootstrap
    os.system("sudo chroot /mnt rebuildfstab")
    post_bootstrap(super_group)

    #   5. Services (init, network, etc.)
    # /etc/init.d/services
    ######os.system("sudo chroot /mnt /bin/bash -c '/sbin/setup-interfaces'")

    #   6. Boot and EFI
    os.system('echo GRUB_CMDLINE_LINUX_DEFAULT=\\"modules=sd-mod,usb-storage,btrfs quiet rootfstype=btrfs\\" | sudo tee -a /mnt/etc/default/grub') # should be before initram create otherwise canonical error in grub-probe
    initram_update()
    grub_ash(v)

    #   BTRFS snapshots
    deploy_base_snapshot()

    #   Copy boot and etc: deployed snapshot <---> common
    deploy_to_common()

    #   Unmount everything and finish
    unmounts()

    clear()
    print("Installation complete!")
    print("You can reboot now :)")

def initram_update():
    if is_luks:
        os.system("sudo dd bs=512 count=4 if=/dev/random of=/mnt/etc/crypto_keyfile.bin iflag=fullblock")
        os.system("sudo chmod 000 /mnt/etc/crypto_keyfile.bin") # Changed from 600 as even root doesn't need access
        os.system(f"sudo cryptsetup luksAddKey {args[1]} /mnt/etc/crypto_keyfile.bin")
        os.system("sudo sed -i -e '/^HOOKS/ s/filesystems/encrypt filesystems/' \
                        -e 's|^FILES=(|FILES=(/etc/crypto_keyfile.bin|' /mnt/etc/mkinitcpio.conf") ### IMPORTANT TODO
    if is_format_btrfs: ### REVIEW TEMPORARY
        os.system("sudo sed -i 's|ext4|ext4 btrfs|' /mnt/etc/mkinitfs/mkinitfs.conf") ### TODO if array not empty, needs to be "btrfs "
    if is_luks or is_format_btrfs: ### REVIEW: does mkinitcpio need to be run without these conditions too?
        try: # work with default kernel modules first
            sp.check_output("sudo chroot /mnt sudo mkinitfs -b / -f /etc/fstab", shell=True) ### REVIEW <kernelvers>
        except sp.CalledProcessError: # and if errors
            kv = os.listdir('/mnt/lib/modules')
            try:
                if len(kv) == 1:
                    sp.check_output(f"sudo chroot /mnt sudo mkinitfs -b / -f /etc/fstab -k {''.join(kv)}", shell=True)
            except:
                print(f"F: Creating initfs with either live default or {kv} kernels failed!")
                print("Next, type just folder name from /mnt/lib/modules i.e. 5.15.104-0-lts")
                while True:
                    try:
                        kv = get_item_from_path("kernel version", "/mnt/lib/modules")
                        sp.check_output(f"sudo chroot /mnt sudo mkinitfs -b / -f /etc/fstab -k {kv}", shell=True)
                        break # Success
                    except sp.CalledProcessError:
                        print(f"F: Creating initfs with kernel {kv} failed!")
                        continue

def install_mode():
    msg = "What mode would you like to install?\nY: Frugal\nN: Scatter"
    if yes_no(msg):
        return "frugal"
    else:
        return "scatter"

def strap(pkg, ARCH, URL):
    if ARCH == "x86_64":
        tcl_file = urlopen(f"{URL}/rootfs64.gz").read() # curl -LO
    elif ARCH == "x86":
        tcl_file = urlopen(f"{URL}/rootfs.gz").read()
    with TemporaryDirectory(dir="/tmp", prefix="ash.") as tmpdir:
        open(f"{tmpdir}/tcl_rootfs.gz", "wb").write(tcl_file)
        os.system('cd /mnt && sudo cpio -iv < f"{tmpdir}/rootfs.gz"')

main()

